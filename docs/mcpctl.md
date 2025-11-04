# mcpctl 命令参考

`mcpctl` 是一个极简 CLI，用于“按客户端/IDE 精准落地 MCP 配置”，避免一次性加载全部服务器导致上下文与 Token 消耗过大。

- 默认理念：中央清单未显式 `enabled: false` 的条目都视为启用；真正是否“加载”，由你对某个 CLI/IDE 的落地选择决定。
- 不修改非 MCP 段；Claude 同步时会清理注册表的多余项、补齐缺失项。

## 快速开始

查看某个客户端的当前集合（别名见下）

    mcpctl status codex
    mcpctl status claude
    mcpctl status vscode

仅对 Claude 下发 context7+serena，并立即启动 Claude CLI：

    mcpctl run --client claude --servers context7,serena -- claude

仅下发不启动：

    mcpctl apply-cli --client claude --servers context7,serena

IDE（VS Code/Cursor）写入全部 MCP；具体开关在 IDE 内操作：

    mcpctl ide-all

## 子命令

- status [client] [--central]
  - 展示各客户端/IDE 的实际 MCP 集合（on/off）。
  - client 支持别名：
    - claude(= claude-file)、claude-reg、codex、gemini、iflow、droid、cursor、vscode(=vscode-user)、vscode-insiders
  - --central 可选显示中央清单（通常不需要）。

- apply-cli --client <client> --servers <name1,name2,...>
  - 将一组 MCP 仅应用到某个 CLI/IDE 的配置文件；其它客户端不受影响。
  - client 取值：claude | codex | gemini | iflow | droid | cursor | vscode-user | vscode-insiders。

- pick
  - 交互式选择目标 CLI/IDE 与 MCP 集合并应用。

- ide-all
  - 将“全部 MCP”写入 VS Code（User/Insiders）与 Cursor；开关在 IDE 界面内操作。

- run --client <client> --servers <...> -- <启动命令...>
  - 先按客户端应用集合，再执行启动命令；若省略启动命令，则只做应用不启动。
  - 示例：
    - mcpctl run --client claude --servers context7,serena -- claude
    - mcpctl run --client vscode-user --servers filesystem -- code .

## 注意事项

- Claude 注册表：apply-cli/run 会清理多余注册项并补齐缺失，确保 /mcp 面板只显示所选集合。
- IDE 专用文件：
  - VS Code：~/.config/Code/User/mcp.json 与 ~/.config/Code - Insiders/User/mcp.json
  - Cursor：~/.cursor/mcp.json
- 文件备份：所有改写会生成带时间戳的 .backup 便于回滚。
 - 中央清单建议：Node 生态服务显式写 `npx -y <package>@latest`，保持最新；如需稳定，可对单个服务改为固定版本（`@x.y.z`）。

## 故障排查

- “status 显示 on/off 与你的预期不一致”：先确认查看的是目标客户端（如 status claude 而非空参）。
- “run 后没有启动”：-- 之后是否跟了启动命令；省略时只做落地不启动。
- “IDE 里未显示新条目”：先执行 mcpctl ide-all，让 IDE 文件包含完整集合，然后在 IDE 界面里逐项开关。
