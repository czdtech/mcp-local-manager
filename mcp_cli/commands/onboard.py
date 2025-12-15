#!/usr/bin/env python3
"""onboard 子命令：一键上手（固化北极星路径）。

目标：
- 新手只需要选“客户端 + 预设包”，即可完成：
  1) 保证 central 存在且包含所需服务（必要时自动创建/启用）
  2) 将该预设包落地到目标客户端（等价于 mcp run --client ... --preset ... --yes）
  3) 可选本地化 npx 服务（localize）
"""

from __future__ import annotations

import os
from copy import deepcopy

from . import central as CENTRAL
from . import run as RUN

CLIENTS: list[tuple[str, str]] = [
    ("cursor", "Cursor（推荐新手）"),
    ("claude", "Claude"),
    ("vscode-user", "VS Code(User)"),
    ("vscode-insiders", "VS Code(Insiders)"),
    ("codex", "Codex"),
    ("gemini", "Gemini"),
    ("iflow", "iFlow"),
    ("droid", "Droid"),
]


DEFAULT_PRESET_BY_CLIENT: dict[str, str] = {
    "cursor": "cursor-minimal",
    "claude": "claude-basic",
    "vscode-user": "vscode-user-basic",
    "vscode-insiders": "vscode-user-basic",
    "codex": "task-suite",
    "gemini": "task-suite",
    "iflow": "task-suite",
    "droid": "task-suite",
}


def _normalize_apply_client(raw: str | None) -> str | None:
    if not raw:
        return None
    v = str(raw).strip().lower()
    alias = {
        "vscode": "vscode-user",
        "vscode-user": "vscode-user",
        "vscode-insiders": "vscode-insiders",
        "vscode-ins": "vscode-insiders",
        "insiders": "vscode-insiders",
        "claude": "claude",
        "codex": "codex",
        "gemini": "gemini",
        "iflow": "iflow",
        "droid": "droid",
        "cursor": "cursor",
    }
    return alias.get(v)


def _choose_client_interactive() -> str:
    print("选择你要配置的客户端/IDE（回车=1）:")
    for i, (key, label) in enumerate(CLIENTS, start=1):
        print(f"  {i}) {label} [{key}]")
    raw = input("输入编号: ").strip() or "1"
    try:
        idx = int(raw)
    except Exception:
        idx = 1
    idx = max(1, min(idx, len(CLIENTS)))
    return CLIENTS[idx - 1][0]


def _choose_preset_interactive(default_preset: str | None) -> str:
    presets = list(RUN.PRESET_PACKS.items())
    default_idx = 1
    if default_preset:
        for i, (k, _) in enumerate(presets, start=1):
            if k == default_preset:
                default_idx = i
                break
    print("\n选择预设/场景包（回车=默认推荐）:")
    for i, (k, v) in enumerate(presets, start=1):
        hint = "（推荐）" if i == default_idx else ""
        print(f'  {i}) {k} - {v["desc"]} {hint}')
    raw = input("输入编号: ").strip() or str(default_idx)
    if raw.isdigit() and 1 <= int(raw) <= len(presets):
        return presets[int(raw) - 1][0]
    return presets[default_idx - 1][0]


def _ensure_central_has_enabled_servers(
    required: list[str], *, dry_run: bool
) -> tuple[bool, list[str]]:
    """确保 central 中存在并启用 required 服务器。

    Returns:
      changed: 是否会修改 central
      actions: 人类可读的变更摘要
    """
    data = CENTRAL._load_central_or_new()  # noqa: SLF001  # 内部复用
    servers = data.setdefault("servers", {})
    changed = False
    actions: list[str] = []

    for name in required:
        if name in servers:
            if not bool((servers[name] or {}).get("enabled", True)):
                servers[name]["enabled"] = True
                changed = True
                actions.append(f"启用: {name}")
            continue

        # 新增缺失服务：优先用内置模板
        if name in CENTRAL._BUILTIN_TEMPLATES:  # noqa: SLF001  # 内部复用
            entry = deepcopy(CENTRAL._BUILTIN_TEMPLATES[name])  # noqa: SLF001
            entry.setdefault("enabled", True)
            servers[name] = entry
            changed = True
            actions.append(f"新增: {name}（模板）")
            continue

        # 特例：寸止（本地二进制）
        if name == "寸止":
            servers[name] = {"command": "寸止", "enabled": True, "type": "local"}
            changed = True
            actions.append("新增: 寸止（自定义）")
            continue

        raise ValueError(
            f"central 缺少服务定义且无内置模板: {name}。请先运行 `mcp central add/template` 补齐。"
        )

    if not changed:
        return False, []

    if dry_run:
        # 仅输出摘要，不写盘
        return True, actions

    CENTRAL._save_central(data, dry=False)  # noqa: SLF001  # 内部复用
    return True, actions


def run(args) -> int:
    dry_run = bool(getattr(args, "dry_run", False))

    raw_client = getattr(args, "client", None)
    client = _normalize_apply_client(raw_client)
    preset = getattr(args, "preset", None)
    yes = bool(getattr(args, "yes", False) or (os.environ.get("MCP_ONBOARD_YES") == "1"))
    localize = bool(getattr(args, "localize", False))

    if not client:
        client = _choose_client_interactive()
    default_preset = DEFAULT_PRESET_BY_CLIENT.get(client)
    if not preset:
        # 一键模式：用户显式指定了 client 时，不再强制二次交互，直接用推荐 preset
        if raw_client and default_preset:
            preset = default_preset
        else:
            preset = _choose_preset_interactive(default_preset)

    if preset not in RUN.PRESET_PACKS:
        print(f"[ERR] 未知预设: {preset}")
        return 1

    required = list(RUN.PRESET_PACKS[preset]["servers"])
    print("\n— 北极星路径：一键上手 —")
    print(f"目标客户端: {client}")
    print(f"预设包  : {preset}")
    print("服务集合: " + ", ".join(required))

    # 先保证 central 存在且包含所需服务
    try:
        changed, actions = _ensure_central_has_enabled_servers(required, dry_run=dry_run)
    except Exception as e:
        print(f"[ERR] central 准备失败: {e}")
        return 1

    if changed:
        if dry_run:
            print("[DRY-RUN] central 将执行以下变更：")
        else:
            print("[OK] central 已执行以下变更：")
        for a in actions:
            print("  - " + a)

    # 最终确认（onboard 只确认一次；后续 run 走 --yes 避免重复确认）
    if dry_run:
        print("[DRY-RUN] 将继续预览下发差异（不写入任何客户端）")
    elif not yes:
        reply = input("确认开始下发? [y/N]: ").strip().lower() or "n"
        if reply != "y":
            print("已取消")
            return 0

    # 调用 run 的预选模式
    run_args = type("args", (object,), {})()
    run_args._dry_run = False
    run_args.client = client
    run_args.preset = preset
    run_args.servers = None
    run_args.yes = True  # 避免二次确认
    run_args.dry_run = dry_run
    run_args.localize = localize
    run_args.verbose = bool(getattr(args, "verbose", False))

    rc = RUN.run(run_args)
    if rc == 0 and not dry_run:
        print("\n下一步建议：")
        print(f"  - 查看状态: mcp status {client}")
        print(f"  - 运行诊断: mcp doctor --client {client}")
    return rc
