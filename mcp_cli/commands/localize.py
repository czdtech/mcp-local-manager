#!/usr/bin/env python3
from __future__ import annotations

"""将中央清单中的 npx/uv 服务本地化，加速启动；落地时优先使用本地路径。"""

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Any

from .. import utils as U

LOCAL_ROOT = Path.home() / '.mcp-local'
RESOLVED = LOCAL_ROOT / 'resolved.json'


def _load_resolved() -> Dict[str, str]:
    return U.load_json(RESOLVED, {}, "读取本地解析记录")


def _save_resolved(obj: Dict[str, str]) -> None:
    RESOLVED.parent.mkdir(parents=True, exist_ok=True)
    RESOLVED.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding='utf-8')


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
    bin_dir = install_dir / 'node_modules' / '.bin'
    bin_name = _binary_name(pkg_spec)
    target = bin_dir / bin_name

    if target.exists() and os.access(target, os.X_OK) and not force and not upgrade:
        print(f"[SKIP] {name}: 已存在本地版 {target}")
        return str(target)

    cmd = ['npm', 'install', '--prefix', str(install_dir)]
    if upgrade:
        cmd.append('--force')
    cmd.append(pkg_spec)

    print(f"[INFO] 安装 {name} -> {target}")
    try:
        subprocess.run(cmd, check=True, text=True, capture_output=True, timeout=180)
    except subprocess.CalledProcessError as e:
        print(f"[ERR] 安装失败 {name}: {e.stderr or e.stdout}")
        return None
    if not target.exists():
        # 尝试 fallback：列出 bin_dir
        if bin_dir.exists():
            bins = list(bin_dir.iterdir())
            if bins:
                target = bins[0]
    return str(target) if target.exists() and os.access(target, os.X_OK) else None


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
