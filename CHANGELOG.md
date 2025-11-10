# Changelog

## v1.3.0 (2025-11-06)

- 重大变更：命令行工具统一为 `mcp`，旧命令别名已移除。
- 代码：`bin/mcp` 由 Bash 包装器替换为 Python 主 CLI（承接原有逻辑），`argparse` 的 `prog` 与帮助文本统一为 `mcp`。
- 文档与脚本：全面改用 `mcp`；相关页面已合并为 `docs/mcp.md`。
- 架构图：更新 Mermaid/PlantUML 标注，统一为 MCP（mcp）。
- 迁移指引（破坏性变更）：
  - 确保 PATH 指向 `bin/mcp`，或重新链接：`ln -sf $(pwd)/bin/mcp ~/.local/bin/mcp`
  - 后续均使用 `mcp`，例如：`mcp run ...`、`mcp check --probe`。


## v1.2.2 (2025-11-06)

- 行为变更：安装脚本默认不再自动同步/落地 MCP，仅生成统一清单并执行体检；需要落地时使用 `mcp pick/run` 或可选 `scripts/mcp-sync.sh`。
- 脚本：`scripts/install-mac.sh` 去除 `mcp-auto-sync.py sync` 调用，新增明确提示“安装默认不落地 MCP，需用户自行选择 via mcp”。保留 npx 预热为可选步骤。
- 文档：
  - `README.md` 更新快速使用与目录说明，强调按需落地与最小化启用；`onboard-cursor-minimal.sh` 标注为“可选”。
  - `docs/QUICKSTART-mac.md` 移除“执行同步”表述，明确安装脚本不落地。
  - `docs/troubleshooting-mcp.md` 说明“默认不自动同步”，保留 `mcp-sync.sh` 作为可选路径。
 - CLI：`mcp` 新增 `-n/--dry-run` 预览模式，支持 `run` 等子命令仅显示将进行的写入、注册与启动动作，不做实际修改。
 - 新增别名：已移除（统一使用 `mcp`）。

## v1.2.1 (2025-11-04)

- 体验：安装脚本追加 npx 预热与 `--probe` 连通性探测，贴近“一键完成”。
- 体检：`mcp-check.sh` 支持 `--probe`，结合 `claude mcp list` / `gemini mcp list` 输出实际连通性。
- CLI：`run --client claude` 强制对齐注册表，确保按中央清单收敛到 npx @latest（`serena` 仍本地二进制）。
- 文档：新增“混合策略”（默认 npx，个别不稳改二进制直连）与 “npx @latest 常见问题（task-master-ai）” 的排障指引。

升级指引（从 v1.1.x → v1.2.1）：

1) 更新脚本：
   - 拉取仓库最新 main；确保 PATH 指向当前仓库的 `bin/mcp`。
2) 一键执行：
   - `bash scripts/install-mac.sh`
   - 安装脚本会完成：同步→（可选）npx 预热→体检+连通性探测。
3) 精准落地（按需）：
   - 仅对需要的客户端下发所需 MCP，例如：
     - `mcp run --client cursor --servers task-master-ai,context7`
     - `mcp run --client claude --servers filesystem,playwright`
4) 验证：
   - `mcp check --probe`（或 `claude/gemini mcp list`）。
5) 如遇 `task-master-ai@latest` 在 Gemini 侧不稳：
   - 切为全局二进制直连：`npm i -g task-master-ai@latest`，并将 Gemini 对应条目改为 `command: "task-master-ai"`、`args: []`。

## v1.1.1 (2025-11-04)

- CLI: 兼容 Python 3.9（添加 `from __future__ import annotations` 延迟注解求值）。
- 清理：移除未使用的 nvm 相关遗留代码与未定义引用。
- 行为：无破坏性变更；可用子命令不变（status/pick/run/check）。
- 升级建议：
  - 重新链接或更新 PATH 到最新 `bin/mcp`。
  - 执行 `mcp -h` 验证；如需，运行 `mcp check` 做只读体检。

> 注：当前仓库基线采用显式最新版（`npx -y <package>@latest`）；如需稳定，可在中央清单对单个服务改回固定版本（`@x.y.z`）。
## v1.3.1 (2025-11-10)

- 新增（CLI）：`mcp clear` 一键清除所有 CLI/IDE 的 MCP 配置；支持 `--client <name>` 定向清理与 `-n` 预览，`-y` 跳过确认。覆盖 Claude(文件+注册表)、Codex、Gemini、iFlow、Droid、Cursor、VS Code(User/Insiders)。
- 修复（Droid）：按官方规范写入 `~/.factory/mcp.json` 顶层 `mcpServers`，并在 `mcp run --client droid` 中改为“先 remove 再 add”强制重注册，确保 `/mcp` 面板即时、准确地反映中央清单。
- 文档：更新 README/docs，明确 Droid 的注册表对齐策略与使用示例；Troubleshooting 增补 `droid mcp add` 推荐写法与 env 传参说明；新增 `clear` 用法文档。
