import json
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from mcp_cli import utils as U
from mcp_cli.commands import ui as UI


def _http_json(url: str, token: str, *, method: str = "GET", payload: dict | None = None) -> dict:
    headers = {"X-MCP-Token": token}
    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=5) as resp:  # noqa: S310
        return json.loads(resp.read().decode("utf-8"))


def test_ui_state_and_toggle_cursor(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    # 让 UI/central/targets 都落在隔离 HOME
    home = tmp_path
    monkeypatch.setattr(U, "HOME", home)
    monkeypatch.setattr(U, "CENTRAL", home / ".mcp-central" / "config" / "mcp-servers.json")

    U.save_json(
        U.CENTRAL,
        {
            "version": "1.1.0",
            "description": "test",
            "servers": {
                "context7": {"enabled": True, "command": "npx", "args": ["-y", "@upstash/context7-mcp@latest"]},
                "disabled-one": {"enabled": False, "command": "npx", "args": ["-y", "x@latest"]},
            },
        },
    )

    cursor_path = home / ".cursor" / "mcp.json"
    U.save_json(cursor_path, {"mcpServers": {}})

    token = "test-token"
    srv = UI.create_server("127.0.0.1", 0, token=token)
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    try:
        port = srv.server_address[1]
        base = f"http://127.0.0.1:{port}"

        meta = _http_json(base + "/api/clients", token)
        assert meta["ok"] is True

        state = _http_json(base + "/api/state?client=cursor", token)
        assert state["ok"] is True
        assert state["central"]["total"] == 2
        assert state["target"]["present"] == []

        res = _http_json(
            base + "/api/toggle",
            token,
            method="POST",
            payload={"client": "cursor", "server": "context7", "on": True},
        )
        assert res["ok"] is True
        obj = json.loads(cursor_path.read_text(encoding="utf-8"))
        assert "context7" in obj.get("mcpServers", {})

        with pytest.raises(urllib.error.HTTPError):
            _http_json(
                base + "/api/toggle",
                token,
                method="POST",
                payload={"client": "cursor", "server": "disabled-one", "on": True},
            )

        # unknown 可被移除（不依赖 central）
        obj["mcpServers"]["unknown-svc"] = {"command": "x"}
        cursor_path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
        _http_json(
            base + "/api/toggle",
            token,
            method="POST",
            payload={"client": "cursor", "server": "unknown-svc", "on": False},
        )
        obj2 = json.loads(cursor_path.read_text(encoding="utf-8"))
        assert "unknown-svc" not in obj2.get("mcpServers", {})

        # unknown 可被“一键收录”进 central（带 source 标记）
        obj2["mcpServers"]["ext-one"] = {"command": "npx", "args": ["-y", "ext@latest"], "env": {"A": "1"}}
        cursor_path.write_text(json.dumps(obj2, ensure_ascii=False, indent=2), encoding="utf-8")
        imp = _http_json(
            base + "/api/import",
            token,
            method="POST",
            payload={"client": "cursor", "server": "ext-one"},
        )
        assert imp["ok"] is True
        central_obj = json.loads(U.CENTRAL.read_text(encoding="utf-8"))
        assert "ext-one" in central_obj.get("servers", {})
        assert central_obj["servers"]["ext-one"].get("source") == "imported:cursor"
    finally:
        srv.shutdown()
        srv.server_close()


def test_ui_token_required(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    home = tmp_path
    monkeypatch.setattr(U, "HOME", home)
    monkeypatch.setattr(U, "CENTRAL", home / ".mcp-central" / "config" / "mcp-servers.json")
    U.save_json(U.CENTRAL, {"version": "1.1.0", "description": "test", "servers": {}})

    token = "test-token"
    srv = UI.create_server("127.0.0.1", 0, token=token)
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    try:
        port = srv.server_address[1]
        base = f"http://127.0.0.1:{port}"
        with pytest.raises(urllib.error.HTTPError) as e:
            _http_json(base + "/api/clients", "wrong-token")
        assert e.value.code == 403
    finally:
        srv.shutdown()
        srv.server_close()


def test_ui_central_admin_endpoints(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    home = tmp_path
    monkeypatch.setattr(U, "HOME", home)
    monkeypatch.setattr(U, "CENTRAL", home / ".mcp-central" / "config" / "mcp-servers.json")
    U.save_json(
        U.CENTRAL,
        {
            "version": "1.1.0",
            "description": "test",
            "servers": {"central-one": {"command": "npx", "args": ["-y", "x@latest"], "enabled": True}},
        },
    )

    token = "test-token"
    srv = UI.create_server("127.0.0.1", 0, token=token)
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    try:
        port = srv.server_address[1]
        base = f"http://127.0.0.1:{port}"

        _http_json(
            base + "/api/central/set-enabled",
            token,
            method="POST",
            payload={"name": "central-one", "enabled": False},
        )
        obj2 = json.loads(U.CENTRAL.read_text(encoding="utf-8"))
        assert obj2["servers"]["central-one"].get("enabled") is False

        _http_json(
            base + "/api/central/delete",
            token,
            method="POST",
            payload={"name": "central-one"},
        )
        obj3 = json.loads(U.CENTRAL.read_text(encoding="utf-8"))
        assert "central-one" not in obj3.get("servers", {})
    finally:
        srv.shutdown()
        srv.server_close()


def test_ui_targets_remove_everywhere(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    home = tmp_path
    monkeypatch.setattr(U, "HOME", home)
    monkeypatch.setattr(U, "CENTRAL", home / ".mcp-central" / "config" / "mcp-servers.json")
    U.save_json(U.CENTRAL, {"version": "1.1.0", "description": "test", "servers": {}})

    # 避免测试环境真实执行 claude/droid 外部命令
    def _fake_run(*_a, **_kw):  # noqa: ANN001
        raise FileNotFoundError("fake")

    monkeypatch.setattr(UI.subprocess, "run", _fake_run)

    cursor_path = home / ".cursor" / "mcp.json"
    U.save_json(cursor_path, {"mcpServers": {"x": {"command": "npx", "args": ["-y", "x@latest"]}}})

    token = "test-token"
    srv = UI.create_server("127.0.0.1", 0, token=token)
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    try:
        port = srv.server_address[1]
        base = f"http://127.0.0.1:{port}"

        res = _http_json(
            base + "/api/targets/remove",
            token,
            method="POST",
            payload={"server": "x"},
        )
        assert res["ok"] is True

        obj = json.loads(cursor_path.read_text(encoding="utf-8"))
        assert "x" not in obj.get("mcpServers", {})

        # 不应为不存在的目标配置创建空文件（例如 Gemini）
        assert not (home / ".gemini" / "settings.json").exists()

        cursor_rows = [t for t in (res.get("targets") or []) if t.get("client") == "cursor"]
        assert cursor_rows and cursor_rows[0].get("changed") is True
    finally:
        srv.shutdown()
        srv.server_close()
