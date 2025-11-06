# Changelog

## v1.2.2 (2025-11-06)

- 行为变更：安装脚本默认不再自动同步/落地 MCP，仅生成统一清单并执行体检；需要落地时使用 `mcpctl pick/apply-cli/run` 或可选 `scripts/mcp-sync.sh`。
- 脚本：`scripts/install-mac.sh` 去除 `mcp-auto-sync.py sync` 调用，新增明确提示“安装默认不落地 MCP，需用户自行选择 via mcpctl”。保留 npx 预热为可选步骤。
- 文档：
  - `README.md` 更新快速使用与目录说明，强调按需落地与最小化启用；`onboard-cursor-minimal.sh` 与 `mcpctl` 标注为“可选”。
  - `docs/QUICKSTART-mac.md` 移除“执行同步”表述，明确安装脚本不落地。
  - `docs/troubleshooting-mcp.md` 说明“默认不自动同步”，保留 `mcp-sync.sh` 作为可选路径。
 - CLI：`mcpctl` 新增 `-n/--dry-run` 预览模式，支持 `apply-cli`/`ide-all`/`run` 等子命令仅显示将进行的写入、注册与启动动作，不做实际修改。

## v1.2.1 (2025-11-04)

- 体验：安装脚本追加 npx 预热与 `--probe` 连通性探测，贴近“一键完成”。
- 体检：`mcp-check.sh` 支持 `--probe`，结合 `claude mcp list` / `gemini mcp list` 输出实际连通性。
- CLI：`mcpctl ide-all` 增加确认提示；`apply-cli --client claude` 强制重注册，确保按中央清单收敛到 npx @latest（`serena` 仍本地二进制）。
- 文档：新增“混合策略”（默认 npx，个别不稳改二进制直连）与 “npx @latest 常见问题（task-master-ai）” 的排障指引。

升级指引（从 v1.1.x → v1.2.1）：

1) 更新脚本：
   - 拉取仓库最新 main；确保 PATH 指向当前仓库的 `bin/mcpctl`。
2) 一键执行：
   - `bash scripts/install-mac.sh`
   - 安装脚本会完成：同步→（可选）npx 预热→体检+连通性探测。
3) 精准落地（按需）：
   - 仅对需要的客户端下发所需 MCP，例如：
     - `mcpctl apply-cli --client cursor --servers task-master-ai,context7`
     - `mcpctl apply-cli --client claude --servers filesystem,playwright`
4) 验证：
   - `mcpctl check --probe`（或 `claude/gemini mcp list`）。
5) 如遇 `task-master-ai@latest` 在 Gemini 侧不稳：
   - 切为全局二进制直连：`npm i -g task-master-ai@latest`，并将 Gemini 对应条目改为 `command: "task-master-ai"`、`args: []`。

## v1.1.1 (2025-11-04)

- CLI: 兼容 Python 3.9（添加 `from __future__ import annotations` 延迟注解求值）。
- 清理：移除未使用的 nvm 相关遗留代码与未定义引用。
- 行为：无破坏性变更；可用子命令不变（status/apply-cli/pick/ide-all/run/check）。
- 升级建议：
  - 重新链接或更新 PATH 到最新 `bin/mcpctl`。
  - 执行 `mcpctl -h` 验证；如需，运行 `mcpctl check` 做只读体检。

> 注：当前仓库基线采用显式最新版（`npx -y <package>@latest`）；如需稳定，可在中央清单对单个服务改回固定版本（`@x.y.z`）。
