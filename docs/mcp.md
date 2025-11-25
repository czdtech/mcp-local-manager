# mcp 命令参考

`mcp` 是一个极简 CLI，用于“按客户端/IDE 精准落地 MCP 配置”，避免一次性加载全部服务器导致上下文与 Token 消耗过大。

- 默认理念：中央清单未显式 `enabled: false` 的条目都视为启用；真正是否“加载”，由你对某个 CLI/IDE 的落地选择决定。
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

（已收敛）不再提供参数式配置命令，全部改为交互模式：

- run（交互式）
  - 运行 `mcp run` 后，依提示选择客户端与服务集合；可选输入启动命令；直接回车仅落地不启动。

## 注意事项

- Claude 注册表：run 会清理多余注册项并补齐缺失，确保 /mcp 面板只显示所选集合。
- Droid 注册表：run 会对所选集合执行“先 remove 再 add”，并写入 `~/.factory/mcp.json` 顶层 `mcpServers`，确保 /mcp 面板与中央清单完全一致。
- IDE 专用文件：
  - VS Code：CLI 会按平台自动定位（macOS 使用 `~/Library/Application Support/...`，Linux 使用 `~/.config/...`）
  - Cursor：~/.cursor/mcp.json
- 文件备份：所有改写会生成单槽 `.backup` 覆盖，配合 `mcp undo` 可回滚。
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
