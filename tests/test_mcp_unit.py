#!/usr/bin/env python3
"""
bin/mcp 内部函数的单元级测试：
- 映射/规范化与路径选择函数
- 文本清理函数
- DRY_RUN 下的写入预览函数

通过 importlib 从文件路径动态加载 bin/mcp 模块，避免改变现有入口结构。
"""

from __future__ import annotations

import io
import json
import os
import sys
from pathlib import Path
import importlib.util
import contextlib


def _load_mcp_module():
    path = Path(__file__).resolve().parents[1] / 'bin' / 'mcp'
    import importlib.machinery
    loader = importlib.machinery.SourceFileLoader('mcp_bin_module', str(path))
    spec = importlib.util.spec_from_loader('mcp_bin_module', loader)
    assert spec is not None
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


def test_normalize_client_aliases():
    from mcp_cli import utils as U
    f = getattr(U, '_normalize_client')
    assert f('claude') == 'claude-file'
    assert f('vscode') == 'vscode-user'
    assert f('insiders') == 'vscode-ins'
    assert f('cursor') == 'cursor'
    assert f('codex') == 'codex'


def test_strip_toml_mcp_block():
    from mcp_cli import utils as U
    f = getattr(U, 'strip_toml_mcp_servers_block')
    src = (
        "# other\n"
        "# === MCP Servers 配置（由 MCP Local Manager 生成）===\n"
        "[mcp_servers.foo]\ncommand=\"x\"\n"
        "# ===\n"
        "[general]\nkey=1\n"
        "[mcp_servers.bar]\ncommand=\"y\"\n"
    )
    out = f(src)
    assert "[mcp_servers.foo]" not in out
    assert "[mcp_servers.bar]" not in out
    assert "[general]" in out


def test_os_detection_and_paths(monkeypatch, tmp_path):
    from mcp_cli import utils as U
    monkeypatch.setenv('HOME', str(tmp_path))
    monkeypatch.setenv('MCP_OS', 'darwin')
    assert getattr(U, '_is_macos')() is True
    user = getattr(U, '_vscode_user_path')()
    ins = getattr(U, '_vscode_insiders_path')()
    assert str(user).endswith('Library/Application Support/Code/User/mcp.json')
    assert str(ins).endswith('Library/Application Support/Code - Insiders/User/mcp.json')

    monkeypatch.setenv('MCP_OS', 'linux')
    assert getattr(U, '_is_macos')() is False
    user = getattr(U, '_vscode_user_path')()
    ins = getattr(U, '_vscode_insiders_path')()
    assert str(user).endswith('.config/Code/User/mcp.json')
    assert str(ins).endswith('.config/Code - Insiders/User/mcp.json')


def test_apply_json_map_dry_run(monkeypatch, tmp_path):
    from mcp_cli.commands import run as RUN
    # 准备最小子集
    subset = {'filesystem': {'command': 'npx', 'args': ['-y', 'mcp-server-filesystem@latest']}}
    # DRY-RUN 打开
    monkeypatch.setenv('HOME', str(tmp_path))
    # 直接使用模块化实现，无需依赖 bin/mcp 的全局 DRY_RUN
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        RUN.apply_json_map('Cursor', Path(tmp_path) / '.cursor' / 'mcp.json', subset, 'mcpServers', dry_run=True)
    out = buf.getvalue()
    assert 'DRY-RUN' in out
    assert 'Cursor' in out and 'mcp.json' in out


def test_apply_json_map_droid_preserves_non_mcp_fields(tmp_path):
    from mcp_cli.commands import run as RUN

    path = Path(tmp_path) / '.factory' / 'mcp.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {"keep": {"a": 1}, "mcpServers": {"old": {"command": "x", "type": "stdio"}}},
            ensure_ascii=False,
            indent=2,
        ),
        encoding='utf-8',
    )

    subset = {"filesystem": {"command": "npx", "args": ["-y", "mcp-server-filesystem@latest"]}}
    rc = RUN.apply_json_map('Droid', path, subset, 'mcpServers', dry_run=False)
    assert rc == 0

    new_data = json.loads(path.read_text(encoding='utf-8'))
    assert new_data.get("keep") == {"a": 1}
    assert "filesystem" in (new_data.get("mcpServers") or {})
    assert "old" not in (new_data.get("mcpServers") or {})
    assert (path.with_name(path.name + ".backup")).exists()
