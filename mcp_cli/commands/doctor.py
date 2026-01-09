#!/usr/bin/env python3
"""doctor 子命令：聚合诊断（central + 目标端漂移 + 下一步建议）。

定位：
- 面向普通用户的一条命令：告诉你“现在到底哪里不对、下一步怎么做”。
- 默认只做本地只读检查（不联网）；尽量不依赖外部 CLI 是否已安装。
"""

from __future__ import annotations

import json
from pathlib import Path

from .. import utils as U
from . import central as CENTRAL


def _normalize_targets(raw_clients: list[str] | None) -> list[str] | None:
    if not raw_clients:
        return None

    # 展开别名；claude 默认包含 file+registry
    alias_map: dict[str, list[str]] = {
        "claude": ["claude-file", "claude-reg"],
        "claude-file": ["claude-file"],
        "claude-reg": ["claude-reg"],
        "codex": ["codex"],
        "gemini": ["gemini"],
        "iflow": ["iflow"],
        "droid": ["droid"],
        "cursor": ["cursor"],
        "vscode": ["vscode-user"],
        "vscode-user": ["vscode-user"],
        "vscode-insiders": ["vscode-insiders"],
        "vscode-ins": ["vscode-insiders"],
        "insiders": ["vscode-insiders"],
    }

    out: list[str] = []
    unknown: list[str] = []
    for c in raw_clients:
        if not c:
            continue
        key = alias_map.get(str(c).strip().lower())
        if not key:
            unknown.append(str(c))
            continue
        for v in key:
            if v not in out:
                out.append(v)

    if unknown:
        print(f"[WARN] 已忽略未识别的 client: {', '.join(unknown)}")
    return out or None


def _get_present_keys(target: str) -> tuple[set[str], Path | None]:
    if target == "claude-file":
        p = U.HOME / ".claude" / "settings.json"
        return U._json_keys(p, "mcpServers", "Claude配置读取"), p
    if target == "claude-reg":
        return U._claude_registered(), None
    if target == "codex":
        p = U.HOME / ".codex" / "config.toml"
        return U._codex_keys(), p
    if target == "gemini":
        p = U.HOME / ".gemini" / "settings.json"
        return U._json_keys(p, "mcpServers", "Gemini配置读取"), p
    if target == "iflow":
        p = U.HOME / ".iflow" / "settings.json"
        return U._json_keys(p, "mcpServers", "iFlow配置读取"), p
    if target == "droid":
        p = U.HOME / ".factory" / "mcp.json"
        return U._json_keys(p, "mcpServers", "Droid配置读取"), p
    if target == "cursor":
        p = U.HOME / ".cursor" / "mcp.json"
        return U._json_keys(p, "mcpServers", "Cursor配置读取"), p
    if target == "vscode-user":
        p = U._vscode_user_path()
        return U._json_keys(p, "servers", "VS Code配置读取"), p
    if target == "vscode-insiders":
        p = U._vscode_insiders_path()
        return U._json_keys(p, "servers", "VS Code Insiders配置读取"), p
    raise ValueError(f"未知 target: {target}")


def _make_suggested_onboard_preset(target: str) -> str:
    # 与 onboard 的默认一致（不强依赖 onboard 模块）
    mapping = {
        "cursor": "cursor-minimal",
        "claude-file": "claude-basic",
        "claude-reg": "claude-basic",
        "vscode-user": "vscode-user-basic",
        "vscode-insiders": "vscode-user-basic",
        "codex": "task-suite",
        "gemini": "task-suite",
        "iflow": "task-suite",
        "droid": "task-suite",
    }
    return mapping.get(target, "task-suite")


def _claude_project_overrides() -> tuple[dict[str, list[str]], Path]:
    """读取 ~/.claude.json projects.*.mcpServers（Claude local scope / 按目录配置）。"""
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


def run(args) -> int:
    use_json = bool(getattr(args, "json", False))
    verbose = bool(getattr(args, "verbose", False))
    targets = _normalize_targets(getattr(args, "client", None))

    all_targets: list[tuple[str, str]] = [
        ("cursor", "Cursor"),
        ("claude-file", "Claude(file)"),
        ("claude-reg", "Claude(register)"),
        ("codex", "Codex"),
        ("gemini", "Gemini"),
        ("iflow", "iFlow"),
        ("droid", "Droid"),
        ("vscode-user", "VS Code(User)"),
        ("vscode-insiders", "VS Code(Insiders)"),
    ]

    # 1) central 基础状态
    central_path = U.CENTRAL
    central_exists = central_path.exists()
    central_data = CENTRAL._load_central_or_new()  # noqa: SLF001

    ok, msg = CENTRAL._validate(central_data)  # noqa: SLF001
    central_doctor = CENTRAL.build_doctor_report(central_data)

    servers_all = central_data.get("servers") if isinstance(central_data, dict) else {}
    if not isinstance(servers_all, dict):
        servers_all = {}
    enabled, disabled = U.split_enabled_servers(servers_all)
    enabled_names = set(enabled.keys())
    disabled_names = set(disabled.keys())
    all_names = set(servers_all.keys())

    claude_overrides, claude_overrides_path = _claude_project_overrides()

    # 2) 目标端漂移（只在“目标端已配置的条目”里找 unknown/disabled）
    target_reports: dict[str, dict] = {}
    worst = "passed"

    def _bump(w: str, s: str) -> str:
        rank = {"passed": 0, "warn": 1, "failed": 2}
        return s if rank.get(s, 0) > rank.get(w, 0) else w

    for key, label in all_targets:
        if targets and key not in targets:
            continue
        try:
            present, path = _get_present_keys(key)
        except Exception as e:
            worst = _bump(worst, "warn")
            target_reports[key] = {"label": label, "status": "warn", "error": str(e)}
            continue

        unknown = sorted(present - all_names)
        disabled_present = sorted(present & disabled_names)

        status = "passed"
        notes: list[str] = []
        suggestions: list[str] = []

        # 没落地：不算问题，给出 onboarding 建议（尤其当用户显式指定该 client）
        if not present and key != "claude-reg":
            status = "passed"
            notes.append("未检测到已落地的 MCP（可忽略）")
            if targets:
                preset = _make_suggested_onboard_preset(key)
                onboard_client = "claude" if key in ("claude-file", "claude-reg") else key
                suggestions.append(
                    "一键上手: mcp onboard --client "
                    + onboard_client
                    + " --preset "
                    + preset
                    + " --yes"
                )

        if unknown:
            status = "warn"
            notes.append("目标端包含 central 未收录的条目: " + ", ".join(unknown))
            clear_client = key
            if key in ("claude-file", "claude-reg"):
                clear_client = "claude"
            suggestions.append(
                f"建议：mcp clear --client {clear_client} --dry-run 先预览，再决定清理/重下发"
            )

        if disabled_present:
            status = "warn"
            notes.append("目标端仍配置了 central 已禁用的条目: " + ", ".join(disabled_present))
            suggestions.append(
                "建议：mcp central enable <name>，或重新 mcp onboard/mcp run 下发覆盖"
            )

        if key == "claude-reg" and claude_overrides:
            status = "warn" if status == "passed" else status
            notes.append(
                f"检测到 Claude local scope（按目录）配置: {claude_overrides_path} "
                f"projects.*.mcpServers 非空（{len(claude_overrides)} 个目录）"
            )
            notes.append(
                "说明：这是 Claude 的 local scope（默认 scope）配置；"
                "仅当你期望纯 user scope（全局）时才需要清理。"
            )
            if verbose:
                for proj, servers in list(claude_overrides.items())[:3]:
                    notes.append(f"override[{proj}]=" + ", ".join(servers))
                if len(claude_overrides) > 3:
                    notes.append(f"… 还有 {len(claude_overrides) - 3} 个目录")
            suggestions.append(
                "如需清理 local scope（按目录）覆盖："
                "请手动删除 ~/.claude.json 中 projects.*.mcpServers（保留其它字段）。"
            )

        if verbose:
            notes.append(f"present={len(present)} enabled={len(enabled_names & present)}")
            if path is not None:
                notes.append(f"path={path}")

        worst = _bump(worst, status)
        target_reports[key] = {
            "label": label,
            "status": status,
            "unknown": unknown,
            "disabled_present": disabled_present,
            "notes": notes,
            "suggestions": suggestions,
        }

    # 3) 汇总与输出
    if not central_exists:
        worst = _bump(worst, "failed")

    if not ok:
        worst = _bump(worst, "failed")

    # central 体检有建议项：标记为 warn（不阻塞使用，但建议处理）
    if ok and central_doctor.get("status") == "failed":
        worst = _bump(worst, "warn")

    out = {
        "status": worst,
        "central": {
            "path": str(central_path),
            "exists": central_exists,
            "valid": ok,
            "message": msg,
            "total": len(servers_all),
            "enabled": len(enabled),
            "disabled": len(disabled),
            "doctor": central_doctor,
        },
        "targets": target_reports,
    }

    if use_json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0 if worst != "failed" else 1

    print("MCP Doctor（聚合诊断）")
    print(f"- central: {central_path} ({'存在' if central_exists else '缺失'})")
    if not central_exists:
        print(
            "  ❌ 未找到 central；建议先运行：mcp onboard（会自动创建最小 central）"
            " 或 scripts/install-mac.sh"
        )
    else:
        check_line = f"- central 校验: {'✅ 通过' if ok else '❌ 失败'}"
        if not ok:
            check_line += f"（{msg}）"
        print(check_line)
        print(f"- central 服务: 总计 {len(servers_all)}，启用 {len(enabled)}，禁用 {len(disabled)}")

    if central_doctor.get("issues"):
        print("\n— central 体检建议（仅启用项）—")
        for it in central_doctor["issues"][:10]:
            print("  - " + str(it))
        if len(central_doctor["issues"]) > 10:
            more = len(central_doctor["issues"]) - 10
            print(f"  - … 还有 {more} 条（建议用 `mcp central doctor --json` 查看完整）")

    print("\n— 目标端漂移（unknown/disabled）—")
    if not target_reports:
        print("  （无目标端检查项）")
    for key, rep in target_reports.items():
        label = rep.get("label", key)
        status = rep.get("status")
        prefix = "✅" if status == "passed" else ("⚠️" if status == "warn" else "❌")
        print(f"\n[{label}] {prefix} {status}")
        for n in rep.get("notes") or []:
            print("  - " + n)
        for s in rep.get("suggestions") or []:
            print("  - " + s)

    # 最终下一步（给普通用户的“单一建议”）
    if worst == "failed":
        print("\n结论: ❌ 需要处理（建议先修 central，再用 mcp onboard 下发）")
        return 1
    if worst == "warn":
        print("\n结论: ⚠️ 有漂移/建议项（不一定阻塞使用）")
        return 0
    print("\n结论: ✅ 基本健康")
    return 0
