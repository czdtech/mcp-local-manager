# mcp 命令参考

`mcp` 是一个极简 CLI，用于“按客户端/IDE 精准落地 MCP 配置”，避免一次性加载全部服务器导致上下文与 Token 消耗过大。

- 默认理念：中央清单未显式 `enabled: false` 的条目都视为启用；真正是否“加载”，由你对某个 CLI/IDE 的落地选择决定。
- 行为约束：`mcp run` 默认只下发 central 中“已启用”的服务；被 `enabled: false` 禁用的条目不会被下发（需先在 central 启用）。
- 状态基线：`mcp status` 的 on/off 以“已启用”集合为基线；若目标端仍配置了 central 已禁用的服务，会提示告警。
- 不修改非 MCP 段；Claude 同步时会清理注册表的多余项、补齐缺失项。

## 快速开始

查看某个客户端的当前集合（别名见下）

    mcp status codex
    mcp status claude
    mcp status vscode

仅对 Claude 下发 context7+serena，并立即启动 Claude CLI：

    运行 `mcp run` 进入交互式选择（可输入启动命令）

仅下发不启动：

    运行 `mcp run` 进入交互式选择（只做落地不启动时直接回车）

为 VS Code/Cursor 按需落地（示例）：

    运行 `mcp run` 交互式选择 Cursor 并下发所需
    运行 `mcp run` 交互式选择 VS Code 并下发所需

安装/同步后建议：

```
# 可选预热，减少 npx 首次拉包失败
bash scripts/npx-prewarm.sh

# 一次看清配置+连通性
mcp check
```

## 子命令

- status [client] [--central]
  - 展示各客户端/IDE 的实际 MCP 集合（on/off）。
  - client 支持别名：
    - claude(= claude-file)、claude-reg、codex、gemini、iflow、droid、cursor、vscode(=vscode-user)、vscode-insiders
  - --central 可选显示中央清单（通常不需要）。

交互优先，同时保留少量参数式用法，方便脚本与自动化：

- onboard（北极星路径，一键上手）
  - 作用：为新手固化“最短路径”，一次完成：
    1) 保证 central 存在且包含预设所需服务（必要时自动创建/启用）
    2) 将预设包下发到目标客户端（等价于 `mcp run --client ... --preset ... --yes`）
    3) 可选本地化 npx 服务（加速启动）
  - 示例：
    - `mcp onboard`（交互式，默认推荐 Cursor 最小包）
    - `mcp onboard --client cursor --yes`（非交互，一键下发 cursor-minimal）
    - `mcp onboard --client claude --preset claude-basic --localize --yes`
  - 关键参数：
    - `--client`：目标客户端（cursor/claude/vscode-user/vscode-insiders/codex/...）
    - `--preset`：预设场景包名称（默认按 client 推荐）
    - `--localize`：下发前对所选 npx 服务执行一次本地化（写入 `~/.mcp-local`）
    - `--dry-run`：仅预览差异，不写入
    - `--yes`：自动确认写入

- run（交互 / 非交互）
  - 交互模式：直接运行 `mcp run`，依提示选择客户端与服务集合；可选输入启动命令；直接回车仅落地不启动。
  - 非交互示例：
    - `mcp run --client cursor --preset cursor-minimal --yes`：为 Cursor 直接下发预设场景包。
    - `mcp run --client codex --servers filesystem,task-master-ai --dry-run`：仅预览将要写入 Codex 的差异。
  - 关键参数：
    - `--client`：预选客户端（cursor / codex / claude / vscode...），跳过交互选择步骤。
    - `--servers`：预选服务列表（逗号分隔），如 `--servers filesystem,task-master-ai`。
    - `--preset`：预选场景包名称（与交互菜单一致，如 `cursor-minimal` / `claude-basic`）。
    - `--yes`：非交互模式自动确认写入（配合 `--client`/`--servers`/`--preset` 使用）。
    - `--dry-run`：仅预览差异，不写入任何客户端配置。
    - `--localize`：在本次 run 中，为当前选择的 npx 服务执行本地安装并写入 `~/.mcp-local/resolved.json`，使其后续优先使用本地二进制。

- clear（交互 / 非交互）
  - 清理指定或全部客户端 MCP 配置（含 Claude 注册表）；支持 `--client` 多选、`--dry-run` 预览、`--yes` 自动确认。
  - 关键点：
    - 未带 `--client` 时：交互选择要清理的客户端（空行=全部）。
    - 带 `--client` 时：只针对指定客户端清理；如提供了未知客户端名称，会报错并不做任何修改（不会“退回到全部清理”）。
    - Claude 额外清理：会同时清空 `~/.claude.json` 中所有 `projects.*.mcpServers`（local scope / 按目录），避免“清不干净”的错觉。
    - 单槽备份 `.backup`，可用 `mcp undo` 回滚。

- localize
  - 将中央清单中使用 `npx` 启动的服务本地安装到 `~/.mcp-local/npm/<name>/...`，并在 `~/.mcp-local/resolved.json` 中记录“服务名 → 本地二进制路径”的映射。
  - 关键参数：
    - `--upgrade`：强制升级本地版本到最新（`@latest`），适合想要保持始终最新版的场景。
    - `--force`：无视已有安装记录，强制重装。
    - `--prune`：清理本地镜像目录 `~/.mcp-local`，不执行安装。
  - 说明：`mcp run --localize` 只针对“当前选择的服务”做一次性本地化；`mcp localize` 则是对 central 中所有 npx 服务做批量预热/升级。

- doctor（聚合诊断，只读）
  - 作用：一条命令汇总：
    - central 是否存在/是否可校验
    - central 体检建议（复用 `mcp central doctor` 的结论）
    - 各目标端是否出现“unknown / central 已禁用但仍配置”的漂移
  - 示例：
    - `mcp doctor`
    - `mcp doctor --client cursor`
    - `mcp doctor --client claude --json`
  - 关键参数：
    - `--client`：指定要检查的客户端（可多次提供；claude 会展开为 file+registry）
    - `--json`：JSON 输出（便于脚本/自动化）
    - `--verbose`：输出更多细节

- ui（本地 Web UI）
  - 作用：用一个“列表 + 开关”的网页界面，实时把 central 的服务落地到目标客户端。
  - 示例：
    - `mcp ui`
    - `mcp ui --port 0`（系统分配随机空闲端口；也是默认行为）
    - `mcp ui --port 17821`（手动指定端口）
  - 说明：
    - UI 仅监听本机 `127.0.0.1`，并使用一次性 token 保护写操作；请使用终端输出的 URL 打开。

## 注意事项

- Claude 注册表：run 会清理多余注册项并补齐缺失，确保 /mcp 面板只显示所选集合。
- Droid 注册表：run 会对所选集合执行“先 remove 再 add”，并写入 `~/.factory/mcp.json` 顶层 `mcpServers`，确保 /mcp 面板与中央清单完全一致。
- IDE 专用文件：
  - VS Code：CLI 会按平台自动定位（macOS 使用 `~/Library/Application Support/...`，Linux 使用 `~/.config/...`）
  - Cursor：~/.cursor/mcp.json
- 文件备份：所有改写会生成单槽 `.backup` 覆盖，配合 `mcp undo` 可回滚；clear 同样使用单槽备份。
- 体检：`mcp check` 为轻量只读体检；如需连通性等深度体检，请运行 `scripts/mcp-check.sh`。
- 中央清单建议：Node 生态服务显式写 `npx -y <package>@latest`，保持最新；如需稳定，可对单个服务改为固定版本（`@x.y.z`）。
- 成本建议：为降低 Token 消耗，建议 CLI（codex/claude/gemini/iflow/droid）按需落地甚至默认不落地；IDE 仅启用必要 MCP（如 `task-master-ai`、`context7`）。

补充（task-master-ai 与 @latest）：
- Cursor 端推荐最小配置：`"command":"npx","args":["-y","task-master-ai@latest"]`，在 `env` 中至少提供一个可用 Provider 的 API Key（如 `OPENAI_API_KEY` 或 `ANTHROPIC_API_KEY`）。
- 若出现“握手失败/0 tools enabled”，请参考 Task Master 官方配置文档的 *MCP Tool Loading Configuration* 与 *MCP Timeout Configuration*：在条目内加入 `"timeout": 300`（秒）并设置 `"TASK_MASTER_TOOLS": "standard"` 或 `"core"`，即可显著缩短加载并避免 60 秒超时。也可以运行 `mcp central doctor`，该命令会对 `task-master-ai` 的超时与工具集配置做专项体检，并在不符合推荐值时给出中文提示。
- 若遇 npx 依赖缓存导致的模块缺失，可按 `docs/troubleshooting-mcp.md` 的“npx @latest 常见问题与修复”章节清缓存预热，或改为全局二进制直连方案。

## 故障排查

- “status 显示 on/off 与你的预期不一致”：先确认查看的是目标客户端（如 status claude 而非空参）。
- “run 后没有启动”：在交互里输入启动命令；回车跳过则只做落地不启动。
- “IDE 里未显示新条目”：请运行 `mcp run` 交互式选择 Cursor/VS Code，并选择需要的服务写入。
