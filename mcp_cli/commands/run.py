#!/usr/bin/env python3
from __future__ import annotations

"""run 子命令实现（按客户端落地 MCP 配置并可启动命令）。"""

import os
import shutil
import subprocess
import json
from pathlib import Path
from .. import utils as U
from . import localize as _localize

# 预设场景包（与 CLI 参数/交互菜单保持一致）
PRESET_PACKS = {
    "cursor-minimal": {
        "desc": "Cursor 最小包：task-master-ai + context7",
        "servers": ["task-master-ai", "context7"],
    },
    "claude-basic": {
        "desc": "Claude 文件+注册表：task-master-ai + context7",
        "servers": ["task-master-ai", "context7"],
    },
    "vscode-user-basic": {
        "desc": "VS Code(User) 基础：task-master-ai + context7",
        "servers": ["task-master-ai", "context7"],
    },
    "frontend-automation": {
        "desc": "前端自动化：playwright + chrome-devtools",
        "servers": ["playwright", "chrome-devtools"],
    },
    "doc-search": {
        "desc": "文档/本地检索：filesystem + context7",
        "servers": ["filesystem", "context7"],
    },
    "task-suite": {
        "desc": "任务管理：task-master-ai + context7（timeout/env 建议）",
        "servers": ["task-master-ai", "context7"],
    },
}


def _localize_on_run(subset: dict, mode: str) -> None:
    """在 mcp run 流程中按需执行本地化（npm 安装），并更新本地 resolved 映射。

    mode:
      - 'off'         : 不执行任何本地化
      - 'interactive' : 交互式选择要本地化的条目
      - 'all'         : 对当前 subset 中所有符合条件的 npx 服务执行本地化（非交互）
    """
    if mode not in ('interactive', 'all'):
        return

    resolved = _load_local_resolved()
    candidates: dict[str, str] = {}

    # 找出当前集合里可本地化但尚未成功落地的 npx 服务
    for name, info in subset.items():
        cmd = (info or {}).get('command')
        args = (info or {}).get('args') or []
        if cmd != 'npx' or not args:
            continue
        # 已有有效本地路径则跳过
        existing = resolved.get(name)
        if existing:
            p = Path(existing)
            if p.exists() and os.access(p, os.X_OK):
                continue
        # 提取真实包名 spec（跳过 -y/--yes）
        pkg_spec = _localize._extract_pkg_spec(list(args))
        if not pkg_spec:
            continue
        candidates[name] = pkg_spec

    if not candidates:
        if mode == 'interactive':
            print('[INFO] 当前所选集合中没有需要本地化的 npx 服务，跳过 localize')
        return

    selected_names: list[str]

    if mode == 'all':
        selected_names = list(candidates.keys())
    else:
        # 交互式选择要本地化的服务
        print('\n检测到以下 MCP 服务器可通过本地安装加速（npx → 本地二进制）：')
        items = list(candidates.items())
        for idx, (name, pkg) in enumerate(items, start=1):
            print(f'  {idx}) {name}  ({pkg})')
        print('选择要本地化的编号（空格分隔；留空=全部跳过；输入 0 = 全部本地化）：')
        picks = input('输入编号列表: ').strip().split()
        if not picks:
            print('[INFO] 已跳过本地化，本次仍通过 npx 启动这些服务')
            return
        if any(p == '0' for p in picks):
            selected_names = [name for name, _ in items]
        else:
            selected_names = []
            for p in picks:
                if p.isdigit():
                    i = int(p)
                    if 1 <= i <= len(items):
                        name = items[i-1][0]
                        if name not in selected_names:
                            selected_names.append(name)
        if not selected_names:
            print('[INFO] 未选择任何服务，本地化已跳过')
            return

    changed = False
    for name in selected_names:
        pkg_spec = candidates.get(name)
        if not pkg_spec:
            continue
        print(f"[INFO] 正在为 {name} 执行本地安装（{pkg_spec}）...")
        path = _localize._install_npm(name, pkg_spec, force=False, upgrade=False)
        if path:
            resolved[name] = path
            changed = True

    if changed:
        _save_local_resolved(resolved)
        if mode == 'interactive':
            print('[OK] 已更新本地化映射，后续 run 将优先使用本地二进制')
def _load_local_resolved() -> dict:
    path = U.HOME / '.mcp-local' / 'resolved.json'
    return U.load_json(path, {}, "读取本地化记录")


def _save_local_resolved(obj: dict) -> None:
    path = U.HOME / '.mcp-local' / 'resolved.json'
    U.save_json(path, obj)


def _strip_npx_args(cmd: str, args: list[str]) -> list[str]:
    """从 npx 参数中剥离 `-y/--yes` 与包名，仅保留真正传给 CLI 的参数。"""
    if cmd != 'npx' or not args:
        return list(args or [])
    i = 0
    # 跳过 -y/--yes
    while i < len(args) and args[i] in ('-y', '--yes'):
        i += 1
    # 跳过包名（pkg / scope/pkg / pkg@ver / @scope/pkg@ver）
    if i < len(args):
        i += 1
    return list(args[i:])


def _apply_local_override(subset: dict) -> dict:
    """若存在本地化记录，优先使用本地路径；失败回退原值。"""
    resolved = _load_local_resolved()
    if not resolved:
        return subset
    out = {}
    for name, info in subset.items():
        path = resolved.get(name)
        if path:
            p = Path(path)
            if p.is_absolute() and p.exists() and os.access(p, os.X_OK):
                new_info = dict(info)
                orig_cmd = (info or {}).get('command') or ''
                orig_args = list((info or {}).get('args') or [])
                new_info['command'] = path
                # 对 npx 迁移：去掉 npx 自身参数与包名，仅保留真正 CLI 参数
                new_info['args'] = _strip_npx_args(orig_cmd, orig_args)
                out[name] = new_info
                continue
        out[name] = info
    return out


def _ensure_command_exists(name: str, info: dict) -> bool:
    cmd = (info or {}).get('command')
    if not cmd:
        return False
    p = Path(cmd)
    if p.is_absolute():
        return p.exists() and os.access(p, os.X_OK)
    return shutil.which(cmd) is not None


def _fallback_to_original(subset: dict, original: dict) -> dict:
    """若当前 command 不可执行，回退到原始定义（通常为 npx），并输出提示。"""
    fixed = {}
    for name, info in subset.items():
        if _ensure_command_exists(name, info):
            fixed[name] = info
            continue
        orig = original.get(name)
        if orig and _ensure_command_exists(name, orig):
            print(f"[WARN] {name}: 本地/当前命令不可用，已回退到中央清单定义")
            fixed[name] = orig
        else:
            fixed[name] = info  # 保持原值，后续落地可能失败但保持透明
            print(f"[WARN] {name}: 找不到可用命令，请检查 npx/本地路径或重新 localize")
    return fixed


def _expand_tilde(v: object) -> object:
    if isinstance(v, str):
        try:
            return os.path.expanduser(v)
        except Exception:
            return v
    return v


def build_subset(names: list[str]) -> dict:
    obj, servers = U.load_central_servers()
    sel = {}
    for n in names:
        if n in servers:
            sel[n] = servers[n]
    return sel


def apply_codex(subset: dict, dry_run: bool=False) -> int:
    p = U.HOME/'.codex'/'config.toml'
    if not p.exists():
        print(f"[ERR] Codex 配置不存在: {p}")
        return 1
    keys = sorted(list(subset.keys()))
    if dry_run:
        print(f"[DRY-RUN] 将应用到 Codex: {p}")
        print("  keys:", ', '.join(keys) if keys else '(none)')
        return 0
    U.backup(p)
    text = p.read_text(encoding='utf-8')
    # 清理旧块 + 所有 [mcp_servers.*]
    text = U.strip_toml_mcp_servers_block(text)
    lines = ["\n# === MCP Servers 配置（由 MCP Local Manager 生成）==="]
    for name,info in subset.items():
        lines.append(f"\n[mcp_servers.{name}]")
        timeout = info.get('timeout') if isinstance(info, dict) else None
        try:
            timeout_sec = int(timeout) if timeout is not None else 60
        except Exception:
            timeout_sec = 60
        if timeout_sec < 1:
            timeout_sec = 60
        lines.append(f"startup_timeout_sec = {timeout_sec}")
        lines.append(f"command = \"{info.get('command','')}\"")
        args = info.get('args') or []
        if args:
            lines.append('args = ' + json.dumps(args))
        env = info.get('env') or {}
        if env:
            lines.append(f"\n[mcp_servers.{name}.env]")
            for k,v in env.items():
                lines.append(f"{k} = \"{v}\"")
    new_block='\n'.join(lines)+"\n"
    p.write_text(text.rstrip()+"\n"+new_block, encoding='utf-8')
    print(f"[OK] 已应用到 Codex: {p}")
    return 0


def apply_json_map(label: str, path: Path, subset: dict, top_key: str='mcpServers', dry_run: bool=False) -> int:
    obj = U.load_json(path, {})
    keys = sorted(list((subset or {}).keys()))
    if dry_run:
        print(f"[DRY-RUN] 将应用到 {label}: {path}")
        print("  keys:", ', '.join(keys) if keys else '(none)')
        return 0

    # Droid: 写入 ~/.factory/mcp.json 顶层 mcpServers（官方格式）
    if label == 'Droid':
        obj = {}
        servers_config = {}
        for name, info in subset.items():
            server_config = {}
            if 'command' in info:
                server_config['command'] = info['command']
            if 'args' in info:
                server_config['args'] = info['args']
            if 'env' in info and info['env']:
                server_config['env'] = info['env']
            if 'timeout' in info and info['timeout'] is not None:
                server_config['timeout'] = info['timeout']
            server_config['type'] = 'stdio'
            servers_config[name] = server_config
        obj['mcpServers'] = servers_config
    elif top_key == 'servers':
        obj['servers'] = subset
    else:
        obj[top_key] = subset
        if label == 'Gemini':
            obj.setdefault('mcp', {})['allowed'] = sorted(subset.keys())

    U.backup(path)
    U.save_json(path, obj)
    print(f"[OK] 已应用到 {label}: {path}")
    return 0


def apply_claude(subset: dict, verbose: bool=False, dry_run: bool=False) -> int:
    # 文件端
    apply_json_map('Claude(文件)', U.HOME/'.claude'/'settings.json', subset, 'mcpServers', dry_run=dry_run)

    # 注册表端：移除多余，补齐缺失，并强制与中央清单一致
    want = sorted(list(subset.keys()))
    if dry_run:
        print('[DRY-RUN] 将对齐 Claude 注册表（预览）')
        print('  keys:', ', '.join(want) if want else '(none)')
        # 展示 add/remove 预览
        for n in want:
            info = subset.get(n) or {}
            cmd = ['claude','mcp','add','--transport','stdio', n]
            for k,v in (info.get('env') or {}).items():
                cmd += ['-e', f'{k}={v}']
            cmd += ['--', _expand_tilde(info.get('command',''))]
            cmd += [ _expand_tilde(str(a)) for a in (info.get('args') or []) ]
            print('[DRY-RUN]', ' '.join(cmd))
        return 0

    # 实际对齐：先 remove 再 add（全量覆盖，避免残留）
    # 先尝试列出已注册项
    try:
        out = subprocess.run(['claude','mcp','list'], capture_output=True, text=True, timeout=10)
        text = (out.stdout or '') + "\n" + (out.stderr or '')
        present = []
        for line in text.splitlines():
            if ':' in line:
                present.append(line.split(':',1)[0].strip())
    except Exception:
        present = []
    # 移除所有现有注册项，确保只保留 want
    remove_ok=[]; remove_fail=[]
    for n in sorted(set(present)):
        try:
            cmd_rm = ['claude','mcp','remove',n]
            if verbose:
                print('[VERBOSE]', ' '.join(cmd_rm))
            r = subprocess.run(cmd_rm, check=False, timeout=10)
            (remove_ok if r.returncode==0 else remove_fail).append(n)
        except Exception:
            remove_fail.append(n)
    # 再按当前 subset 重加（包含本地化覆盖后的 command/args）
    add_ok=[]; add_fail=[]
    for n in want:
        info = subset.get(n) or {}
        try:
            subprocess.run(['claude','mcp','remove', n], check=False, timeout=10)
        except Exception:
            pass
        cmd = ['claude','mcp','add','--transport','stdio', n]
        for k,v in (info.get('env') or {}).items():
            cmd += ['-e', f'{k}={v}']
        cmd += ['--', _expand_tilde(info.get('command',''))]
        cmd += [ _expand_tilde(str(a)) for a in (info.get('args') or []) ]
        try:
            if verbose:
                print('[VERBOSE]', ' '.join(cmd))
            r = subprocess.run(cmd, check=False, timeout=45)
            (add_ok if r.returncode==0 else add_fail).append(n)
        except Exception:
            add_fail.append(n)
    print('[OK] Claude 注册表已与所选集合对齐')
    if remove_ok or remove_fail:
        print(f"  remove: ok={len(remove_ok)} fail={len(remove_fail)}" + (f"; failed=[{', '.join(remove_fail)}]" if remove_fail else ''))
    if add_ok or add_fail:
        print(f"  add   : ok={len(add_ok)} fail={len(add_fail)}" + (f"; failed=[{', '.join(add_fail)}]" if add_fail else ''))
    return 0


def _preview(client: str, subset: dict, dry_run: bool) -> None:
    names = sorted(subset.keys())
    print('— 差异预览 —')
    print(f'目标客户端: {client}')
    print('服务器集合: ' + (', '.join(names) if names else '(empty)'))
    if client == 'codex':
        print(f'目标文件  : {U.HOME/".codex"/"config.toml"}')
    elif client == 'gemini':
        print(f'目标文件  : {U.HOME/".gemini"/"settings.json"}')
    elif client == 'iflow':
        print(f'目标文件  : {U.HOME/".iflow"/"settings.json"}')
    elif client == 'droid':
        print(f'目标文件  : {U.HOME/".factory"/"mcp.json"}')
        print('注册表    : droid mcp remove/add (先删再加)')
    elif client == 'cursor':
        print(f'目标文件  : {U.HOME/".cursor"/"mcp.json"}')
    elif client == 'claude':
        print(f'目标文件  : {U.HOME/".claude"/"settings.json"}')
        print('注册表    : claude mcp remove/add')
    elif client == 'vscode-user':
        print(f'目标文件  : {U._vscode_user_path()}')
    elif client == 'vscode-insiders':
        print(f'目标文件  : {U._vscode_insiders_path()}')
    print(f'模式      : {"DRY-RUN 预览" if dry_run else "实际写入"}')


def run(args) -> int:
    """run 子命令主入口。

    支持两种使用方式：
    1) `mcp run` 交互式：函数内部引导选择 client 与 servers；
    2) 预选模式：当 args 上已经带有 `client` 与 `servers` 或 `preset` 时直接按给定集合落地，避免重复交互。
    """
    # 是否 dry-run：兼容未来从外层传入 _dry_run 标记
    dry_run = bool(getattr(args, '_dry_run', False) or getattr(args, 'dry_run', False))

    client = getattr(args, 'client', None)
    pre_servers = getattr(args, 'servers', None)
    pre_preset = getattr(args, 'preset', None)
    preselected = bool(client and (pre_servers or pre_preset))
    subset = None

    # 预选模式：参数构造 client/servers 或 preset
    if client and (pre_servers or pre_preset):
        _, servers = U.load_central_servers()
        if pre_servers:
            if isinstance(pre_servers, str):
                names = [s for s in pre_servers.split(',') if s.strip()]
            elif isinstance(pre_servers, (list, tuple)):
                names = [str(s) for s in pre_servers if str(s).strip()]
            else:
                names = []
        else:
            if pre_preset not in PRESET_PACKS:
                print(f'[ERR] 未知预设: {pre_preset}')
                return 1
            names = list(PRESET_PACKS[pre_preset]['servers'])
        missing = [n for n in names if n not in servers]
        if missing:
            print(f"[ERR] 选定的服务器不在中央清单: {', '.join(missing)}")
            return 1
        subset = {n: servers[n] for n in names}
    else:
        # 全交互式：引导选择客户端与服务器集合
        # 选择客户端
        clients = [
            ('claude','Claude'),
            ('codex','Codex'),
            ('gemini','Gemini'),
            ('iflow','iFlow'),
            ('droid','Droid'),
            ('cursor','Cursor'),
            ('vscode-user','VS Code(User)'),
            ('vscode-insiders','VS Code(Insiders)'),
        ]
        if os.environ.get('MCP_DEBUG'):
            print('[DBG] enter run', file=os.sys.stderr)
        print('选择目标 CLI/IDE:')
        for i,(k,label) in enumerate(clients, start=1):
            print(f'  {i}) {label} [{k}]')
        try:
            idx = int(input('输入编号: ').strip() or '1')
        except Exception:
            idx = 1
        client = clients[max(1, min(idx, len(clients)))-1][0]
        # 选择服务器集合
        _, servers = U.load_central_servers()
        names = sorted(servers.keys())
        if not names:
            print('[ERR] 中央清单为空')
            return 1
        # 预设/场景包优先
        presets = list(PRESET_PACKS.items())
        print('\n选择预设/场景包 (回车=1, 0=手动逐项选择):')
        for i,(k,v) in enumerate(presets, start=1):
            print(f'  {i}) {k} - {v["desc"]}')
        pick_preset_raw = input('输入编号: ').strip()
        chosen = []
        if pick_preset_raw in ('', None):
            pick_preset_raw = '1'
        if pick_preset_raw.isdigit() and int(pick_preset_raw) == 0:
            pick_preset_raw = None  # 走手动
        if pick_preset_raw and pick_preset_raw.isdigit() and 1 <= int(pick_preset_raw) <= len(presets):
            sel_name = presets[int(pick_preset_raw)-1][0]
            preset_servers = PRESET_PACKS.get(sel_name, {}).get('servers', [])
            missing = [n for n in preset_servers if n not in servers]
            if missing:
                print(f"[WARN] 预设 {sel_name} 中部分条目不在中央清单，已跳过: {', '.join(missing)}")
            chosen = [n for n in preset_servers if n in servers]
        if not chosen:
            print('\n选择要启用的 MCP（空格分隔编号；留空=第一个）:')
            for i,n in enumerate(names, start=1):
                print(f'  {i:2}) {n}')
            if os.environ.get('MCP_DEBUG'):
                print('[DBG] before picks', file=os.sys.stderr)
            picks = input('输入编号列表: ').strip().split()
            if os.environ.get('MCP_DEBUG'):
                print('[DBG] got picks', picks, file=os.sys.stderr)
            for p in picks:
                if p.isdigit() and 1 <= int(p) <= len(names):
                    chosen.append(names[int(p)-1])
            if not chosen:
                chosen = [names[0]]
        subset = {n: servers[n] for n in chosen}

    if os.environ.get('MCP_DEBUG'):
        print('[DBG] client', client, file=os.sys.stderr)

    # 非交互模式的预览与确认
    # 根据参数选择是否在 run 流程中执行一次本地化（可实现“边选边本地化”的混合配置）
    localize_mode = 'off'
    if getattr(args, 'localize', False) and not dry_run:
        # 预选模式下走“全部本地化”（避免额外交互）；纯交互模式则提供列表选择
        localize_mode = 'all' if preselected else 'interactive'
    _localize_on_run(subset, localize_mode)

    # 尝试应用本地化覆盖，再按需回退到中央清单定义
    original_subset = subset
    subset = _apply_local_override(subset)
    subset = _fallback_to_original(subset, original_subset)

    if (preselected or dry_run) and client and subset:
        _preview(client, subset, dry_run)
        if preselected and not dry_run and not getattr(args, 'yes', False):
            reply = input('确认写入? [y/N]: ').strip().lower() or 'n'
            if reply != 'y':
                print('已取消')
                return 0

    if client == 'claude':
        rc = apply_claude(subset, verbose=getattr(args, 'verbose', False), dry_run=dry_run)
    elif client == 'codex':
        rc = apply_codex(subset, dry_run=dry_run)
    elif client == 'gemini':
        rc = apply_json_map('Gemini', U.HOME/'.gemini'/'settings.json', subset, 'mcpServers', dry_run=dry_run)
    elif client == 'iflow':
        rc = apply_json_map('iFlow', U.HOME/'.iflow'/'settings.json', subset, 'mcpServers', dry_run=dry_run)
    elif client == 'droid':
        rc = apply_json_map('Droid', U.HOME/'.factory'/'mcp.json', subset, 'mcpServers', dry_run=dry_run)
        # 对齐 Droid 注册表
        want = set(subset.keys())
        obj,_ = U.load_central_servers()
        servers = obj.get('servers') or {}
        if dry_run:
            print('[DRY-RUN] 将对齐 Droid 注册（预览：先 remove 再 add）')
            print('  keys:', ', '.join(sorted(want)) if want else '(none)')
            for n in sorted(want):
                info = servers.get(n) or {}
                cmd_str = ' '.join([
                    _expand_tilde(info.get('command',''))
                ] + [_expand_tilde(str(a)) for a in (info.get('args') or [])])
                print('[DRY-RUN]', ' '.join(['droid','mcp','remove', n]))
                cmd = ['droid','mcp','add', n, cmd_str]
                for k,v in (info.get('env') or {}).items():
                    cmd += ['--env', f'{k}={v}']
                print('[DRY-RUN]', ' '.join(cmd))
        else:
            for n in sorted(want):
                try:
                    subprocess.run(['droid','mcp','remove', n], check=False, timeout=10)
                except Exception:
                    pass
                info = servers.get(n) or {}
                cmd_str = ' '.join([
                    _expand_tilde(info.get('command',''))
                ] + [_expand_tilde(str(a)) for a in (info.get('args') or [])])
                cmd = ['droid','mcp','add', n, cmd_str]
                for k,v in (info.get('env') or {}).items():
                    cmd += ['--env', f'{k}={v}']
                try:
                    if getattr(args, 'verbose', False):
                        print('[VERBOSE]', ' '.join(cmd))
                    subprocess.run(cmd, check=False, timeout=30)
                except Exception:
                    pass
    elif client == 'cursor':
        rc = apply_json_map('Cursor', U.HOME/'.cursor'/'mcp.json', subset, 'mcpServers', dry_run=dry_run)
    elif client == 'vscode-user':
        rc = apply_json_map('VS Code(User)', U._vscode_user_path(), subset, 'servers', dry_run=dry_run)
    elif client == 'vscode-insiders':
        rc = apply_json_map('VS Code(Insiders)', U._vscode_insiders_path(), subset, 'servers', dry_run=dry_run)
    else:
        print('[ERR] 未知 client')
        return 2

    if isinstance(rc, int) and rc != 0:
        return rc

    # 可选执行命令（提供建议与健壮校验）
    import shutil
    default_exec = {
        'claude': 'claude',
        'codex': 'codex',
        'gemini': 'gemini',
        'iflow': 'iflow',
        'droid': 'droid',
        'cursor': 'cursor',
        'vscode-user': 'code',
        'vscode-insiders': 'code-insiders',
    }.get(client, '')

    def _prompt_once():
        hint = (
            f"（回车跳过，输入 ? 查看建议，输入 y 用默认 {default_exec}）"
            if default_exec else "（回车跳过，输入 ? 查看建议）"
        )
        return input(f'是否要启动相关程序? {hint}: ').strip()

    attempt = 0
    while True:
        attempt += 1
        if os.environ.get('MCP_DEBUG'):
            print('[DBG] prompt attempt', attempt, file=os.sys.stderr)
        raw = _prompt_once()
        if os.environ.get('MCP_DEBUG'):
            print('[DBG] raw', repr(raw), file=os.sys.stderr)
        if not raw:
            print('[OK] 已应用所选集合；未提供启动命令，结束。')
            return 0
        if raw == '?':
            print('常用命令建议：')
            print('  - claude / codex / gemini / iflow / droid / cursor')
            print('  - VS Code: code / code-insiders')
            print('  - 也可输入绝对路径或任意可执行命令')
            continue
        yn = raw.strip().lower()
        if (yn == 'y' or yn == 'yes' or yn in ('是','好','确定') or 'y' in yn) and default_exec:
            cmd = default_exec
        else:
            cmd = raw
        parts = cmd.split()
        exe = parts[0]
        # 验证命令是否存在（绝对路径或 PATH）
        exists = (os.path.isabs(exe) and os.path.exists(exe)) or (shutil.which(exe) is not None)
        if not exists:
            print(f"[ERR] 未找到命令: {exe}。请检查 PATH 或输入绝对路径。")
            if attempt < 3:
                continue
            return 1
        try:
            os.execvp(exe, parts)
        except FileNotFoundError:
            print(f"[ERR] 启动失败：找不到可执行文件 {exe}")
            return 1
        except Exception as e:
            print(f"[ERR] 启动失败：{e}")
            return 1
