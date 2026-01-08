#!/usr/bin/env python3
"""通用工具与平台/路径/注册表探测函数。

仅供 mcp_cli.commands.* 调用；保持纯函数或可预测副作用，便于单测。
"""

from __future__ import annotations

import json
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

# HOME/CENTRAL 由 Path.home() 推导，受环境变量 HOME 影响，测试已隔离
HOME = Path.home()
CENTRAL = HOME / ".mcp-central" / "config" / "mcp-servers.json"

# 校验模块（可选）
try:
    from mcp_validation import (
        MCPConfigError,
        MCPSchemaError,
        MCPValidationError,
        format_validation_error,
        validate_mcp_servers_config,
    )

    VALIDATION_AVAILABLE = True
except ImportError:
    VALIDATION_AVAILABLE = False

    def validate_mcp_servers_config(config_path):
        return {}

    class MCPValidationError(Exception):
        pass

    class MCPSchemaError(Exception):
        pass

    class MCPConfigError(Exception):
        pass

    def format_validation_error(error):
        return f"❌ 配置错误: {str(error)}"


def load_json(p: Path, default: Any, error_context: str = "") -> Any:
    if not p.exists():
        return default
    try:
        content = p.read_text(encoding="utf-8")
        if not content.strip():
            if error_context:
                print(f"⚠️ 警告: {error_context} - 文件为空: {p}", file=sys.stderr)
            return default
        return json.loads(content)
    except json.JSONDecodeError as e:
        if error_context:
            print(f"❌ {error_context} - JSON 解析错误: {p}", file=sys.stderr)
            print(f"   错误位置: 行 {e.lineno}, 列 {e.colno}", file=sys.stderr)
            if e.msg:
                print(f"   错误信息: {e.msg}", file=sys.stderr)
        return default
    except Exception as e:
        if error_context:
            print(f"❌ {error_context} - 读取文件失败: {p}", file=sys.stderr)
            print(f"   错误信息: {e}", file=sys.stderr)
        return default


def save_json(p: Path, obj: dict[str, Any]) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def backup(p: Path) -> Path | None:
    if not p.exists():
        return None
    b = p.with_name(p.name + ".backup")
    shutil.copy2(p, b)
    return b


def _is_macos() -> bool:
    v = os.environ.get("MCP_OS")
    if v:
        return v.lower() in ("darwin", "mac", "macos", "osx")
    return platform.system() == "Darwin"


def _vscode_user_path() -> Path:
    if _is_macos():
        return HOME / "Library" / "Application Support" / "Code" / "User" / "mcp.json"
    return HOME / ".config" / "Code" / "User" / "mcp.json"


def _vscode_insiders_path() -> Path:
    if _is_macos():
        return HOME / "Library" / "Application Support" / "Code - Insiders" / "User" / "mcp.json"
    return HOME / ".config" / "Code - Insiders" / "User" / "mcp.json"


def _json_keys(path: Path, pref_key: str = "mcpServers", error_context: str = "") -> set[str]:
    obj = load_json(path, {}, error_context or f"读取 {path.name} 配置")
    if isinstance(obj.get(pref_key), dict):
        return set(obj[pref_key].keys())
    if isinstance(obj.get("servers"), dict):
        return set(obj["servers"].keys())
    return set()


def strip_toml_mcp_servers_block(text: str) -> str:
    """移除 Codex config.toml 中我们写入的 MCP 段与所有 [mcp_servers.*] 段。"""
    pattern = (
        r"\n*# === MCP Servers 配置（由 MCP (?:Local Manager|Central) 生成）===\n"
        r"(?:.|\n)*?(?=\n?# ===|\Z)"
    )
    text = re.sub(
        pattern,
        "\n",
        text,
    )
    text = re.sub(r"(?ms)^\[mcp_servers\.[^\]]+\][\s\S]*?(?=^\[|\Z)", "", text)
    return text


def _codex_keys() -> set[str]:
    p = HOME / ".codex" / "config.toml"
    if not p.exists():
        return set()
    try:
        import tomllib

        conf = tomllib.loads(p.read_text(encoding="utf-8"))
        m = conf.get("mcp_servers", {}) or {}
        return {k for k in m.keys() if not k.endswith(".env")}
    except Exception:
        names = set()
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            m = re.match(r"^\[mcp_servers\.([^\]]+)\]$", line)
            if m:
                name = m.group(1)
                if not name.endswith(".env"):
                    names.add(name)
        return names


def _claude_registered() -> set[str]:
    """读取 Claude Code MCP 注册表中的 server 名称集合。

    - 当 scope=user 时，优先直接读取 ~/.claude.json 顶层 mcpServers（更快且不受 `claude mcp list` 变慢影响）。
    - 其它 scope 回退到 `claude mcp list` 解析输出。
    """

    scope = claude_registry_scope()
    if scope == "user":
        return claude_user_mcp_servers()

    try:
        t = float(os.environ.get("CLAUDE_LIST_TIMEOUT", "10"))
        out = subprocess.run(["claude", "mcp", "list"], capture_output=True, text=True, timeout=t)
        text = (out.stdout or "") + "\n" + (out.stderr or "")
        reg = set()
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("plugin:"):
                continue
            if ":" in line:
                reg.add(line.split(":", 1)[0].strip())
        return reg
    except Exception:
        return set()


def claude_registry_scope() -> str:
    """Claude MCP 注册表写入 scope。

    Claude Code 的 `claude mcp add/remove` 支持 scope：local/user/project。
    - user: 全局可用（推荐）
    - local/project: 与当前目录绑定

    通过环境变量 `MCP_CLAUDE_SCOPE` 覆盖；默认使用 user。
    """

    scope = (os.environ.get("MCP_CLAUDE_SCOPE") or "user").strip().lower()
    if scope in ("local", "user", "project"):
        return scope
    if scope:
        print(
            f"⚠️  MCP_CLAUDE_SCOPE={scope!r} 非法，已回退到 'user'",
            file=sys.stderr,
        )
    return "user"


def claude_user_mcp_servers() -> set[str]:
    """从 ~/.claude.json 顶层 mcpServers 读取 user scope 下的 server 名称集合。"""

    p = HOME / ".claude.json"
    obj = load_json(p, {}, "Claude user 配置读取")
    if isinstance(obj, dict) and isinstance(obj.get("mcpServers"), dict):
        return set(obj["mcpServers"].keys())
    return set()


def _print_client(
    label: str, present: set[str] | list[str], universe: set[str] | list[str]
) -> None:
    present = sorted(present)
    absent = sorted(set(universe) - set(present))
    print(f"\n[{label}]")
    print("  on : " + (", ".join(present) if present else "无"))
    print("  off: " + (", ".join(absent) if absent else "无"))


def _normalize_client(alias: str | None) -> str | None:
    if not alias:
        return None
    a = alias.strip().lower()
    mapping = {
        "claude": "claude-file",
        "claude-file": "claude-file",
        "claude-reg": "claude-reg",
        "codex": "codex",
        "gemini": "gemini",
        "iflow": "iflow",
        "droid": "droid",
        "cursor": "cursor",
        "vscode": "vscode-user",
        "vscode-user": "vscode-user",
        "vscode-insiders": "vscode-ins",
        "vscode-ins": "vscode-ins",
        "insiders": "vscode-ins",
    }
    return mapping.get(a)


def load_central_servers() -> tuple[dict[str, Any], dict[str, Any]]:
    validation_passed = False
    obj = {}
    if VALIDATION_AVAILABLE and CENTRAL.exists():
        try:
            obj = validate_mcp_servers_config(CENTRAL)
            validation_passed = True
        except (MCPValidationError, MCPSchemaError) as e:
            print(format_validation_error(e), file=sys.stderr)
            print("⚠️  警告: Schema 验证失败，使用基本 JSON 解析（功能可能受限）", file=sys.stderr)
            obj = load_json(CENTRAL, {}, "中央配置验证失败")
        except Exception as e:
            print(f"❌ 验证过程发生未知错误: {e}", file=sys.stderr)
            print("⚠️  警告: 使用基本 JSON 解析", file=sys.stderr)
            obj = load_json(CENTRAL, {}, "中央配置验证异常")
    else:
        obj = load_json(CENTRAL, {}, "中央配置加载")

    servers = obj.get("servers") or {}
    if not isinstance(servers, dict):
        print("❌ 错误: 'servers' 字段必须是对象格式", file=sys.stderr)
        servers = {}

    if VALIDATION_AVAILABLE and validation_passed:
        from mcp_validation import validate_server_config

        for server_name, server_info in servers.items():
            try:
                validate_server_config(server_name, server_info)
            except MCPValidationError as e:
                print(f"⚠️  服务器配置警告 - {server_name}: {e}", file=sys.stderr)

    return obj, servers


def list_servers() -> None:
    obj, servers = load_central_servers()
    rows = []
    for n, v in sorted(servers.items()):
        en = bool(v.get("enabled", True))
        cmd = v.get("command", "")
        rows.append((n, "on" if en else "off", cmd))
    print("中央清单（启用开关与命令路径）")
    print("name                        state  command")
    print("-" * 60)
    for n, st, cmd in rows:
        print(f"{n:26} {st:5}  {cmd}")


def split_enabled_servers(servers: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """按 central 的 enabled 字段拆分服务集合。

    - 未显式写 enabled 的条目视为 True
    - 返回 (enabled, disabled)
    """
    enabled: dict[str, Any] = {}
    disabled: dict[str, Any] = {}
    for name, info in (servers or {}).items():
        if bool((info or {}).get("enabled", True)):
            enabled[name] = info
        else:
            disabled[name] = info
    return enabled, disabled


def to_target_server_info(info: dict[str, Any], client: str | None = None) -> dict[str, Any]:
    """将 central 的 server 配置裁剪为"可写入目标端"的形态（去除元数据字段）。

    目标端通常只需要：command/args/env/timeout/url/headers。
    对于 Gemini 客户端，会额外移除 type 字段（因为 Gemini CLI 不支持）。

    支持 client_overrides 字段：当指定 client 时，会用对应的覆盖配置合并默认配置。
    """
    if not isinstance(info, dict):
        return {}

    # 应用 client_overrides（如果存在）
    overrides = info.get("client_overrides", {})
    if client and isinstance(overrides, dict) and client in overrides:
        override = overrides[client]
        if isinstance(override, dict):
            # 合并：override 中的字段覆盖默认值
            info = {**info, **override}

    out: dict[str, Any] = {}
    if "command" in info and info.get("command"):
        out["command"] = str(info["command"])

    args = info.get("args")
    if isinstance(args, list) and args:
        out["args"] = [str(x) for x in args]

    env = info.get("env")
    if isinstance(env, dict) and env:
        out["env"] = {str(k): str(v) for k, v in env.items() if v is not None}

    headers = info.get("headers")
    if isinstance(headers, dict) and headers:
        out["headers"] = {str(k): str(v) for k, v in headers.items() if v is not None}

    url = info.get("url")
    if url:
        out["url"] = str(url)

    def _map_type_for_client(server_type: object, target: str | None) -> str | None:
        """不同 MCP 客户端对 type 字段的取值不完全一致：

        - Cursor 文档示例使用 `local` 表示本地进程（stdio）。
        - Claude / VS Code 文档示例使用 `stdio`。
        """
        # 仅在 central 显式提供 type 时才做映射；否则保持“不写 type”（避免误把远端/SSE 配置写成 stdio/local）。
        if server_type is None:
            return None
        t = str(server_type).strip().lower()
        if not t:
            return None
        c = str(target or "").strip().lower()

        # Cursor：优先写 local；若 central 写了 stdio，也做兼容映射
        if c == "cursor":
            if t == "stdio":
                return "local"
            return t

        # Claude / VS Code：优先写 stdio；若 central 写了 local，也做兼容映射
        if c in ("claude", "claude-file", "claude-reg", "vscode-user", "vscode-insiders", "vscode-ins"):
            if t == "local":
                return "stdio"
            return t

        return t or None

    # Gemini CLI 和 iFlow CLI 不支持 type 字段
    if client not in ("gemini", "iflow"):
        mapped = _map_type_for_client(info.get("type"), client)
        if mapped:
            out["type"] = mapped

    timeout = info.get("timeout")
    if timeout is not None:
        try:
            t = int(timeout)
            if t >= 1:
                out["timeout"] = t
        except Exception:
            pass

    return out
