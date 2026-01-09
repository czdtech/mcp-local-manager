#!/usr/bin/env python3
"""ui 子命令：本地 Web UI（列表 + 开关，实时落地到目标端）。

设计目标：
- 面向普通用户：不记命令，不理解 central/落地细节也能用。
- 一个页面：选择目标客户端 → 一张表 → 开关即写入（带备份）。
- 安全：仅监听 127.0.0.1；所有 API 必须携带一次性 token。
"""

from __future__ import annotations

import http.server
import json
import os
import re
import secrets
import subprocess
import threading
from copy import deepcopy
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from .. import utils as U
from . import central as CENTRAL
from . import run as RUN

_WRITE_LOCK = threading.Lock()
_UI_INDEX_PATH = Path(__file__).with_name("ui_index.html")
_UI_INDEX_CACHE: bytes | None = None


def _coerce_claude_scope(v: object | None) -> str:
    """将用户输入规范化为 Claude scope。

    Claude Code 支持：local/user/project。
    - None: 回退到环境变量/默认值（utils.claude_registry_scope，默认 user）
    """

    if v is None:
        return U.claude_registry_scope()
    s = str(v).strip().lower()
    if s in ("local", "user", "project"):
        return s
    raise ValueError("claude_scope 必须是 local/user/project")


def _expand_tilde(v: object) -> object:
    if isinstance(v, str):
        try:
            return os.path.expanduser(v)
        except Exception:
            return v
    return v


def _index_html_bytes() -> bytes:
    global _UI_INDEX_CACHE
    if _UI_INDEX_CACHE is not None:
        return _UI_INDEX_CACHE
    try:
        _UI_INDEX_CACHE = _UI_INDEX_PATH.read_text(encoding="utf-8").encode()
    except Exception:
        _UI_INDEX_CACHE = "UI 资源缺失：mcp_cli/commands/ui_index.html\n".encode()
    return _UI_INDEX_CACHE


def _json_error(handler: http.server.BaseHTTPRequestHandler, code: int, msg: str) -> None:
    payload = {"ok": False, "error": msg}
    body = json.dumps(payload, ensure_ascii=False).encode()
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _json_ok(handler: http.server.BaseHTTPRequestHandler, payload: dict[str, Any]) -> None:
    body = json.dumps(payload, ensure_ascii=False, indent=2).encode()
    handler.send_response(200)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _require_token(handler: http.server.BaseHTTPRequestHandler) -> bool:
    token = getattr(handler.server, "ui_token", "")
    got = handler.headers.get("X-MCP-Token") or ""
    if token and got == token:
        return True
    _json_error(handler, 403, "token 无效或缺失，请从终端输出的 URL 打开 UI。")
    return False


def _client_catalog() -> list[dict[str, str]]:
    return [
        {"key": "cursor", "label": "Cursor"},
        {"key": "vscode-user", "label": "VS Code(User)"},
        {"key": "vscode-insiders", "label": "VS Code(Insiders)"},
        {"key": "claude", "label": "Claude"},
        {"key": "codex", "label": "Codex"},
        {"key": "gemini", "label": "Gemini"},
        {"key": "iflow", "label": "iFlow"},
        {"key": "droid", "label": "Droid"},
    ]


def _central_state() -> dict[str, Any]:
    central_path = U.CENTRAL
    exists = central_path.exists()
    data = CENTRAL._load_central_or_new()  # noqa: SLF001
    ok, msg = CENTRAL._validate(data)  # noqa: SLF001
    servers_all = data.get("servers") if isinstance(data, dict) else {}
    if not isinstance(servers_all, dict):
        servers_all = {}
    enabled, disabled = U.split_enabled_servers(servers_all)
    return {
        "path": str(central_path),
        "exists": exists,
        "valid": ok,
        "message": msg,
        "total": len(servers_all),
        "enabled": len(enabled),
        "disabled": len(disabled),
        "servers": {k: servers_all[k] for k in sorted(servers_all.keys())},
        "enabled_names": sorted(enabled.keys()),
        "disabled_names": sorted(disabled.keys()),
    }


def _load_json_map(path: Path, top_key: str) -> tuple[dict[str, Any], dict[str, Any]]:
    obj = U.load_json(path, {}, f"读取 {path.name}")
    if not isinstance(obj, dict):
        obj = {}
    raw = obj.get(top_key)
    if not isinstance(raw, dict):
        raw = {}
    return obj, raw


def _save_json_map(path: Path, obj: dict[str, Any]) -> None:
    U.backup(path)
    U.save_json(path, obj)


def _claude_project_overrides() -> tuple[dict[str, list[str]], Path]:
    p = U.HOME / ".claude.json"
    obj = U.load_json(p, {}, "")
    if not isinstance(obj, dict):
        return {}, p
    projects = obj.get("projects")
    if not isinstance(projects, dict):
        return {}, p

    out: dict[str, list[str]] = {}
    for name, conf in projects.items():
        if not isinstance(conf, dict):
            continue
        mcp_servers = conf.get("mcpServers")
        if isinstance(mcp_servers, dict) and mcp_servers:
            out[str(name)] = sorted([str(k) for k in mcp_servers.keys()])
    return out, p


def _target_state(client: str, central: dict[str, Any]) -> dict[str, Any]:
    servers_all = central.get("servers") or {}
    all_names = set(servers_all.keys())
    disabled_names = set(central.get("disabled_names") or [])

    def _mk(present: set[str], path: Path | None) -> dict[str, Any]:
        unknown = sorted(present - all_names)
        disabled_present = sorted(present & disabled_names)
        return {
            "path": str(path) if path else None,
            "present": sorted(present),
            "unknown": unknown,
            "disabled_present": disabled_present,
        }

    if client == "cursor":
        p = U.HOME / ".cursor" / "mcp.json"
        _, mp = _load_json_map(p, "mcpServers")
        return _mk(set(mp.keys()), p)
    if client == "gemini":
        p = U.HOME / ".gemini" / "settings.json"
        _, mp = _load_json_map(p, "mcpServers")
        return _mk(set(mp.keys()), p)
    if client == "iflow":
        p = U.HOME / ".iflow" / "settings.json"
        _, mp = _load_json_map(p, "mcpServers")
        return _mk(set(mp.keys()), p)
    if client == "droid":
        p = U.HOME / ".factory" / "mcp.json"
        _, mp = _load_json_map(p, "mcpServers")
        return _mk(set(mp.keys()), p)
    if client == "vscode-user":
        p = U._vscode_user_path()
        _, mp = _load_json_map(p, "servers")
        return _mk(set(mp.keys()), p)
    if client == "vscode-insiders":
        p = U._vscode_insiders_path()
        _, mp = _load_json_map(p, "servers")
        return _mk(set(mp.keys()), p)
    if client == "codex":
        p = U.HOME / ".codex" / "config.toml"
        present = U._codex_keys()
        return _mk(set(present), p)
    if client == "claude":
        p = U.HOME / ".claude" / "settings.json"
        _, mp = _load_json_map(p, "mcpServers")
        file_present = set(mp.keys())
        reg_present = set(U._claude_registered())
        overrides, overrides_path = _claude_project_overrides()
        present = file_present | reg_present
        out = _mk(present, p)
        out["claude_file_present"] = sorted(file_present)
        out["claude_registry_present"] = sorted(reg_present)
        out["claude_project_overrides"] = {
            "path": str(overrides_path),
            "count": len(overrides),
            "examples": list(overrides.items())[:3],
        }
        return out
    raise ValueError(f"未知 client: {client}")


def _read_target_entry(client: str, name: str) -> dict[str, Any]:
    """从目标端配置读取某个 server 的原始定义（用于收录到 central）。"""
    if client == "cursor":
        p = U.HOME / ".cursor" / "mcp.json"
        _, mp = _load_json_map(p, "mcpServers")
        v = mp.get(name)
        if isinstance(v, dict):
            return v
        raise KeyError(f"Cursor 未找到: {name}")
    if client == "gemini":
        p = U.HOME / ".gemini" / "settings.json"
        _, mp = _load_json_map(p, "mcpServers")
        v = mp.get(name)
        if isinstance(v, dict):
            return v
        raise KeyError(f"Gemini 未找到: {name}")
    if client == "iflow":
        p = U.HOME / ".iflow" / "settings.json"
        _, mp = _load_json_map(p, "mcpServers")
        v = mp.get(name)
        if isinstance(v, dict):
            return v
        raise KeyError(f"iFlow 未找到: {name}")
    if client == "droid":
        p = U.HOME / ".factory" / "mcp.json"
        _, mp = _load_json_map(p, "mcpServers")
        v = mp.get(name)
        if isinstance(v, dict):
            return v
        raise KeyError(f"Droid 未找到: {name}")
    if client == "vscode-user":
        p = U._vscode_user_path()
        _, mp = _load_json_map(p, "servers")
        v = mp.get(name)
        if isinstance(v, dict):
            return v
        raise KeyError(f"VS Code(User) 未找到: {name}")
    if client == "vscode-insiders":
        p = U._vscode_insiders_path()
        _, mp = _load_json_map(p, "servers")
        v = mp.get(name)
        if isinstance(v, dict):
            return v
        raise KeyError(f"VS Code(Insiders) 未找到: {name}")
    if client == "claude":
        p = U.HOME / ".claude" / "settings.json"
        _, mp = _load_json_map(p, "mcpServers")
        v = mp.get(name)
        if isinstance(v, dict):
            return v
        # 可能仅存在于注册表：缺少配置详情无法收录
        raise KeyError(f"Claude 文件端未找到: {name}（若仅在注册表存在，无法自动收录）")
    if client == "codex":
        p = U.HOME / ".codex" / "config.toml"
        if not p.exists():
            raise KeyError("Codex 配置不存在")
        try:
            import tomllib

            conf = tomllib.loads(p.read_text(encoding="utf-8"))
            m = conf.get("mcp_servers", {}) or {}
            raw = m.get(name)
            if not isinstance(raw, dict):
                raise KeyError(f"Codex 未找到: {name}")
            out: dict[str, Any] = {}
            if raw.get("command"):
                out["command"] = raw["command"]
            if isinstance(raw.get("args"), list):
                out["args"] = [str(x) for x in raw.get("args") or []]
            env = raw.get("env")
            if isinstance(env, dict) and env:
                out["env"] = {str(k): str(v) for k, v in env.items() if v is not None}
            timeout = raw.get("startup_timeout_sec")
            if timeout is not None:
                try:
                    out["timeout"] = int(timeout)
                except Exception:
                    pass
            return out
        except Exception as e:
            raise KeyError(f"Codex 解析失败: {e}") from e

    raise ValueError(f"未知 client: {client}")


def import_to_central(client: str, name: str) -> dict[str, Any]:
    """将目标端已有条目收录到 central，并加上来源标记。"""
    raw = _read_target_entry(client, name)
    entry = U.to_target_server_info(raw, client=client)
    if not entry.get("command"):
        raise ValueError("目标端条目缺少 command，无法收录到 central")

    entry["enabled"] = True
    entry["source"] = f"imported:{client}"

    with _WRITE_LOCK:
        data = CENTRAL._load_central_or_new()  # noqa: SLF001
        servers = data.setdefault("servers", {})
        if name in servers:
            raise ValueError(f"central 已存在同名条目: {name}")
        servers[name] = entry
        CENTRAL._save_central(data, dry=False)  # noqa: SLF001

    return {"imported": name, "entry": entry}


def delete_from_central(name: str) -> dict[str, Any]:
    name = str(name or "").strip()
    if not name:
        raise ValueError("缺少 name")

    with _WRITE_LOCK:
        data = CENTRAL._load_central_or_new()  # noqa: SLF001
        servers = data.setdefault("servers", {})
        if name not in servers:
            raise ValueError(f"central 未找到: {name}")
        removed = servers.pop(name)
        CENTRAL._save_central(data, dry=False)  # noqa: SLF001
    return {"deleted": name, "entry": removed}


def set_central_enabled(name: str, enabled: bool) -> dict[str, Any]:
    name = str(name or "").strip()
    if not name:
        raise ValueError("缺少 name")

    with _WRITE_LOCK:
        data = CENTRAL._load_central_or_new()  # noqa: SLF001
        servers = data.setdefault("servers", {})
        if name not in servers:
            raise ValueError(f"central 未找到: {name}")
        servers[name]["enabled"] = bool(enabled)
        CENTRAL._save_central(data, dry=False)  # noqa: SLF001
    return {"name": name, "enabled": bool(enabled)}


def _build_server_info_from_central(
    central_servers: dict[str, Any], name: str, client: str | None = None
) -> dict[str, Any]:
    if name not in central_servers:
        raise KeyError(f"central 未收录: {name}")
    info = central_servers.get(name) or {}
    if not isinstance(info, dict):
        raise ValueError(f"central 配置非法（必须是对象）: {name}")
    subset = {name: deepcopy(info)}
    original = deepcopy(subset)
    subset = RUN._apply_local_override(subset, client=client)  # noqa: SLF001
    subset = RUN._fallback_to_original(subset, original)  # noqa: SLF001
    return subset[name]


def _to_droid_entry(info: dict[str, Any]) -> dict[str, Any]:
    server_config: dict[str, Any] = {"type": "stdio"}
    if "command" in info:
        server_config["command"] = info["command"]
    if "args" in info:
        server_config["args"] = info["args"]
    if "env" in info and info.get("env"):
        server_config["env"] = info["env"]
    if "timeout" in info and info.get("timeout") is not None:
        server_config["timeout"] = info["timeout"]
    return server_config


def _sync_claude_registry(
    name: str,
    info: dict[str, Any] | None,
    on: bool,
    *,
    claude_scope: str | None = None,
) -> list[str]:
    notes: list[str] = []
    scope = _coerce_claude_scope(claude_scope)
    if on:
        cmd = ["claude", "mcp", "add", "--transport", "stdio"]
        for k, v in (info or {}).get("env") or {}.items():
            cmd += ["--env", f"{k}={v}"]
        cmd += ["-s", scope, name]
        cmd += ["--", str(_expand_tilde((info or {}).get("command", "")))]
        cmd += [str(_expand_tilde(a)) for a in ((info or {}).get("args") or [])]
        try:
            r = subprocess.run(cmd, check=False, timeout=45, capture_output=True, text=True)
            if r.returncode != 0:
                notes.append(
                    "⚠️ claude registry add 失败（已写入文件端）: " + (r.stderr or r.stdout or "")
                )
        except Exception as e:
            notes.append(f"⚠️ claude registry add 异常（已写入文件端）: {e}")
        return notes

    try:
        cmd_rm = ["claude", "mcp", "remove", name, "-s", scope]
        r = subprocess.run(cmd_rm, check=False, timeout=15, capture_output=True, text=True)
        if r.returncode != 0:
            notes.append(
                "⚠️ claude registry remove 失败（已写入文件端）: " + (r.stderr or r.stdout or "")
            )
    except Exception as e:
        notes.append(f"⚠️ claude registry remove 异常（已写入文件端）: {e}")
    return notes


def _sync_droid_registry(name: str, info: dict[str, Any] | None, on: bool) -> list[str]:
    notes: list[str] = []
    if on:
        cmd_str = " ".join(
            [str(_expand_tilde((info or {}).get("command", "")))]
            + [str(_expand_tilde(a)) for a in ((info or {}).get("args") or [])]
        )
        cmd = ["droid", "mcp", "add", name, cmd_str]
        for k, v in (info or {}).get("env") or {}.items():
            cmd += ["--env", f"{k}={v}"]
        try:
            r = subprocess.run(cmd, check=False, timeout=30, capture_output=True, text=True)
            if r.returncode != 0:
                notes.append(
                    "⚠️ droid registry add 失败（已写入文件端）: " + (r.stderr or r.stdout or "")
                )
        except Exception as e:
            notes.append(f"⚠️ droid registry add 异常（已写入文件端）: {e}")
        return notes

    try:
        cmd_rm = ["droid", "mcp", "remove", name]
        r = subprocess.run(cmd_rm, check=False, timeout=10, capture_output=True, text=True)
        if r.returncode != 0:
            notes.append(
                "⚠️ droid registry remove 失败（已写入文件端）: " + (r.stderr or r.stdout or "")
            )
    except Exception as e:
        notes.append(f"⚠️ droid registry remove 异常（已写入文件端）: {e}")
    return notes


def _codex_strip_server_tables(text: str, name: str) -> str:
    """从 Codex config.toml 中移除指定 server 的所有表段（含 .env 等子表）。"""
    name_esc = re.escape(str(name))
    # 兼容我们自己写入的标记行（若存在）
    text = re.sub(
        rf"(?m)^\s*# === MCP Server: {name_esc} .*?\n",
        "",
        text,
    )
    # 移除 [mcp_servers.<name>] 以及 [mcp_servers.<name>.*] 相关段落
    text = re.sub(
        rf"(?ms)^\[mcp_servers\.{name_esc}(?:\.[^\]]+)?\][\s\S]*?(?=^\[|\Z)",
        "",
        text,
    )
    return text


def _codex_render_server_block(name: str, info: dict[str, Any]) -> str:
    """渲染单个 Codex server 的 TOML 段落（追加到文件末尾）。"""
    info = U.to_target_server_info(info or {}, client="codex")
    name = str(name)

    timeout = info.get("timeout")
    try:
        timeout_sec = int(timeout) if timeout is not None else 60
    except Exception:
        timeout_sec = 60
    if timeout_sec < 1:
        timeout_sec = 60

    cmd = str(info.get("command") or "")
    args = info.get("args") or []
    env = info.get("env") or {}

    lines: list[str] = []
    lines.append(f"\n# === MCP Server: {name} (由 MCP Local Manager 生成) ===")
    lines.append(f"[mcp_servers.{name}]")
    lines.append(f"startup_timeout_sec = {timeout_sec}")
    lines.append(f"tool_timeout_sec = {timeout_sec}")
    lines.append("command = " + json.dumps(cmd))
    if isinstance(args, list) and args:
        lines.append("args = " + json.dumps([str(x) for x in args]))
    if isinstance(env, dict) and env:
        lines.append(f"\n[mcp_servers.{name}.env]")
        for k, v in env.items():
            lines.append(f"{k} = " + json.dumps(str(v)))
    lines.append("")
    return "\n".join(lines)


def remove_from_target(
    client: str, name: str, *, claude_scope: str | None = None
) -> dict[str, Any]:
    """从目标端删除某个 server（不会为不存在的配置文件创建空文件）。"""
    name = str(name or "").strip()
    if not name:
        raise ValueError("缺少 server name")

    notes: list[str] = []
    changed = False
    skipped: str | None = None

    def _remove_json_key(path: Path, top_key: str, *, update_gemini_allowed: bool = False) -> None:
        nonlocal changed
        obj = U.load_json(path, {}, f"读取 {path.name}")
        if not isinstance(obj, dict):
            obj = {}
        raw = obj.get(top_key)
        if not isinstance(raw, dict):
            raw = {}

        before_allowed = None
        if update_gemini_allowed:
            before_allowed = list((obj.get("mcp") or {}).get("allowed") or [])

        if name in raw:
            raw.pop(name, None)
            changed = True

        obj[top_key] = raw
        if update_gemini_allowed:
            obj.setdefault("mcp", {})["allowed"] = sorted(raw.keys())
            after_allowed = list(obj["mcp"]["allowed"])
            if before_allowed != after_allowed:
                changed = True

        if changed:
            U.backup(path)
            U.save_json(path, obj)

    with _WRITE_LOCK:
        if client == "cursor":
            p = U.HOME / ".cursor" / "mcp.json"
            if not p.exists():
                skipped = f"配置不存在: {p}"
                return {"client": client, "changed": False, "skipped": skipped, "notes": notes}
            _remove_json_key(p, "mcpServers")
            return {"client": client, "changed": changed, "skipped": skipped, "notes": notes}

        if client == "gemini":
            p = U.HOME / ".gemini" / "settings.json"
            if not p.exists():
                skipped = f"配置不存在: {p}"
                return {"client": client, "changed": False, "skipped": skipped, "notes": notes}
            _remove_json_key(p, "mcpServers", update_gemini_allowed=True)
            return {"client": client, "changed": changed, "skipped": skipped, "notes": notes}

        if client == "iflow":
            p = U.HOME / ".iflow" / "settings.json"
            if not p.exists():
                skipped = f"配置不存在: {p}"
                return {"client": client, "changed": False, "skipped": skipped, "notes": notes}
            _remove_json_key(p, "mcpServers")
            return {"client": client, "changed": changed, "skipped": skipped, "notes": notes}

        if client == "vscode-user":
            p = U._vscode_user_path()
            if not p.exists():
                skipped = f"配置不存在: {p}"
                return {"client": client, "changed": False, "skipped": skipped, "notes": notes}
            _remove_json_key(p, "servers")
            return {"client": client, "changed": changed, "skipped": skipped, "notes": notes}

        if client == "vscode-insiders":
            p = U._vscode_insiders_path()
            if not p.exists():
                skipped = f"配置不存在: {p}"
                return {"client": client, "changed": False, "skipped": skipped, "notes": notes}
            _remove_json_key(p, "servers")
            return {"client": client, "changed": changed, "skipped": skipped, "notes": notes}

        if client == "claude":
            p = U.HOME / ".claude" / "settings.json"
            if p.exists():
                _remove_json_key(p, "mcpServers")
            else:
                skipped = f"文件端配置不存在（将仅尝试注册表移除）: {p}"
            notes += _sync_claude_registry(name, None, False, claude_scope=claude_scope)
            return {"client": client, "changed": changed, "skipped": skipped, "notes": notes}

        if client == "droid":
            p = U.HOME / ".factory" / "mcp.json"
            if p.exists():
                _remove_json_key(p, "mcpServers")
            else:
                skipped = f"文件端配置不存在（将仅尝试注册表移除）: {p}"
            notes += _sync_droid_registry(name, None, False)
            return {"client": client, "changed": changed, "skipped": skipped, "notes": notes}

        if client == "codex":
            p = U.HOME / ".codex" / "config.toml"
            if not p.exists():
                skipped = f"配置不存在: {p}"
                return {"client": client, "changed": False, "skipped": skipped, "notes": notes}
            text = p.read_text(encoding="utf-8")
            new_text = _codex_strip_server_tables(text, name)
            if new_text != text:
                U.backup(p)
                p.write_text(new_text, encoding="utf-8")
                changed = True
            return {"client": client, "changed": changed, "skipped": skipped, "notes": notes}

        raise ValueError(f"未知 client: {client}")


def remove_everywhere(
    name: str,
    *,
    claude_scope: str | None = None,
) -> dict[str, Any]:
    """从多个目标端移除指定 server（默认：UI 支持的全部目标）。"""
    name = str(name or "").strip()
    if not name:
        raise ValueError("缺少 server")

    results: list[dict[str, Any]] = []
    errors: dict[str, str] = {}
    for c in [c["key"] for c in _client_catalog()]:
        try:
            results.append(remove_from_target(c, name, claude_scope=claude_scope))
        except Exception as e:
            errors[c] = str(e)

    return {"server": name, "targets": results, "errors": errors}


def apply_toggle(
    client: str,
    name: str,
    on: bool,
    *,
    claude_scope: str | None = None,
) -> dict[str, Any]:
    central = _central_state()
    servers_all: dict[str, Any] = central.get("servers") or {}
    disabled_names = set(central.get("disabled_names") or [])

    info: dict[str, Any] | None = None
    if on:
        if name in disabled_names:
            raise ValueError(f"此服务在 central 已禁用（enabled:false）：{name}。请先启用再落地。")
        info = _build_server_info_from_central(servers_all, name, client=client)

    notes: list[str] = []
    with _WRITE_LOCK:
        if client == "codex":
            p = U.HOME / ".codex" / "config.toml"
            if not p.exists():
                raise RuntimeError(f"Codex 配置不存在: {p}")
            text = p.read_text(encoding="utf-8")
            new_text = _codex_strip_server_tables(text, name)
            if on:
                new_text = new_text.rstrip() + _codex_render_server_block(name, info or {})
            if new_text != text:
                U.backup(p)
                p.write_text(new_text, encoding="utf-8")
            return {"notes": notes, "client": client, "changed": {"server": name, "on": on}}

        if client == "claude":
            p = U.HOME / ".claude" / "settings.json"
            changed = False
            if on or p.exists():
                obj, mp = _load_json_map(p, "mcpServers")
                if on:
                    mp[name] = U.to_target_server_info(info or {}, client="claude")
                    changed = True
                else:
                    if name in mp:
                        mp.pop(name, None)
                        changed = True
                obj["mcpServers"] = mp
                if changed:
                    _save_json_map(p, obj)
            notes += _sync_claude_registry(name, info, on, claude_scope=claude_scope)
            return {"notes": notes, "client": client, "changed": {"server": name, "on": on}}

        if client == "cursor":
            p = U.HOME / ".cursor" / "mcp.json"
            changed = False
            if on or p.exists():
                obj, mp = _load_json_map(p, "mcpServers")
                if on:
                    mp[name] = U.to_target_server_info(info or {}, client="cursor")
                    changed = True
                else:
                    if name in mp:
                        mp.pop(name, None)
                        changed = True
                obj["mcpServers"] = mp
                if changed:
                    _save_json_map(p, obj)
            return {"notes": notes, "client": client, "changed": {"server": name, "on": on}}

        if client == "gemini":
            p = U.HOME / ".gemini" / "settings.json"
            changed = False
            if on or p.exists():
                obj, mp = _load_json_map(p, "mcpServers")
                before_allowed = list((obj.get("mcp") or {}).get("allowed") or [])
                if on:
                    mp[name] = U.to_target_server_info(info or {}, client="gemini")
                    changed = True
                else:
                    if name in mp:
                        mp.pop(name, None)
                        changed = True
                obj["mcpServers"] = mp
                obj.setdefault("mcp", {})["allowed"] = sorted(mp.keys())
                if list(obj["mcp"]["allowed"]) != before_allowed:
                    changed = True
                if changed:
                    _save_json_map(p, obj)
            return {"notes": notes, "client": client, "changed": {"server": name, "on": on}}

        if client == "iflow":
            p = U.HOME / ".iflow" / "settings.json"
            changed = False
            if on or p.exists():
                obj, mp = _load_json_map(p, "mcpServers")
                if on:
                    mp[name] = U.to_target_server_info(info or {}, client="iflow")
                    changed = True
                else:
                    if name in mp:
                        mp.pop(name, None)
                        changed = True
                obj["mcpServers"] = mp
                if changed:
                    _save_json_map(p, obj)
            return {"notes": notes, "client": client, "changed": {"server": name, "on": on}}

        if client == "droid":
            p = U.HOME / ".factory" / "mcp.json"
            changed = False
            if on or p.exists():
                obj, mp = _load_json_map(p, "mcpServers")
                if on:
                    mp[name] = _to_droid_entry(info or {})
                    changed = True
                else:
                    if name in mp:
                        mp.pop(name, None)
                        changed = True
                obj["mcpServers"] = mp
                if changed:
                    _save_json_map(p, obj)
            notes += _sync_droid_registry(name, info, on)
            return {"notes": notes, "client": client, "changed": {"server": name, "on": on}}

        if client == "vscode-user":
            p = U._vscode_user_path()
            changed = False
            if on or p.exists():
                obj, mp = _load_json_map(p, "servers")
                if on:
                    mp[name] = U.to_target_server_info(info or {}, client="vscode-user")
                    changed = True
                else:
                    if name in mp:
                        mp.pop(name, None)
                        changed = True
                obj["servers"] = mp
                if changed:
                    _save_json_map(p, obj)
            return {"notes": notes, "client": client, "changed": {"server": name, "on": on}}

        if client == "vscode-insiders":
            p = U._vscode_insiders_path()
            changed = False
            if on or p.exists():
                obj, mp = _load_json_map(p, "servers")
                if on:
                    mp[name] = U.to_target_server_info(info or {}, client="vscode-insiders")
                    changed = True
                else:
                    if name in mp:
                        mp.pop(name, None)
                        changed = True
                obj["servers"] = mp
                if changed:
                    _save_json_map(p, obj)
            return {"notes": notes, "client": client, "changed": {"server": name, "on": on}}

        raise ValueError(f"未知 client: {client}")


class _UIHandler(http.server.BaseHTTPRequestHandler):
    server: Any

    def log_message(self, fmt: str, *args: Any) -> None:
        # UI 模式默认不刷屏；如需调试可设置 MCP_UI_DEBUG=1
        if os.environ.get("MCP_UI_DEBUG") == "1":
            super().log_message(fmt, *args)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/":
            qs = parse_qs(parsed.query or "")
            token = (qs.get("token") or [""])[0]
            if token != getattr(self.server, "ui_token", ""):
                self.send_response(403)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.end_headers()
                self.wfile.write("token 无效，请从终端输出的 URL 打开。\n".encode())
                return
            body = _index_html_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if not path.startswith("/api/"):
            self.send_response(404)
            self.end_headers()
            return

        if not _require_token(self):
            return

        if path == "/api/clients":
            _json_ok(
                self,
                {
                    "ok": True,
                    "clients": _client_catalog(),
                    "default": "cursor",
                    "claude_scopes": ["user", "local", "project"],
                    "cwd": os.getcwd(),
                },
            )
            return

        if path == "/api/state":
            qs = parse_qs(parsed.query or "")
            client = (qs.get("client") or [""])[0]
            if not client:
                _json_error(self, 400, "缺少 client 参数")
                return
            try:
                central = _central_state()
                target = _target_state(client, central)
            except Exception as e:
                _json_error(self, 400, str(e))
                return
            _json_ok(self, {"ok": True, "client": client, "central": central, "target": target})
            return

        _json_error(self, 404, "未知 API")

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        if not path.startswith("/api/"):
            self.send_response(404)
            self.end_headers()
            return

        if not _require_token(self):
            return

        if (self.headers.get("Content-Type") or "").split(";")[
            0
        ].strip().lower() != "application/json":
            _json_error(self, 415, "只接受 application/json")
            return

        try:
            raw = self.rfile.read(int(self.headers.get("Content-Length") or "0") or 0)
            data = json.loads(raw.decode("utf-8") if raw else "{}")
        except Exception:
            _json_error(self, 400, "JSON 解析失败")
            return

        if path == "/api/toggle":
            client = str(data.get("client") or "").strip()
            name = str(data.get("server") or "").strip()
            on = bool(data.get("on"))
            if not client or not name:
                _json_error(self, 400, "缺少 client/server")
                return
            try:
                claude_scope = data.get("claude_scope", None)
                out = apply_toggle(client, name, on, claude_scope=claude_scope)
                res = {"ok": True, **out}
            except Exception as e:
                _json_error(self, 400, str(e))
                return
            _json_ok(self, res)
            return

        if path == "/api/import":
            client = str(data.get("client") or "").strip()
            name = str(data.get("server") or "").strip()
            if not client or not name:
                _json_error(self, 400, "缺少 client/server")
                return
            try:
                out = import_to_central(client, name)
            except Exception as e:
                _json_error(self, 400, str(e))
                return
            _json_ok(self, {"ok": True, **out, "notes": [f"已收录到 central: {name}"]})
            return

        if path == "/api/central/delete":
            name = str(data.get("name") or "").strip()
            try:
                out = delete_from_central(name)
            except Exception as e:
                _json_error(self, 400, str(e))
                return
            _json_ok(self, {"ok": True, **out, "notes": [f"已从 central 删除: {name}"]})
            return

        if path == "/api/central/set-enabled":
            name = str(data.get("name") or "").strip()
            enabled = bool(data.get("enabled"))
            try:
                out = set_central_enabled(name, enabled)
            except Exception as e:
                _json_error(self, 400, str(e))
                return
            _json_ok(self, {"ok": True, **out})
            return

        if path == "/api/targets/remove":
            name = str(data.get("server") or data.get("name") or "").strip()
            try:
                claude_scope = data.get("claude_scope", None)
                out = remove_everywhere(name, claude_scope=claude_scope)
            except Exception as e:
                _json_error(self, 400, str(e))
                return
            _json_ok(self, {"ok": True, **out})
            return

        _json_error(self, 404, "未知 API")


class MCPUIHTTPServer(http.server.ThreadingHTTPServer):
    allow_reuse_address = True

    def __init__(self, server_address: tuple[str, int], *, ui_token: str):
        super().__init__(server_address, _UIHandler)
        self.ui_token = ui_token


def create_server(host: str, port: int, *, token: str) -> MCPUIHTTPServer:
    return MCPUIHTTPServer((host, port), ui_token=token)


def run(args) -> int:
    host = str(getattr(args, "host", "127.0.0.1") or "127.0.0.1")
    # 默认不使用固定常见端口，避免冲突：0 = 让系统分配空闲端口
    port = int(getattr(args, "port", 0) or 0)
    token = secrets.token_urlsafe(18)

    srv = create_server(host, port, token=token)
    actual_port = srv.server_address[1]
    url = f"http://{host}:{actual_port}/?token={token}"
    print("MCP Web UI 已启动（Ctrl+C 退出）")
    print("打开：")
    print("  " + url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
    return 0
