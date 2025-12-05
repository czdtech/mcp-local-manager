#!/usr/bin/env python3
"""将中央清单中的 npx/uv 服务本地化，加速启动；落地时优先使用本地路径。"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

from .. import utils as U

LOCAL_ROOT = Path.home() / '.mcp-local'
RESOLVED = LOCAL_ROOT / 'resolved.json'


def _load_resolved() -> dict[str, str]:
    return U.load_json(RESOLVED, {}, "读取本地解析记录")


def _save_resolved(obj: dict[str, str]) -> None:
    RESOLVED.parent.mkdir(parents=True, exist_ok=True)
    RESOLVED.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding='utf-8')


def _pkg_base(pkg_spec: str) -> str:
    """去掉版本段，保留完整的 scope/pkg 形式。"""
    return pkg_spec.rsplit('@', 1)[0] if '@' in pkg_spec else pkg_spec


def _binary_name(pkg_spec: str) -> str:
    """根据 npm 包 spec 推导二进制名。

    兼容形式：
      - pkg
      - pkg@latest / pkg@1.2.3
      - @scope/pkg
      - @scope/pkg@latest
    规则：
      1) 去掉最后一个 @ 之后的版本段；
      2) 若带 scope，仅保留最后一段（pkg）。
    """
    base = pkg_spec.rsplit('@', 1)[0] if '@' in pkg_spec else pkg_spec
    if '/' in base:
        base = base.split('/')[-1]
    return base


def _locate_binary(install_dir: Path, pkg_base: str, pkg_spec: str) -> Path | None:
    """在已安装目录内查找真实的可执行二进制路径。"""
    bin_dir = install_dir / 'node_modules' / '.bin'
    if not bin_dir.exists():
        return None

    candidates: list[str] = []

    # 优先读取 package.json 的 bin 字段，避免猜测失败（如 @playwright/mcp）。
    pkg_json = install_dir / 'node_modules' / pkg_base / 'package.json'
    if pkg_json.exists():
        try:
            pkg_meta = json.loads(pkg_json.read_text())
            bin_field = pkg_meta.get('bin')
            if isinstance(bin_field, str):
                # npm 对 string 形式的 bin 会使用包名（去 scope）作为二进制名
                candidates.append(_binary_name(pkg_spec))
            elif isinstance(bin_field, dict):
                # dict 形式的 key 就是真实的可执行名
                candidates.extend(list(bin_field.keys()))
        except Exception:
            pass

    # 保持与历史逻辑一致的猜测项
    candidates.append(_binary_name(pkg_spec))

    seen: set[str] = set()
    for name in candidates:
        if not name or name in seen:
            continue
        seen.add(name)
        cand = bin_dir / name
        if cand.exists() and os.access(cand, os.X_OK):
            return cand

    # 兜底：返回 .bin 下的第一个可执行文件，避免空手而归
    for cand in sorted(bin_dir.iterdir()):
        if cand.is_file() and os.access(cand, os.X_OK):
            return cand

    return None


def _extract_pkg_spec(args: list[str]) -> str | None:
    """从 npx 参数中提取真实的包名 spec（跳过 -y/--yes 等前缀）。

    例如:
      ["-y","task-master-ai@latest"]        -> "task-master-ai@latest"
      ["--yes","@scope/server@latest"]     -> "@scope/server@latest"
      ["pkg@1.2.3"]                        -> "pkg@1.2.3"
    """
    if not args:
        return None
    i = 0
    while i < len(args) and args[i] in ('-y', '--yes'):
        i += 1
    if i >= len(args):
        return None
    return args[i]


def _install_npm(name: str, pkg_spec: str, force: bool, upgrade: bool) -> str | None:
    install_dir = LOCAL_ROOT / 'npm' / name
    pkg_base = _pkg_base(pkg_spec)

    # 若已存在有效二进制且无需强制/升级，直接复用
    if not force and not upgrade:
        existing = _locate_binary(install_dir, pkg_base, pkg_spec)
        if existing:
            print(f"[SKIP] {name}: 已存在本地版 {existing}")
            return str(existing)

    cmd = ['npm', 'install', '--prefix', str(install_dir)]
    if upgrade:
        cmd.append('--force')
    cmd.append(pkg_spec)

    print(f"[INFO] 安装 {name} -> {install_dir}")
    try:
        subprocess.run(cmd, check=True, text=True, capture_output=True, timeout=180)
    except subprocess.CalledProcessError as e:
        print(f"[ERR] 安装失败 {name}: {e.stderr or e.stdout}")
        return None

    target = _locate_binary(install_dir, pkg_base, pkg_spec)
    if target and target.exists() and os.access(target, os.X_OK):
        return str(target)

    bin_dir = install_dir / 'node_modules' / '.bin'
    if bin_dir.exists():
        bins = ', '.join(p.name for p in sorted(bin_dir.iterdir()))
        print(f"[ERR] 未找到可执行文件，.bin 内容：{bins}")
    else:
        print(f"[ERR] 未找到 .bin 目录：{bin_dir}")
    return None


def _prune():
    if LOCAL_ROOT.exists():
        shutil.rmtree(LOCAL_ROOT)
        print(f"[OK] 已清理本地镜像: {LOCAL_ROOT}")
    else:
        print("[INFO] 无本地镜像可清理")


def run(args) -> int:
    if getattr(args, 'prune', False):
        _prune()
        return 0

    upgrade = bool(getattr(args, 'upgrade', False))
    force = bool(getattr(args, 'force', False))

    obj, servers = U.load_central_servers()
    if not servers:
        print("[ERR] 中央清单为空")
        return 1

    resolved = _load_resolved()
    changed = False
    ok = 0
    skip = 0
    fail = 0

    for name, info in servers.items():
        cmd = (info or {}).get('command')
        args_list = (info or {}).get('args') or []
        if cmd == 'npx' and args_list:
            pkg_spec = _extract_pkg_spec(list(args_list))
            if not pkg_spec:
                fail += 1
                continue
            path = _install_npm(name, pkg_spec, force, upgrade)
            if path:
                resolved[name] = path
                changed = True
                ok += 1
            else:
                fail += 1
        else:
            skip += 1

    if changed:
        _save_resolved(resolved)
    total = ok + skip + fail
    print(f"[SUMMARY] 本地化完成 total={total} ok={ok} skip={skip} fail={fail}")
    if fail:
        print("[HINT] 可重试: mcp localize --force 或检查网络/npm/uv 环境")
    return 0 if fail == 0 else 1
