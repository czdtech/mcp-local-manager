#!/usr/bin/env python3
from __future__ import annotations

"""status 子命令实现（只读）。"""

from .. import utils as U


def run(args) -> int:
    """显示 MCP 服务器状态，包括中央配置和各客户端的实际启用状态。"""
    try:
        obj, servers = U.load_central_servers()
    except Exception as e:
        print(f"❌ 加载中央配置失败: {e}")
        print("⚠️  尝试使用默认配置继续...")
        servers = {}
        obj = {}

    central_names = sorted(servers.keys())
    print(f"📊 中央配置中的服务器数量: {len(central_names)}")

    if getattr(args, 'central', False):
        U.list_servers()

    sel = U._normalize_client(getattr(args, 'client_pos', None)) or U._normalize_client(getattr(args, 'client', None))
    targets = [
        ('claude-file', 'Claude(file)', lambda: U._json_keys(U.HOME/'.claude'/'settings.json', 'mcpServers', 'Claude配置读取')),
        ('claude-reg',  'Claude(register)', U._claude_registered),
        ('codex',       'Codex', U._codex_keys),
        ('gemini',      'Gemini', lambda: U._json_keys(U.HOME/'.gemini'/'settings.json', 'mcpServers', 'Gemini配置读取')),
        ('iflow',       'iFlow', lambda: U._json_keys(U.HOME/'.iflow'/'settings.json', 'mcpServers', 'iFlow配置读取')),
        ('droid',       'Droid', lambda: U._json_keys(U.HOME/'.factory'/'mcp.json', 'mcpServers', 'Droid配置读取')),
        ('cursor',      'Cursor', lambda: U._json_keys(U.HOME/'.cursor'/'mcp.json', 'mcpServers', 'Cursor配置读取')),
        ('vscode-user', 'VS Code(User)', lambda: U._json_keys(U._vscode_user_path(), 'servers', 'VS Code配置读取')),
        ('vscode-ins',  'VS Code(Insiders)', lambda: U._json_keys(U._vscode_insiders_path(), 'servers', 'VS Code Insiders配置读取')),
    ]
    print("— 按客户端/IDE 的实际启用视图 —")
    for key, label, fn in targets:
        if sel and sel != key:
            continue
        try:
            present = fn()
            if getattr(args, 'verbose', False):
                print(f"🔍 {label}: 找到 {len(present)} 个已配置服务器")
        except Exception as e:
            if getattr(args, 'verbose', False):
                print(f"⚠️  {label}: 读取配置时出错 - {e}")
            present = set()
        U._print_client(label, present, central_names)

    return 0
