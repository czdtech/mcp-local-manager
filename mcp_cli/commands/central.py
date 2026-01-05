#!/usr/bin/env python3
"""mcp central 子命令：管理 ~/.mcp-central/config/mcp-servers.json（CRUD/模板/导入导出/校验/体检）。

特性：
- 所有写操作均支持 dry-run（args._dry_run 或 MCP_FORCE_DRY_RUN=1）与自动备份。
- 写入采用临时文件 + 原子替换，降低并发风险。
- 所有子命令支持 --json 输出（结构化结果），默认人类可读输出。
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from .. import utils as U


def _dry(args) -> bool:
    # 交互版不再支持 CLI dry-run 开关，统一在交互里做预览/确认
    return False


def _load_central_or_new() -> dict[str, Any]:
    if U.CENTRAL.exists():
        try:
            data = U.load_json(U.CENTRAL, {})
            if not isinstance(data, dict):
                data = {}
        except Exception:
            data = {}
    else:
        data = {}
    data.setdefault("version", "1.1.0")
    data.setdefault("description", "Central MCP Servers config")
    data.setdefault("servers", {})
    return data


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(content, encoding="utf-8")
    os.replace(tmp, path)


def _save_central(obj: dict[str, Any], *, dry: bool) -> None:
    # 写盘前强制校验（即使上层漏调 _validate，也不写入非法配置）
    ok, msg = _validate(obj)
    if not ok:
        print(f"❌ 校验失败: {msg}")
        raise ValueError(msg)
    try:
        if not dry:
            U.backup(U.CENTRAL)
            _atomic_write(U.CENTRAL, json.dumps(obj, ensure_ascii=False, indent=2))
    except Exception as e:
        print(f"❌ 保存失败: {e}")
        raise


def _validate(obj: dict[str, Any]) -> tuple[bool, str]:
    """校验“待写入”的 central 对象（内存态），而不是校验磁盘现有文件。"""
    try:
        data = json.loads(json.dumps(obj))
    except Exception as e:
        return False, f"配置无法序列化为 JSON: {e}"

    # 1) 基础内容校验（不依赖 jsonschema / mcp_validation），确保缺少依赖时也不会放过明显错误
    try:
        if not isinstance(data, dict):
            raise ValueError("配置必须是对象格式")
        for k in ("version", "description", "servers"):
            if k not in data:
                raise ValueError(f"缺少必需字段: '{k}'")
        if not isinstance(data.get("version"), str) or not str(data.get("version")).strip():
            raise ValueError("'version' 字段必须是非空字符串")
        if not isinstance(data.get("description"), str) or not str(data.get("description")).strip():
            raise ValueError("'description' 字段必须是非空字符串")
        if not isinstance(data.get("servers"), dict):
            raise ValueError("'servers' 字段必须是对象格式")
    except Exception as e:
        return False, str(e)

    # 2) 额外字段（additionalProperties=false）与关键字段类型校验（覆盖 schema 里的主要约束）
    allowed_top = {"version", "description", "servers"}
    allowed_server = {
        "enabled",
        "type",
        "command",
        "args",
        "env",
        "url",
        "timeout",
        "headers",
        "source",
        "client_overrides",
    }
    extra_top = set(data.keys()) - allowed_top
    if extra_top:
        return False, f"不允许的顶层字段: {sorted(extra_top)}"
    servers: dict[str, Any] = data.get("servers") or {}
    for name, info in servers.items():
        if not isinstance(info, dict):
            return False, f"服务器 '{name}' 配置必须是对象格式"
        extra = set(info.keys()) - allowed_server
        if extra:
            return False, f"服务器 '{name}' 包含不支持的字段: {sorted(extra)}"

        cmd = info.get("command")
        if not isinstance(cmd, str) or not cmd.strip():
            return False, f"服务器 '{name}' 缺少必需字段: 'command'"

        if "enabled" in info and not isinstance(info.get("enabled"), bool):
            return False, f"服务器 '{name}' 的 'enabled' 必须是布尔值"

        if "type" in info:
            v = info.get("type")
            if not isinstance(v, str) or not v.strip():
                return False, f"服务器 '{name}' 的 'type' 必须是非空字符串"

        if "args" in info:
            args = info.get("args")
            if not isinstance(args, list):
                return False, f"服务器 '{name}' 的 'args' 必须是数组"
            for i, arg in enumerate(args):
                if not isinstance(arg, str):
                    return False, f"服务器 '{name}' 的 'args[{i}]' 必须是字符串"

        if "env" in info:
            env = info.get("env")
            if not isinstance(env, dict):
                return False, f"服务器 '{name}' 的 'env' 必须是对象"
            for k, v in env.items():
                if not isinstance(v, str):
                    return False, f"服务器 '{name}' 的环境变量 '{k}' 必须是字符串"

        if "url" in info:
            url = info.get("url")
            if not isinstance(url, str) or not url.strip():
                return False, f"服务器 '{name}' 的 'url' 必须是非空字符串"

        if "timeout" in info:
            timeout = info.get("timeout")
            if isinstance(timeout, bool) or not isinstance(timeout, int):
                return False, f"服务器 '{name}' 的 'timeout' 必须是整数（秒）"
            if timeout < 1 or timeout > 3600:
                return False, f"服务器 '{name}' 的 'timeout' 超出范围（1-3600）: {timeout}"

        if "headers" in info:
            headers = info.get("headers")
            if not isinstance(headers, dict):
                return False, f"服务器 '{name}' 的 'headers' 必须是对象"
            for k, v in headers.items():
                if not isinstance(v, str):
                    return False, f"服务器 '{name}' 的 HTTP 头 '{k}' 必须是字符串"

        if "source" in info:
            source = info.get("source")
            if not isinstance(source, str) or not source.strip():
                return False, f"服务器 '{name}' 的 'source' 必须是非空字符串"

        if "client_overrides" in info:
            overrides = info.get("client_overrides")
            if not isinstance(overrides, dict):
                return False, f"服务器 '{name}' 的 'client_overrides' 必须是对象"
            for client, override in overrides.items():
                if not isinstance(override, dict):
                    return False, f"服务器 '{name}' 的 client_overrides.{client} 必须是对象"
                if "command" in override:
                    v = override.get("command")
                    if not isinstance(v, str) or not v.strip():
                        return False, f"服务器 '{name}' 的 client_overrides.{client}.command 必须是非空字符串"
                if "args" in override:
                    args = override.get("args")
                    if not isinstance(args, list):
                        return False, f"服务器 '{name}' 的 client_overrides.{client}.args 必须是数组"
                    for i, arg in enumerate(args):
                        if not isinstance(arg, str):
                            return False, f"服务器 '{name}' 的 client_overrides.{client}.args[{i}] 必须是字符串"
                if "env" in override:
                    env = override.get("env")
                    if not isinstance(env, dict):
                        return False, f"服务器 '{name}' 的 client_overrides.{client}.env 必须是对象"
                    for k, v in env.items():
                        if not isinstance(v, str):
                            return False, (
                                f"服务器 '{name}' 的 client_overrides.{client} 环境变量 '{k}' 必须是字符串"
                            )

    # 3) 若 jsonschema 可用，则执行完整 schema 校验（更精确的类型/范围校验）
    # 注意：mcp_validation 在 CLI 场景可用（bin 目录），但库/测试环境不一定可 import。
    schema_path = Path(__file__).resolve().parents[2] / "config" / "mcp-servers.schema.json"
    if schema_path.exists():
        try:
            import jsonschema
        except ImportError:
            # jsonschema 不可用：上面的手工校验已覆盖 schema 的关键约束，避免“静默跳过导致写入脏配置”。
            pass
        else:
            try:
                schema = json.loads(schema_path.read_text(encoding="utf-8"))
                jsonschema.validate(instance=data, schema=schema)
            except Exception as e:
                try:
                    from mcp_validation import format_validation_error

                    return False, format_validation_error(e)
                except Exception:
                    return False, str(e)

    return True, "ok"


def _parse_kv_list(items: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for it in items or []:
        if "=" not in it:
            continue
        k, v = it.split("=", 1)
        out[k] = v
    return out


def _print_or_json(obj: Any, use_json: bool) -> None:
    if use_json:
        print(json.dumps(obj, ensure_ascii=False, indent=2))
    else:
        if isinstance(obj, (dict, list)):
            print(json.dumps(obj, ensure_ascii=False, indent=2))
        else:
            print(obj)


def _cmd_list(args) -> int:
    use_json = bool(args.json)
    data = _load_central_or_new()
    servers: dict[str, Any] = data.get("servers", {})
    if use_json:
        out = [
            {
                "name": name,
                "enabled": bool(info.get("enabled", True)),
                "type": info.get("type") or "",
                "command": info.get("command") or "",
            }
            for name, info in sorted(servers.items())
        ]
        _print_or_json({"servers": out, "total": len(out)}, True)
        return 0
    print(f"共 {len(servers)} 个服务：")
    for name, info in sorted(servers.items()):
        en = "on" if bool(info.get("enabled", True)) else "off"
        cmd = info.get("command", "")
        print(f"- {name:24} [{en}]  {cmd}")
    return 0


def _cmd_show(args) -> int:
    use_json = bool(args.json)
    name = args.name
    data = _load_central_or_new()
    sv = data.get("servers", {})
    if name not in sv:
        print(f"❌ 未找到: {name}")
        return 2
    _print_or_json({name: sv[name]}, use_json)
    return 0


def _cmd_add(args) -> int:
    dry = _dry(args)
    use_json = bool(args.json)
    name = args.name
    data = _load_central_or_new()
    sv = data.setdefault("servers", {})
    if name in sv:
        print(f"❌ 已存在: {name}")
        return 2
    entry: dict[str, Any] = {}
    entry["command"] = getattr(args, "command", None)
    if getattr(args, "args", None):
        entry["args"] = args.args
    if getattr(args, "env", None):
        entry["env"] = _parse_kv_list(args.env)
    if getattr(args, "headers", None):
        entry["headers"] = _parse_kv_list(args.headers)
    if getattr(args, "type", None):
        entry["type"] = args.type
    if getattr(args, "url", None):
        entry["url"] = args.url
    if getattr(args, "enabled", None) is not None:
        entry["enabled"] = bool(args.enabled)
    sv[name] = entry
    ok, msg = _validate(data)
    if not ok:
        print(f"❌ 校验失败: {msg}")
        return 3
    if dry:
        print("[DRY-RUN] 将新增服务:")
        _print_or_json({name: entry}, use_json)
        return 0
    _save_central(data, dry=False)
    _print_or_json({"added": name, "entry": entry}, use_json)
    return 0


def _cmd_update(args) -> int:
    dry = _dry(args)
    use_json = bool(args.json)
    name = args.name
    data = _load_central_or_new()
    sv = data.setdefault("servers", {})
    if name not in sv:
        print(f"❌ 未找到: {name}")
        return 2
    entry: dict[str, Any] = json.loads(json.dumps(sv[name]))  # deep copy
    before = json.loads(json.dumps(entry))

    if getattr(args, "rename", None):
        newn = args.rename
        if newn in sv and newn != name:
            print(f"❌ rename 冲突: 目标已存在 {newn}")
            return 2
        sv.pop(name)
        name = newn
        sv[name] = entry

    if getattr(args, "command", None):
        entry["command"] = args.command
    if getattr(args, "type", None):
        entry["type"] = args.type
    if getattr(args, "url", None):
        entry["url"] = args.url
    if getattr(args, "enabled", None) is not None:
        entry["enabled"] = bool(args.enabled)
    # args 操作
    arr = list(entry.get("args", []))
    if getattr(args, "prepend_arg", None):
        arr = args.prepend_arg + arr
    if getattr(args, "append_arg", None):
        arr = arr + args.append_arg
    if getattr(args, "remove_arg", None):
        arr = [x for x in arr if x not in set(args.remove_arg)]
    if arr:
        entry["args"] = arr
    elif (args.prepend_arg or args.append_arg or args.remove_arg) and not arr:
        entry.pop("args", None)
    # env 操作
    env = dict(entry.get("env", {}))
    if getattr(args, "set_env", None):
        env.update(_parse_kv_list(args.set_env))
    if getattr(args, "unset_env", None):
        for k in args.unset_env:
            env.pop(k, None)
    if env:
        entry["env"] = env
    elif args.set_env or args.unset_env:
        entry.pop("env", None)
    # headers
    headers = dict(entry.get("headers", {}))
    if getattr(args, "set_header", None):
        headers.update(_parse_kv_list(args.set_header))
    if getattr(args, "unset_header", None):
        for k in args.unset_header:
            headers.pop(k, None)
    if headers:
        entry["headers"] = headers
    elif args.set_header or args.unset_header:
        entry.pop("headers", None)

    sv[name] = entry
    ok, msg = _validate(data)
    if not ok:
        print(f"❌ 校验失败: {msg}")
        return 3
    if dry:
        print("[DRY-RUN] 将更新服务:")
        _print_or_json({"name": name, "before": before, "after": entry}, use_json)
        return 0
    _save_central(data, dry=False)
    _print_or_json({"updated": name, "after": entry}, use_json)
    return 0


def _cmd_remove(args) -> int:
    dry = _dry(args)
    use_json = bool(args.json)
    name = args.name
    data = _load_central_or_new()
    sv = data.setdefault("servers", {})
    if name not in sv:
        print(f"❌ 未找到: {name}")
        return 2
    old = sv.pop(name)
    ok, msg = _validate(data)
    if not ok:
        print(f"❌ 校验失败: {msg}")
        return 3
    if dry:
        print("[DRY-RUN] 将删除服务:")
        _print_or_json({name: old}, use_json)
        return 0
    _save_central(data, dry=False)
    _print_or_json({"removed": name}, use_json)
    return 0


def _cmd_toggle(args, enable: bool) -> int:
    dry = _dry(args)
    use_json = bool(args.json)
    name = args.name
    data = _load_central_or_new()
    sv = data.setdefault("servers", {})
    if name not in sv:
        print(f"❌ 未找到: {name}")
        return 2
    before = bool(sv[name].get("enabled", True))
    sv[name]["enabled"] = enable
    if dry:
        print(f"[DRY-RUN] 将{'启用' if enable else '禁用'} {name}")
        return 0
    _save_central(data, dry=False)
    _print_or_json({"name": name, "enabled": enable, "was": before}, use_json)
    return 0


def _cmd_export(args) -> int:
    use_json = bool(args.json)
    data = _load_central_or_new()
    if args.file in ("-", None):
        _print_or_json(data, use_json)
        return 0
    path = Path(args.file).expanduser()
    content = json.dumps(data, ensure_ascii=False, indent=2)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    print(f"[OK] 已导出到: {path}")
    return 0


def _merge_servers(
    dst: dict[str, Any], src: dict[str, Any], prefer_incoming: bool
) -> dict[str, Any]:
    out = dict(dst)
    for k, v in src.items():
        if k not in out:
            out[k] = v
        else:
            out[k] = v if prefer_incoming else out[k]
    return out


def _cmd_import(args) -> int:
    dry = _dry(args)
    src = Path(args.file).expanduser()
    if not src.exists():
        print(f"❌ 文件不存在: {src}")
        return 2
    incoming = U.load_json(src, {})
    if not isinstance(incoming, dict):
        print("❌ 导入文件不是 JSON 对象")
        return 2
    data = _load_central_or_new()
    if args.replace:
        data = incoming
    else:
        # merge
        prefer_incoming = bool(args.prefer_incoming)
        dst_servers = data.get("servers") or {}
        src_servers = incoming.get("servers") or {}
        data["servers"] = _merge_servers(dst_servers, src_servers, prefer_incoming)
        # 版本/描述沿用现有
        data.setdefault("version", incoming.get("version", data.get("version", "1.1.0")))
        data.setdefault(
            "description",
            incoming.get("description", data.get("description", "Central MCP Servers config")),
        )
    ok, msg = _validate(data)
    if not ok:
        print(f"❌ 校验失败: {msg}")
        return 3
    if dry:
        print("[DRY-RUN] 将导入/合并 central 配置")
        return 0
    _save_central(data, dry=False)
    print("[OK] 导入完成")
    return 0


_BUILTIN_TEMPLATES: dict[str, dict[str, Any]] = {
    "filesystem": {"command": "npx", "args": ["-y", "mcp-server-filesystem@latest", "~/work"]},
    "sequential-thinking": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-sequential-thinking@latest"],
    },
    "playwright": {"command": "npx", "args": ["-y", "@playwright/mcp@latest", "--headless"]},
    "serena": {
        "command": "~/.local/bin/serena",
        "args": ["start-mcp-server", "--context", "desktop-app"],
    },
    "context7": {"command": "npx", "args": ["-y", "@upstash/context7-mcp@latest"]},
    "task-master-ai": {
        "command": "npx",
        "args": ["-y", "task-master-ai@latest"],
        "timeout": 300,
        "env": {"TASK_MASTER_TOOLS": "standard"},
    },
    "chrome-devtools": {"command": "npx", "args": ["-y", "chrome-devtools-mcp@latest"]},
    "custom-npx": {"command": "npx", "args": ["-y", "<package>@latest"]},
    "frontend-automation": {
        "command": "npx",
        "args": ["-y", "@playwright/mcp@latest", "--headless"],
        "env": {"PLAYWRIGHT_BROWSERS_PATH": "0"},
    },
    "doc-search": {
        "command": "npx",
        "args": ["-y", "mcp-server-filesystem@latest", "~/work", "~/.mcp-central"],
    },
    "task-suite": {
        "command": "npx",
        "args": ["-y", "task-master-ai@latest"],
        "timeout": 300,
        "env": {"TASK_MASTER_TOOLS": "standard"},
    },
}

_TPL_DESC = {
    "frontend-automation": "前端自动化：@playwright/mcp headless + 预设浏览器路径",
    "doc-search": "文档/本地检索：filesystem 指向 ~/work 与 ~/.mcp-central",
    "task-suite": "任务管理组合：task-master-ai（timeout 300 + standard 工具集）",
    "task-master-ai": "官方推荐：timeout 300 + TASK_MASTER_TOOLS=standard",
    "filesystem": "最小文件系统服务",
    "playwright": "浏览器自动化（headless）",
    "chrome-devtools": "DevTools 浏览器控制",
    "context7": "Context7 文档检索",
}


def _cmd_template(args) -> int:
    dry = _dry(args)
    use_json = bool(args.json)
    tpl = args.template
    name = args.name
    data = _load_central_or_new()
    sv = data.setdefault("servers", {})
    if name in sv:
        print(f"❌ 已存在: {name}")
        return 2
    if args.from_path:
        src_path = Path(args.from_path).expanduser()
        tpl_data = U.load_json(src_path, {})
        if not isinstance(tpl_data, dict):
            print("❌ 模板文件不是对象")
            return 2
        entry = tpl_data
    else:
        if tpl not in _BUILTIN_TEMPLATES:
            print(f"❌ 未知模板: {tpl}")
            return 2
        entry = json.loads(json.dumps(_BUILTIN_TEMPLATES[tpl]))
    # 覆盖参数
    if args.command:
        entry["command"] = args.command
    if args.args:
        entry["args"] = args.args
    if args.env:
        entry["env"] = _parse_kv_list(args.env)
    sv[name] = entry
    ok, msg = _validate(data)
    if not ok:
        print(f"❌ 校验失败: {msg}")
        return 3
    if dry:
        print("[DRY-RUN] 将基于模板创建:")
        _print_or_json({name: entry}, use_json)
        return 0
    _save_central(data, dry=False)
    _print_or_json({"created": name, "entry": entry}, use_json)
    return 0


def _cmd_dup(args) -> int:
    dry = _dry(args)
    use_json = bool(args.json)
    old = args.src
    new = args.dest
    data = _load_central_or_new()
    sv = data.setdefault("servers", {})
    if old not in sv:
        print(f"❌ 未找到: {old}")
        return 2
    if new in sv:
        print(f"❌ 目标已存在: {new}")
        return 2
    sv[new] = json.loads(json.dumps(sv[old]))
    if dry:
        print("[DRY-RUN] 将复制条目")
        _print_or_json({"from": old, "to": new}, use_json)
        return 0
    _save_central(data, dry=False)
    _print_or_json({"duplicated": {"from": old, "to": new}}, use_json)
    return 0


def _cmd_validate(args) -> int:
    use_json = bool(args.json)
    data = _load_central_or_new()
    ok, msg = _validate(data)
    if use_json:
        _print_or_json({"ok": ok, "message": msg}, True)
    else:
        print("✅ 通过" if ok else f"❌ 失败: {msg}")
    return 0 if ok else 1


_URL_RE = re.compile(r"^https?://[A-Za-z0-9_.:-]+(/.*)?$")


def build_doctor_report(data: dict[str, Any]) -> dict[str, Any]:
    """对 central 配置做只读体检，返回结构化报告（可被 mcp doctor 复用）。"""
    servers: dict[str, Any] = data.get("servers", {})
    total = len(servers)
    issues: list[str] = []
    per: dict[str, Any] = {}

    def _which(cmd: str) -> bool:
        from shutil import which

        if os.path.isabs(cmd):
            return Path(cmd).expanduser().exists()
        return which(cmd) is not None

    for name, info in servers.items():
        if not bool((info or {}).get("enabled", True)):
            per[name] = {
                "status": "skipped",
                "issues": [],
                "suggestions": ["已在 central 禁用（enabled:false）"],
            }
            continue
        c_issues: list[str] = []
        suggestions: list[str] = []
        cmd = info.get("command")
        if not cmd or not isinstance(cmd, str):
            c_issues.append("缺少 command 或类型错误")
        else:
            if cmd == "npx":
                if not _which("npx"):
                    c_issues.append("npx 不可用")
                    suggestions.append(
                        "请安装 node/npm 或使用全局二进制：npm i -g <pkg>@latest 并更新 command"
                    )
            else:
                if not _which(cmd):
                    c_issues.append(f"命令未找到: {cmd}")
                    suggestions.append(f"请确保 {cmd} 在 PATH 中，或改为 npx -y <pkg>@latest")
        url = info.get("url")
        if url and not _URL_RE.match(str(url)):
            c_issues.append("url 格式不合法")
        # task-master-ai 专项体检：timeout 与 TASK_MASTER_TOOLS 建议值
        if name == "task-master-ai":
            timeout = info.get("timeout")
            try:
                timeout_val = int(timeout) if timeout is not None else None
            except Exception:
                timeout_val = None
            if timeout_val is None:
                c_issues.append("task-master-ai 未配置 timeout（建议 >= 300 秒，例如 300/600）")
                suggestions.append(
                    "操作示例: mcp central update task-master-ai --json（编辑输出或文件，"
                    "将 timeout 设置为 300）"
                )
            elif timeout_val < 300:
                c_issues.append(f"task-master-ai timeout 过小: {timeout_val}（建议至少 300）")
                suggestions.append(
                    "操作示例: mcp central update task-master-ai --json（编辑输出或文件，"
                    "将 timeout 调整为 300/600）"
                )

            env = info.get("env") or {}
            tools_mode = str(env.get("TASK_MASTER_TOOLS", "")).strip()
            if not tools_mode:
                c_issues.append(
                    "task-master-ai 未设置 env.TASK_MASTER_TOOLS（建议 standard，"
                    "或按需 core/lean/自定义列表）"
                )
                suggestions.append(
                    "示例: mcp central update task-master-ai --set-env TASK_MASTER_TOOLS=standard"
                )
            elif tools_mode.lower() == "all":
                c_issues.append(
                    "task-master-ai 使用 TASK_MASTER_TOOLS=all，可能导致加载过慢"
                    "（建议改为 standard/core/lean）"
                )
                suggestions.append(
                    "示例: mcp central update task-master-ai --set-env TASK_MASTER_TOOLS=standard"
                )

        per[name] = {
            "status": "passed" if not c_issues else "failed",
            "issues": c_issues,
            "suggestions": suggestions,
        }
        issues += [f"{name}: {x}" for x in c_issues]

    status = "passed" if not issues else "failed"
    return {"status": status, "total_servers": total, "issues": issues, "servers": per}


def _cmd_doctor(args) -> int:
    use_json = bool(args.json)
    data = _load_central_or_new()
    out = build_doctor_report(data)
    _print_or_json(out, use_json)
    return 0 if out.get("status") == "passed" else 1


def run(args) -> int:
    # 交互增强：当子命令缺少必要参数或显式 --interactive 时，进入交互模式
    def _choose_server(prompt: str, allow_new: bool = False) -> str | None:
        data = _load_central_or_new()
        names = sorted((data.get("servers") or {}).keys())
        if allow_new:
            print("0) 新建名称…")
        for i, n in enumerate(names, start=1):
            print(f"{i}) {n}")
        s = input(f"{prompt} 输入编号: ").strip()
        if s == "0" and allow_new:
            return input("输入新名称: ").strip() or None
        if s.isdigit():
            idx = int(s)
            if 1 <= idx <= len(names):
                return names[idx - 1]
        return None

    cmd = getattr(args, "central_cmd", None)
    if cmd is None:
        # 简化交互菜单（新手模式）：列出、模板、校验/体检，其他用简短入口
        while True:
            print("\nCentral 管理（简化交互）:")
            print("  1) 列表/查看")
            print("  2) 新增/更新/启用/禁用")
            print("  3) 模板创建")
            print("  4) 导入/导出")
            print("  5) 校验/体检")
            print("  0) 退出")
            sel = input("选择: ").strip() or "0"
            if sel == "0":
                return 0
            if sel == "1":
                _cmd_list(type("o", (object,), {"json": False}))
                n = input("查看某个服务? 输入名称或回车跳过: ").strip()
                if n:
                    _cmd_show(type("o", (object,), {"name": n, "json": False}))
            elif sel == "2":
                name = _choose_server("选择服务 (或 0 新建)", allow_new=True)
                if not name:
                    continue
                op = (
                    input("操作: [u]pdate/[e]nable/[d]isable/[r]emove (回车=update): ")
                    .strip()
                    .lower()
                    or "u"
                )
                if op.startswith("e"):
                    _cmd_toggle(type("o", (object,), {"name": name, "json": False}), True)
                elif op.startswith("d"):
                    _cmd_toggle(type("o", (object,), {"name": name, "json": False}), False)
                elif op.startswith("r"):
                    _cmd_remove(type("o", (object,), {"name": name, "json": False}))
                else:
                    run(
                        type(
                            "args",
                            (object,),
                            {
                                "central_cmd": "update",
                                "interactive": True,
                                "json": False,
                                "name": name,
                            },
                        )
                    )
            elif sel == "3":
                run(
                    type(
                        "args",
                        (object,),
                        {"central_cmd": "template", "interactive": True, "json": False},
                    )
                )
            elif sel == "4":
                io = input("导入(i) / 导出(o): ").strip().lower()
                if io.startswith("i"):
                    run(
                        type(
                            "args",
                            (object,),
                            {"central_cmd": "import", "interactive": True, "json": False},
                        )
                    )
                else:
                    run(
                        type(
                            "args",
                            (object,),
                            {"central_cmd": "export", "interactive": True, "json": False},
                        )
                    )
            elif sel == "5":
                _cmd_validate(type("o", (object,), {"json": False}))
                _cmd_doctor(type("o", (object,), {"json": False}))
            else:
                print("无效选择")
    if cmd == "list":
        return _cmd_list(args)
    if cmd == "show":
        if getattr(args, "interactive", False) or not getattr(args, "name", None):
            name = _choose_server("选择要查看的服务")
            if not name:
                print("已取消")
                return 0
            args.name = name
        return _cmd_show(args)
    if cmd == "add":
        if (
            getattr(args, "interactive", False)
            or not getattr(args, "name", None)
            or not getattr(args, "command", None)
        ):
            name = getattr(args, "name", None) or input("新服务名称: ").strip()
            args.name = name
            if not getattr(args, "command", None):
                args.command = input("command (默认 npx): ").strip() or "npx"
            if not getattr(args, "args", None):
                raw = input("args（以空格分隔，可留空）: ").strip()
                args.args = raw.split() if raw else []
            if getattr(args, "env", None) is None:
                raw = input("env（形如 KEY=VAL 用空格分隔，可留空）: ").strip()
                args.env = raw.split() if raw else []
            if getattr(args, "enabled", None) is None:
                yn = input("是否启用? [Y/n]: ").strip().lower() or "y"
                args.enabled = yn.startswith("y")
        return _cmd_add(args)
    if cmd == "update":
        if getattr(args, "interactive", False) or not getattr(args, "name", None):
            name = _choose_server("选择要更新的服务")
            if not name:
                print("已取消")
                return 0
            args.name = name
        return _cmd_update(args)
    if cmd == "remove":
        if getattr(args, "interactive", False) or not getattr(args, "name", None):
            name = _choose_server("选择要删除的服务")
            if not name:
                print("已取消")
                return 0
            args.name = name
        return _cmd_remove(args)
    if cmd == "enable":
        if getattr(args, "interactive", False) or not getattr(args, "name", None):
            name = _choose_server("选择要启用的服务")
            if not name:
                print("已取消")
                return 0
            args.name = name
        return _cmd_toggle(args, True)
    if cmd == "disable":
        if getattr(args, "interactive", False) or not getattr(args, "name", None):
            name = _choose_server("选择要禁用的服务")
            if not name:
                print("已取消")
                return 0
            args.name = name
        return _cmd_toggle(args, False)
    if cmd == "export":
        if getattr(args, "interactive", False) and not getattr(args, "file", None):
            f = input("导出文件路径（留空输出到 stdout）: ").strip()
            args.file = f if f else None
        return _cmd_export(args)
    if cmd == "import":
        if getattr(args, "interactive", False) and not getattr(args, "file", None):
            f = input("导入文件路径: ").strip()
            args.file = f
            mode = input("模式: [m]erge / [r]eplace? ").strip().lower() or "m"
            args.replace = mode.startswith("r")
            pref = input("冲突偏好: [e]xisting / [i]ncoming? ").strip().lower() or "e"
            args.prefer_incoming = pref.startswith("i")
        return _cmd_import(args)
    if cmd == "template":
        if (
            getattr(args, "interactive", False)
            or not getattr(args, "template", None)
            or not getattr(args, "name", None)
        ):
            print("可选模板:")
            for i, k in enumerate(sorted(_BUILTIN_TEMPLATES.keys()), start=1):
                desc = _TPL_DESC.get(k, "")
                extra = f" - {desc}" if desc else ""
                print(f"  {i}) {k}{extra}")
            t = input("选择模板编号（或输入名称）: ").strip()
            keys = sorted(_BUILTIN_TEMPLATES.keys())
            if t.isdigit():
                idx = int(t)
                if 1 <= idx <= len(keys):
                    args.template = keys[idx - 1]
            if not getattr(args, "template", None):
                args.template = t or "custom-npx"
            if not getattr(args, "name", None):
                args.name = input("新服务名称: ").strip()
            if not getattr(args, "args", None):
                raw = input("模板 args（空格分隔，可留空）: ").strip()
                args.args = raw.split() if raw else []
        return _cmd_template(args)
    if cmd == "dup":
        if getattr(args, "interactive", False) or (
            not getattr(args, "src", None) or not getattr(args, "dest", None)
        ):
            src = _choose_server("选择要复制的服务")
            if not src:
                print("已取消")
                return 0
            args.src = src
            if not getattr(args, "dest", None):
                args.dest = input("输入新名称: ").strip()
        return _cmd_dup(args)
    if cmd == "validate":
        return _cmd_validate(args)
    if cmd == "doctor":
        return _cmd_doctor(args)
    print("❌ 未知 central 子命令")
    return 2
