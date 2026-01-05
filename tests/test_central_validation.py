#!/usr/bin/env python3
"""
mcp_cli.commands.central 的校验逻辑回归测试。
"""

from __future__ import annotations

import builtins


def test_validate_fails_fast_when_jsonschema_missing(monkeypatch):
    """jsonschema 缺失时也应拦截 schema 级别错误（避免“静默跳过导致写入脏配置”）。"""
    from mcp_cli.commands import central as CENTRAL

    data = {
        "version": "1.1.0",
        "description": "test",
        # timeout=0 违反 schema(minimum:1)，此前在缺少 jsonschema 时可能被放过
        "servers": {"s1": {"command": "npx", "args": ["-y", "pkg@latest"], "timeout": 0}},
    }

    real_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):  # noqa: A002
        if name == "jsonschema":
            raise ImportError("mocked missing jsonschema")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    ok, msg = CENTRAL._validate(data)  # noqa: SLF001
    assert ok is False
    assert "timeout" in msg
