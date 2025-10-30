# MCP Local Manager

用途：在 macOS 与 Linux 上以“单一来源”管理所有 CLI/编辑器的 MCP 服务器配置，做到一次修改、处处生效；并提供一键同步与只读健康检查。

核心理念：
- 统一来源：`~/.mcp-central/config/mcp-servers.json`
- 仅改 MCP 段：不同目标只写入各自 MCP 部分（如 Codex 的 `[mcp_servers.*]`、Gemini 的 `mcpServers` 等），不触碰其它设置
- Claude：文件为主（`~/.claude/settings.json`），命令兜底仅补“缺失项”

## 目录

```
mcp-local-manager/
├─ bin/
│  └─ mcp-auto-sync.py        # 跨平台同步（darwin/linux），只改 MCP 段
├─ scripts/
│  ├─ install-mac.sh          # macOS 首次安装：体检→渲染→同步→体检
│  ├─ mcp-sync.sh             # 一键同步
│  └─ mcp-check.sh            # 健康检查（只读）
├─ config/
│  └─ mcp-servers.sample.json # 示例统一清单（可参考）
└─ docs/
   └─ QUICKSTART-mac.md       # macOS 快速开始
```

## 快速上手

1. 体检 + 渲染统一清单 + 同步 + 体检
```
bash scripts/install-mac.sh
```

2. 之后日常只需：
```
bash scripts/mcp-sync.sh   # 同步（只改 MCP）
bash scripts/mcp-check.sh  # 只读健康检查
```

## 统一清单位置（两端通用）

- 脚本会生成/使用：`~/.mcp-central/config/mcp-servers.json`
- 你也可以用本仓库的 `config/mcp-servers.sample.json` 作参考，然后复制到 `~/.mcp-central/config/mcp-servers.json` 后再执行同步

## 目标落地（仅改 MCP 部分，macOS/Linux 通用，路径按系统适配）

- Codex:   `~/.codex/config.toml`      仅 `[mcp_servers.*]` 与 `*.env`
- Gemini:  `~/.gemini/settings.json`   仅 `mcpServers` + `mcp.allowed`
- iFlow:   `~/.iflow/settings.json`    仅 `mcpServers`
- Claude:  `~/.claude/settings.json`   写 `mcpServers`；若缺项则命令兜底补齐
- Droid:   `~/.factory/mcp.json`       仅 `mcpServers`
- Cursor:  `~/.cursor/mcp.json`        仅 `mcpServers`
- VS Code: macOS `~/Library/Application Support/Code/User/mcp.json` 顶层 `servers`
           macOS Insiders `~/Library/Application Support/Code - Insiders/User/mcp.json`
           Linux `~/.config/Code/User/mcp.json` 与 `~/.config/Code - Insiders/User/mcp.json`

## 已有配置不一致怎么办？（安全迁移）

- 只改 MCP：本项目所有脚本都“仅替换 MCP 配置段”，不会触碰其它设置。
- 自动备份：每次落地前都会生成 `*.backup`，可随时回滚。
- 推荐流程：
  1) 先运行 `scripts/mcp-check.sh` 只读体检，记录现状。
  2) 准备/确认 `~/.mcp-central/config/mcp-servers.json`（统一清单）。
  3) 运行 `scripts/mcp-sync.sh` 同步各目标（Claude 缺项命令兜底）。
  4) 再运行 `scripts/mcp-check.sh`，期待结论 `OK`。
- 去重提示：
  - Cursor 建议只保留 `~/.cursor/mcp.json`，避免把 `mcpServers` 放在 `~/.config/cursor/User/settings.json` 造成重复展示。
  - VS Code 使用 `mcp.json`（顶层 `servers`），不要把清单放入 `settings.json`。

