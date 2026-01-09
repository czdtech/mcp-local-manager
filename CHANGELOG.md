# Changelog

## v1.3.11 (2026-01-09)

- Claude Code：user scope 优先读取 `~/.claude/settings.json` 的 `mcpServers`，并兼容旧版 `~/.claude.json`。
- Doctor/UI/文档：将 `projects.*.mcpServers` 统一表述为 local scope（按目录），减少“项目级覆盖”误解。
- 维护：新增 `scripts/qa.sh` 本地质检与 `docs/RELEASE.md` 发版指南；补齐 GitHub issue/PR 模板；CI workflow 示例化。

## v1.3.10 (2026-01-09)

- Central：强化校验并对齐 Augment MCP 落地。
- Claude Code：支持 scope（user/local/project），并可用 `MCP_CLAUDE_SCOPE` 指定；user scope 读取 `~/.claude.json` 更稳定。
- UI：新增 Claude scope 选择；相关 API 支持 `claude_scope` 参数。
- CLI/脚本：Claude registry 的 add/remove 统一携带 `-s <scope>`，并使用 `--env KEY=VAL` 传参。
- 文档：README / 架构图 / Troubleshooting 对齐 Claude Code 注册表策略与 scope 说明。

## v1.3.9 (2025-12-25)

- 配置：移除 `寸止` 服务器配置
- 配置：新增 `augment-context-engine` 服务器配置（需要用户自行安装 auggie 工具）
- 文档：更新 README.md，在"推荐基线"部分添加 `augment-context-engine` 的安装说明与注意事项

## v1.3.6 (2025-12-22)

- 文档：完善 README 安装说明，添加详细的 4 步安装流程（克隆、运行脚本、配置 PATH、验证安装）

## v1.3.5 (2025-11-27)

- 破坏性变更：移除旧版 `mcp pick` 子命令，统一通过 `mcp run`/`mcp central`/`mcp status`/`mcp check`/`mcp undo` 管理配置。
- 备份策略：改为单槽 `*.backup` 覆盖，避免备份堆积；提供 `mcp undo` 回滚。
- CLI：按用户反馈恢复并加强 `mcp clear`，支持 `--client/--dry-run/--yes`，单槽备份；未知客户端参数会报错并保持现有配置不变。
- CLI：`mcp run` 新增 `--localize` 选项，可在一次 run 中为当前选择的 npx 服务执行本地化并写入 `~/.mcp-local/resolved.json`，实现“边选择边本地化”的混合配置；Claude 注册表同步逻辑改为使用应用本地化覆盖后的 `command/args` 重建条目。
- 文档：清理 pick 相关描述，对齐新的 run/clear/localize 行为。

## v1.3.2 (2025-11-10)

- 文档/脚本同步与测试补充（补丁发布，不含 CLI 功能变更）：
  - docs: QUICKSTART / troubleshooting / 架构图 等微调
  - scripts: install / onboard / quickstart 提示同步
  - tests: 新增 tests/test_sync_integration.py；修正与整理测试套件

## v1.3.1 (2025-11-10)

- 修复（Droid）：按官方规范写入 `~/.factory/mcp.json` 顶层 `mcpServers`，并在 `mcp run` 交互中选择 Droid 时改为“先 remove 再 add”强制重注册，确保 `/mcp` 面板即时、准确地反映中央清单。
- 文档：更新 README/docs，明确 Droid 的注册表对齐策略与使用示例；Troubleshooting 增补 `droid mcp add` 推荐写法与 env 传参说明。

## v1.3.0 (2025-11-06)

- 重大变更：命令行工具统一为 `mcp`，旧命令别名已移除。
- 代码：`bin/mcp` 由 Bash 包装器替换为 Python 主 CLI（承接原有逻辑），`argparse` 的 `prog` 与帮助文本统一为 `mcp`。
- 文档与脚本：全面改用 `mcp`；相关页面已合并为 `docs/mcp.md`。
- 架构图：更新 Mermaid/PlantUML 标注，统一为 MCP（mcp）。
- 迁移指引（破坏性变更）：
  - 确保 PATH 指向 `bin/mcp`，或重新链接：`ln -sf $(pwd)/bin/mcp ~/.local/bin/mcp`
  - 后续均使用 `mcp`，例如：`mcp run ...`；如需深度体检可运行 `bash scripts/mcp-check.sh --probe`。


## v1.2.2 (2025-11-06)

- 行为变更：安装脚本默认不再自动同步/落地 MCP，仅生成统一清单并执行体检；需要落地时使用 `mcp run` 或可选 `scripts/mcp-sync.sh`。
- 脚本：`scripts/install-mac.sh` 去除 `mcp-auto-sync.py sync` 调用，新增明确提示“安装默认不落地 MCP，需用户自行选择 via mcp”。保留 npx 预热为可选步骤。
- 文档：
  - `README.md` 更新快速使用与目录说明，强调按需落地与最小化启用；`onboard-cursor-minimal.sh` 标注为“可选”。
  - `docs/QUICKSTART.md` 强调安装脚本不落地，需按需使用 `mcp` 选择后下发。
  - `docs/troubleshooting-mcp.md` 说明“默认不自动同步”，保留 `mcp-sync.sh` 作为可选路径。
- CLI 交互化：配置/管理能力改为交互模式；全局 `-n/--dry-run` 已移除，预览与确认在交互步骤中完成，需要预览时使用子命令级 `--dry-run`（如 `mcp run --dry-run` / `mcp clear --dry-run`）。
 - 新增别名：已移除（统一使用 `mcp`）。

## v1.2.1 (2025-11-04)

- 体验：安装脚本追加 npx 预热与 `--probe` 连通性探测，贴近“一键完成”。
- 体检：`mcp-check.sh` 支持 `--probe`，结合 `claude mcp list` / `gemini mcp list` 输出实际连通性。
- CLI：在 `mcp run` 交互中选择 Claude 时，强制对齐注册表，确保按中央清单收敛到 npx @latest（`serena` 仍本地二进制）。
- 文档：新增“混合策略”（默认 npx，个别不稳改二进制直连）与 “npx @latest 常见问题（task-master-ai）” 的排障指引。

升级指引（从 v1.1.x → v1.2.1）：

1) 更新脚本：
   - 拉取仓库最新 main；确保 PATH 指向当前仓库的 `bin/mcp`。
2) 一键执行：
   - `bash scripts/install-mac.sh`
   - 安装脚本会完成：同步→（可选）npx 预热→体检+连通性探测。
3) 精准落地（按需）：
   - 仅对需要的客户端下发所需 MCP，例如：
     - 运行 `mcp run` 进入交互选择所需 MCP 并落地到目标客户端
4) 验证：
   - `bash scripts/mcp-check.sh --probe`（或 `claude/gemini mcp list`）。
5) 如遇 `task-master-ai@latest` 在 Gemini 侧不稳：
   - 切为全局二进制直连：`npm i -g task-master-ai@latest`，并将 Gemini 对应条目改为 `command: "task-master-ai"`、`args: []`。

## v1.1.1 (2025-11-04)

- CLI: 兼容 Python 3.9（添加 `from __future__ import annotations` 延迟注解求值）。
- 清理：移除未使用的 nvm 相关遗留代码与未定义引用。
- 行为：无破坏性变更；可用子命令不变（status/run/check）。
- 升级建议：
  - 重新链接或更新 PATH 到最新 `bin/mcp`。
  - 执行 `mcp -h` 验证；如需，运行 `mcp check` 做只读体检。

> 注：当前仓库基线采用显式最新版（`npx -y <package>@latest`）；如需稳定，可在中央清单对单个服务改回固定版本（`@x.y.z`）。
