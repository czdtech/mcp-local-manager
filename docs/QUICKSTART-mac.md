# QUICKSTART (macOS)

## 前置
- 已安装 Node（推荐 nvm）
- 可选：Chrome for Testing（若无则使用系统 Chrome 或 Playwright 自带）
- 相关 CLI（codex/gemini/iflow/claude/droid）已安装或允许稍后手动安装

## 一次安装（不自动落地）
（默认策略：所有 Node 生态 MCP 使用 `npx -y <package>@latest`，始终获取最新版；`serena` 走本地二进制。安装脚本仅渲染统一清单与体检，不执行同步/落地）

新人一键最小落地（推荐）：

```
# 仅为 Cursor 启用 context7 + task-master-ai，其它 CLI/IDE 保持“裸奔”
bash scripts/onboard-cursor-minimal.sh
# 复验：
mcpctl status cursor
```

若需对某 CLI 临时下发少量服务，请使用：

```
mcpctl apply-cli --client <cli> --servers context7,task-master-ai
```

仅预览（不写入）：可在任何命令加 `-n/--dry-run`，例如：
```
mcpctl apply-cli -n --client claude --servers context7,serena
```
```
cd mcp-local-manager
bash scripts/install-mac.sh
```
- 脚本会：
  - 体检 macOS 路径（VS Code/Insiders、Cursor、Node、Chrome）
  - 生成 `~/.mcp-central/config/mcp-servers.json`
  - 不执行同步（默认不落地 MCP，需按需使用 mcpctl）
  - 运行健康检查并输出结论

## 每次启动 CLI/IDE 前（推荐）
优先用 mcpctl 按需下发，避免一次性加载全部服务：
```
# 例：Claude 只启用 context7+serena
mcpctl run --client claude --servers context7,serena -- claude

# 或者仅下发不启动：
mcpctl apply-cli --client claude --servers context7,serena

# IDE（VS Code/Cursor）建议按需启用少量（示例：Cursor 只启用 task-master-ai + context7）：
mcpctl apply-cli --client cursor --servers task-master-ai,context7

# 查看当前集合：
mcpctl status codex   # 或 claude/vscode/cursor
```

## 统一来源位置
- `~/.mcp-central/config/mcp-servers.json`

## 目标落地（只改 MCP；默认全部启用，除非显式 `enabled: false`）
- Codex: `~/.codex/config.toml` `[mcp_servers.*]` + `*.env`
- Gemini: `~/.gemini/settings.json` `mcpServers` + `mcp.allowed`
- iFlow: `~/.iflow/settings.json` `mcpServers`
- Claude: `~/.claude/settings.json` `mcpServers` + 命令兜底
- Droid: `~/.factory/mcp.json` `mcpServers`
- Cursor: `~/.cursor/mcp.json` `mcpServers`
- VS Code: `~/Library/Application Support/Code/User/mcp.json` 顶层 `servers`
