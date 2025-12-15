#!/usr/bin/env python3
"""check 子命令实现（只读健康检查）。"""

from __future__ import annotations

from .. import utils as U


def run(args) -> int:
    print("MCP 健康检查报告")
    print(f"- 中央清单: {U.CENTRAL}")
    for label, path in [
        ("Claude 文件", U.HOME / ".claude" / "settings.json"),
        ("Codex TOML", U.HOME / ".codex" / "config.toml"),
        ("Gemini 文件", U.HOME / ".gemini" / "settings.json"),
        ("iFlow 文件", U.HOME / ".iflow" / "settings.json"),
        ("Droid 文件", U.HOME / ".factory" / "mcp.json"),
        ("Cursor 文件", U.HOME / ".cursor" / "mcp.json"),
        ("VS Code(User)", U._vscode_user_path()),
        ("VS Code(Insiders)", U._vscode_insiders_path()),
    ]:
        state = "存在" if path.exists() else "缺失"
        print(f"  [INFO] {label}: {path} ({state})")
    print("\n结论: 最小体检完成（如需深度体检，请执行 scripts/mcp-check.sh）")
    return 0
