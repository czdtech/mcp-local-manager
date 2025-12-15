#!/usr/bin/env python3
"""status 子命令实现（只读）。"""

from __future__ import annotations

from .. import utils as U


def run(args) -> int:
    """显示 MCP 服务器状态，包括中央配置和各客户端的实际启用状态。"""
    try:
        _, servers = U.load_central_servers()
    except Exception as e:
        print(f"❌ 加载中央配置失败: {e}")
        print("⚠️  尝试使用默认配置继续...")
        servers = {}

    enabled, disabled = U.split_enabled_servers(servers)
    enabled_names = set(enabled.keys())
    disabled_names = set(disabled.keys())
    print(f"📊 中央配置：总计 {len(servers)}，启用 {len(enabled)}，禁用 {len(disabled)}")
    if disabled_names:
        print("🚫 central 已禁用: " + ", ".join(sorted(disabled_names)))

    if getattr(args, "central", False):
        U.list_servers()

    sel = U._normalize_client(getattr(args, "client_pos", None)) or U._normalize_client(
        getattr(args, "client", None)
    )
    targets = [
        (
            "claude-file",
            "Claude(file)",
            lambda: U._json_keys(
                U.HOME / ".claude" / "settings.json", "mcpServers", "Claude配置读取"
            ),
        ),
        ("claude-reg", "Claude(register)", U._claude_registered),
        ("codex", "Codex", U._codex_keys),
        (
            "gemini",
            "Gemini",
            lambda: U._json_keys(
                U.HOME / ".gemini" / "settings.json", "mcpServers", "Gemini配置读取"
            ),
        ),
        (
            "iflow",
            "iFlow",
            lambda: U._json_keys(
                U.HOME / ".iflow" / "settings.json", "mcpServers", "iFlow配置读取"
            ),
        ),
        (
            "droid",
            "Droid",
            lambda: U._json_keys(U.HOME / ".factory" / "mcp.json", "mcpServers", "Droid配置读取"),
        ),
        (
            "cursor",
            "Cursor",
            lambda: U._json_keys(U.HOME / ".cursor" / "mcp.json", "mcpServers", "Cursor配置读取"),
        ),
        (
            "vscode-user",
            "VS Code(User)",
            lambda: U._json_keys(U._vscode_user_path(), "servers", "VS Code配置读取"),
        ),
        (
            "vscode-ins",
            "VS Code(Insiders)",
            lambda: U._json_keys(U._vscode_insiders_path(), "servers", "VS Code Insiders配置读取"),
        ),
    ]
    print("— 按客户端/IDE 的实际启用视图 —")

    def _print_client(label: str, present: set[str]) -> None:
        present_set = set(present or set())
        on_enabled = sorted(present_set & enabled_names)
        off_enabled = sorted(enabled_names - present_set)
        on_disabled = sorted(present_set & disabled_names)
        unknown = sorted(present_set - enabled_names - disabled_names)
        print(f"\n[{label}]")
        print("  on : " + (", ".join(on_enabled) if on_enabled else "无"))
        print("  off: " + (", ".join(off_enabled) if off_enabled else "无"))
        if on_disabled:
            print("  ⚠️ central 禁用但目标已配置: " + ", ".join(on_disabled))
        if unknown:
            print("  ⚠️ 目标存在但 central 未收录: " + ", ".join(unknown))

    for key, label, fn in targets:
        if sel and sel != key:
            continue
        try:
            present = fn()
            if getattr(args, "verbose", False):
                print(f"🔍 {label}: 找到 {len(present)} 个已配置服务器")
        except Exception as e:
            if getattr(args, "verbose", False):
                print(f"⚠️  {label}: 读取配置时出错 - {e}")
            present = set()
        _print_client(label, set(present))

    return 0
