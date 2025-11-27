#!/usr/bin/env python3
from __future__ import annotations

"""clear 子命令实现：清除各客户端 MCP 配置（含注册表）。"""

import os
import subprocess
from pathlib import Path
from .. import utils as U


def _clear_json_map(label: str, path: Path, top_key='mcpServers', extra: str | None = None, dry_run: bool = False):
    if dry_run:
        print(f"[DRY-RUN] 将清空 {label} 的配置: {path}")
        return 0
    if not path.exists():
        print(f"[INFO] 跳过 {label}（配置不存在）: {path}")
        return 0
    obj = U.load_json(path, {})
    if top_key == 'servers':
        obj['servers'] = {}
    else:
        obj[top_key] = {}
        if label.startswith('Gemini'):
            obj.setdefault('mcp', {})['allowed'] = []
    if extra == 'gemini.allowed':
        obj.setdefault('mcp', {})['allowed'] = []
    U.backup(path)
    U.save_json(path, obj)
    print(f"[OK] 已清空 {label}: {path}")
    return 0


def _clear_claude_registry(verbose: bool = False, dry_run: bool = False):
    if dry_run:
        print('[DRY-RUN] 将清空 Claude 注册表（预览，跳过 `claude mcp list`）')
        return 0
    try:
        out = subprocess.run(['claude', 'mcp', 'list'], capture_output=True, text=True, timeout=30)
        text = (out.stdout or '') + "\n" + (out.stderr or '')
        names = []
        for line in text.splitlines():
            if ':' in line:
                names.append(line.split(':', 1)[0].strip())
    except Exception:
        names = []
    if not names:
        if verbose:
            print('[INFO] Claude 注册表无条目需清理')
        return 0
    ok = 0
    fail = 0
    for n in names:
        try:
            cmd = ['claude', 'mcp', 'remove', n]
            if verbose:
                print('[VERBOSE]', ' '.join(cmd))
            r = subprocess.run(cmd, check=False, timeout=10)
            ok += 1 if r.returncode == 0 else 0
            fail += 1 if r.returncode != 0 else 0
        except Exception:
            fail += 1
    print(f"[OK] 已清理 Claude 注册表: ok={ok} fail={fail}")
    return 0


def _preview(targets: list[str], dry_run: bool) -> None:
    print('— 清理预览 —')
    print('目标客户端:', ', '.join(targets))
    print('模式      : ' + ('DRY-RUN 预览' if dry_run else '实际写入'))
    for t in targets:
        if t == 'claude':
            print(f'  - Claude 文件: {U.HOME/".claude"/"settings.json"}; 注册表: claude mcp remove *')
        elif t == 'codex':
            print(f'  - Codex TOML: {U.HOME/".codex"/"config.toml"}')
        elif t == 'gemini':
            print(f'  - Gemini JSON: {U.HOME/".gemini"/"settings.json"}')
        elif t == 'iflow':
            print(f'  - iFlow JSON: {U.HOME/".iflow"/"settings.json"}')
        elif t == 'droid':
            print(f'  - Droid JSON: {U.HOME/".factory"/"mcp.json"}')
        elif t == 'cursor':
            print(f'  - Cursor JSON: {U.HOME/".cursor"/"mcp.json"}')
        elif t == 'vscode-user':
            print(f'  - VS Code(User): {U._vscode_user_path()}')
        elif t == 'vscode-insiders':
            print(f'  - VS Code(Insiders): {U._vscode_insiders_path()}')


def run(args) -> int:
    """交互式/非交互式清除各客户端 MCP 配置。"""
    dry_run = bool(getattr(args, '_dry_run', False) or getattr(args, 'dry_run', False))
    all_targets = ['claude', 'codex', 'gemini', 'iflow', 'droid', 'cursor', 'vscode-user', 'vscode-insiders']
    preset = getattr(args, 'client', None)
    if preset:
        # 将别名映射到 clear 子命令内部统一的 client 名称
        alias_map = {
            'claude': 'claude',
            'claude-file': 'claude',
            'claude-reg': 'claude',
            'codex': 'codex',
            'gemini': 'gemini',
            'iflow': 'iflow',
            'droid': 'droid',
            'cursor': 'cursor',
            'vscode': 'vscode-user',
            'vscode-user': 'vscode-user',
            'vscode-insiders': 'vscode-insiders',
            'vscode-ins': 'vscode-insiders',
            'insiders': 'vscode-insiders',
        }
        targets: list[str] = []
        unknown: list[str] = []
        for raw in preset:
            if not raw:
                continue
            key = alias_map.get(str(raw).strip().lower())
            if key and key in all_targets:
                if key not in targets:
                    targets.append(key)
            else:
                unknown.append(str(raw))
        if not targets:
            # 显式指定了 client 但一个都识别不了：不要回退到“全部清理”，而是直接报错并不做任何修改
            print(f"[ERR] 未识别的客户端: {', '.join(unknown)}")
            print("可用客户端: " + ', '.join(all_targets))
            return 1
        if unknown:
            print(f"[WARN] 已忽略未识别的客户端: {', '.join(unknown)}")
    else:
        print('选择要清除的客户端（空格分隔编号；留空=全部）:')
        for i, k in enumerate(all_targets, start=1):
            print(f'  {i}) {k}')
        picks = input('输入编号列表: ').strip().split()
        if picks:
            targets = []
            for p in picks:
                if p.isdigit() and 1 <= int(p) <= len(all_targets):
                    targets.append(all_targets[int(p)-1])
            if not targets:
                print('已取消'); return 0
        else:
            targets = all_targets
    _preview(targets, dry_run)
    if dry_run:
        return 0
    if os.environ.get('MCP_CLEAR_YES') == '1':
        reply = 'y'
    elif getattr(args, 'yes', False):
        reply = 'y'
    else:
        reply = (input(f"将清空以下客户端: {', '.join(targets)}，确认? [y/N]: ").strip().lower() or 'n')
    if reply != 'y':
        print('已取消')
        return 0

    for t in targets:
        try:
            if t == 'claude':
                _clear_json_map('Claude(文件)', U.HOME/'.claude'/'settings.json', 'mcpServers', dry_run=dry_run)
                _clear_claude_registry(verbose=getattr(args, 'verbose', False), dry_run=dry_run)
            elif t == 'codex':
                p = U.HOME/'.codex'/'config.toml'
                if dry_run:
                    print(f"[DRY-RUN] 将清理 Codex 配置: {p}")
                else:
                    if not p.exists():
                        print(f"[INFO] 跳过 Codex（配置不存在）: {p}")
                    else:
                        U.backup(p)
                        text = p.read_text(encoding='utf-8')
                        new_text = U.strip_toml_mcp_servers_block(text)
                        p.write_text(new_text, encoding='utf-8')
                        print(f"[OK] 已清空 Codex: {p}")
            elif t == 'gemini':
                _clear_json_map('Gemini', U.HOME/'.gemini'/'settings.json', 'mcpServers', extra='gemini.allowed', dry_run=dry_run)
            elif t == 'iflow':
                _clear_json_map('iFlow', U.HOME/'.iflow'/'settings.json', 'mcpServers', dry_run=dry_run)
            elif t == 'droid':
                _clear_json_map('Droid', U.HOME/'.factory'/'mcp.json', 'mcpServers', dry_run=dry_run)
            elif t == 'cursor':
                _clear_json_map('Cursor', U.HOME/'.cursor'/'mcp.json', 'mcpServers', dry_run=dry_run)
            elif t == 'vscode-user':
                _clear_json_map('VS Code(User)', U._vscode_user_path(), 'servers', dry_run=dry_run)
            elif t == 'vscode-insiders':
                _clear_json_map('VS Code(Insiders)', U._vscode_insiders_path(), 'servers', dry_run=dry_run)
        except Exception as e:
            print(f"[WARN] 清理 {t} 失败: {e}")
    print('[OK] 清理完成')
    return 0
