#!/usr/bin/env python3
from __future__ import annotations

"""run 子命令实现（按客户端落地 MCP 配置并可启动命令）。"""

import os
import subprocess
import json
from pathlib import Path
from .. import utils as U


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
        lines.append("startup_timeout_sec = 60")
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
        obj,_ = U.load_central_servers()
        servers = obj.get('servers') or {}
        for n in want:
            info = servers.get(n) or {}
            cmd = ['claude','mcp','add','--transport','stdio', n]
            for k,v in (info.get('env') or {}).items():
                cmd += ['-e', f'{k}={v}']
            cmd += ['--', _expand_tilde(info.get('command',''))]
            cmd += [ _expand_tilde(str(a)) for a in (info.get('args') or []) ]
            print('[DRY-RUN]', ' '.join(cmd))
        return 0

    # 实际对齐：先 remove 再 add
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
    # 移除所有 present 中属于 want 的项（稳妥起见）
    remove_ok=[]; remove_fail=[]
    for n in sorted(set(present) & set(want)):
        try:
            cmd_rm = ['claude','mcp','remove',n]
            if verbose:
                print('[VERBOSE]', ' '.join(cmd_rm))
            r = subprocess.run(cmd_rm, check=False, timeout=10)
            (remove_ok if r.returncode==0 else remove_fail).append(n)
        except Exception:
            remove_fail.append(n)
    # 再按中央清单重加
    obj,_ = U.load_central_servers()
    servers = obj.get('servers') or {}
    add_ok=[]; add_fail=[]
    for n in want:
        info = servers.get(n) or {}
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


def run(args) -> int:
    """run 子命令主入口。

    支持两种使用方式：
    1) `mcp run` 交互式：函数内部引导选择 client 与 servers；
    2) 预选模式：当 args 上已经带有 `client` 与 `servers` 时
      （例如 `mcp pick` 调用）直接按给定集合落地，避免重复交互。
    """
    # 是否 dry-run：兼容未来从外层传入 _dry_run 标记
    dry_run = bool(getattr(args, '_dry_run', False))

    client = getattr(args, 'client', None)
    pre_servers = getattr(args, 'servers', None)
    subset = None

    # 预选模式：pick 等入口会构造 client/servers 参数
    if client and pre_servers:
        _, servers = U.load_central_servers()
        if isinstance(pre_servers, str):
            names = [s for s in pre_servers.split(',') if s.strip()]
        elif isinstance(pre_servers, (list, tuple)):
            names = [str(s) for s in pre_servers if str(s).strip()]
        else:
            names = []
        names = [n for n in names if n in servers]
        if not names:
            print('[ERR] 选定的服务器在中央清单中不存在')
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
        print('\n选择要启用的 MCP（空格分隔编号；留空=第一个）:')
        for i,n in enumerate(names, start=1):
            print(f'  {i:2}) {n}')
        if os.environ.get('MCP_DEBUG'):
            print('[DBG] before picks', file=os.sys.stderr)
        picks = input('输入编号列表: ').strip().split()
        if os.environ.get('MCP_DEBUG'):
            print('[DBG] got picks', picks, file=os.sys.stderr)
        chosen = []
        for p in picks:
            if p.isdigit() and 1 <= int(p) <= len(names):
                chosen.append(names[int(p)-1])
        if not chosen:
            chosen = [names[0]]
        subset = {n: servers[n] for n in chosen}

    if os.environ.get('MCP_DEBUG'):
        print('[DBG] client', client, file=os.sys.stderr)

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
