# MCP Local Manager

![安装](https://img.shields.io/badge/%E5%AE%89%E8%A3%85-install--mac.sh-2ea44f?logo=gnubash&logoColor=white)
![CLI](https://img.shields.io/badge/CLI-mcp-2ea44f?logo=gnubash&logoColor=white)
![体检](https://img.shields.io/badge/%E4%BD%93%E6%A3%80-mcp--check.sh-2ea44f?logo=gnubash&logoColor=white)

在 macOS 与 Linux 上以"单一来源"管理所有 CLI/编辑器的 MCP 服务器配置，做到一次修改、处处生效；并提供一键同步与只读健康检查。

## 快速使用

### 安装（默认不自动落地 MCP）

```bash
# 安装脚本仅：体检→渲染统一清单→体检（不执行同步/落地）
bash scripts/install-mac.sh
bash scripts/mcp-check.sh     # 只读健康检查
```

### CLI 命令（推荐日常使用）

```bash
# 将所选 MCP 仅应用到某个 CLI/IDE：
mcp apply-cli --client claude --servers context7,serena

# 交互选择并应用：
mcp pick

# 应用后直接启动：
mcp run --client claude --servers context7,serena -- claude

# 查看单个客户端当前集合：
mcp status codex   # 等价于：mcp status --client codex

# IDE（VS Code/Cursor）统一写入全部，具体开关在 IDE 内操作：
mcp ide-all
```

### 预览模式（dry-run）

为任意命令追加 \`-n\` 或 \`--dry-run\` 可预览变更而不实际执行：

```bash
# 仅预览将写入 Claude 文件与注册表的变更
mcp apply-cli -n --client claude --servers context7,serena

# 仅预览将写入 VS Code/Cursor 的全集（不落地）
mcp ide-all --dry-run

# 仅预览按客户端应用后将要启动的命令
mcp run -n --client claude --servers context7,serena -- claude
```

### 新人一键最小落地（可选，推荐）

```bash
# 仅为 Cursor 启用 context7 + task-master-ai，其它 CLI/IDE 保持"裸奔"
bash scripts/onboard-cursor-minimal.sh
# 复验：
mcp status cursor
```

## 核心理念

- **统一来源**：\`~/.mcp-central/config/mcp-servers.json\`
- **仅改 MCP 段**：不同目标只写入各自 MCP 部分（如 Codex 的 \`[mcp_servers.*]\`、Gemini 的 \`mcpServers\` 等），不触碰其它设置
- **Claude**：文件为主（\`~/.claude/settings.json\`），命令兜底仅补"缺失项"
- **默认全部启用**：清单里未显式写 \`enabled: false\` 的服务都视为启用；是否真正"加载"，由你对某个 CLI/IDE 的落地选择决定
- **安装默认不落地**：\`scripts/install-mac.sh\` 不会执行同步，需使用 \`mcp\` 按需选择后落地

## 推荐基线

- Node 生态 MCP 一律使用 \`npx -y <package>@latest\`，便于获得上游修复（如 \`task-master-ai\`）
- 仅 \`serena\` 走本地二进制（\`~/.local/bin/serena\`）
- 日常建议：仅对 Cursor 落地所需 MCP，其他 CLI/IDE 保持"裸奔"
- 混合策略：默认优先 npx；若某客户端（如 Gemini）对某个服务（如 \`task-master-ai\`）不稳定，则改为"全局二进制直连"（\`npm i -g <pkg>@latest\`，\`command\` 改为该二进制）

## 项目结构

```
mcp-local-manager/
├─ bin/
│  ├─ mcp-auto-sync.py        # 跨平台同步（保留）
│  ├─ mcp                     # 终端 CLI（按客户端落地/查看/启动）
│  └─ mcp_validation.py       # 配置验证模块
├─ scripts/
│  ├─ install-mac.sh          # 首次安装：体检→渲染→体检（不自动同步）
│  ├─ mcp-sync.sh             # 可选：全量同步（只改 MCP 段）
│  ├─ mcp-check.sh            # 健康检查（只读）
│  └─ onboard-cursor-minimal.sh  # 一键最小落地
├─ config/
│  ├─ mcp-servers.sample.json # 示例统一清单
│  └─ mcp-servers.schema.json # JSON Schema 验证定义
├─ tests/                      # 测试框架
│  ├─ test_validation.py      # 验证模块测试
│  ├─ test_mcp_cli.py         # CLI 命令测试
│  └─ test_sync.py            # 同步操作测试
└─ docs/
   └─ mcp-architecture.png    # 架构图
```

## 安装和配置

### 首次安装

```bash
bash scripts/install-mac.sh
```

脚本会自动：
- 生成/更新统一清单（不对各客户端落地）
- 可选预热 npx 缓存（减少首次拉包失败）
- 运行体检并附带连通性探测（\`--probe\`）：调用 \`claude mcp list\`、\`gemini mcp list\` 等一并输出

### 统一清单位置

- 脚本会生成/使用：\`~/.mcp-central/config/mcp-servers.json\`（安装不落地）
- 你也可以用本仓库的 \`config/mcp-servers.sample.json\` 作参考，然后复制到 \`~/.mcp-central/config/mcp-servers.json\` 后再执行同步

### 目标落地位置（仅改 MCP 部分）

- **Codex**: \`~/.codex/config.toml\` - 仅 \`[mcp_servers.*]\` 与 \`*.env\`
- **Gemini**: \`~/.gemini/settings.json\` - 仅 \`mcpServers\` + \`mcp.allowed\`
- **iFlow**: \`~/.iflow/settings.json\` - 仅 \`mcpServers\`
- **Claude**: \`~/.claude/settings.json\` - 写 \`mcpServers\`；若缺项则命令兜底补齐
- **Droid**: \`~/.factory/mcp.json\` - 仅 \`mcpServers\`
- **Cursor**: \`~/.cursor/mcp.json\` - 仅 \`mcpServers\`
- **VS Code**: 
  - macOS: \`~/Library/Application Support/Code/User/mcp.json\` 顶层 \`servers\`
  - macOS Insiders: \`~/Library/Application Support/Code - Insiders/User/mcp.json\`
  - Linux: \`~/.config/Code/User/mcp.json\` 与 \`~/.config/Code - Insiders/User/mcp.json\`

## CLI 命令参考

### status

查看各客户端/IDE 的实际启用状态：

```bash
mcp status [client] [--central]
```

- \`client\` 支持别名：\`claude\`(= claude-file)、\`claude-reg\`、\`codex\`、\`gemini\`、\`iflow\`、\`droid\`、\`cursor\`、\`vscode\`(=vscode-user)、\`vscode-insiders\`
- \`--central\` 可选显示中央清单（通常不需要）

示例：
```bash
mcp status codex
mcp status claude
mcp status cursor
```

### apply-cli

将一组 MCP 仅应用到某个 CLI/IDE 的配置文件：

```bash
mcp apply-cli --client <client> --servers <name1,name2,...>
```

- \`client\` 取值：\`claude\` | \`codex\` | \`gemini\` | \`iflow\` | \`droid\` | \`cursor\` | \`vscode-user\` | \`vscode-insiders\`

示例：
```bash
mcp apply-cli --client claude --servers context7,serena
mcp apply-cli --client cursor --servers task-master-ai,context7
```

### pick

交互式选择目标 CLI/IDE 与 MCP 集合并应用：

```bash
mcp pick
```

### ide-all

将"全部 MCP"写入 VS Code（User/Insiders）与 Cursor；开关在 IDE 界面内操作：

```bash
mcp ide-all
```

### run

先按客户端应用集合，再执行启动命令：

```bash
mcp run --client <client> --servers <...> -- <启动命令...>
```

示例：
```bash
mcp run --client claude --servers context7,serena -- claude
mcp run --client vscode-user --servers filesystem -- code .
```

### check

只读健康检查：

```bash
mcp check [--probe]
```

- \`--probe\` 启用连通性探测，调用各 CLI 的 \`mcp list\` 命令

## 配置验证

项目包含 JSON Schema 配置验证功能，可以验证配置文件的格式和内容：

```bash
# 验证配置文件
python3 bin/mcp_validation.py ~/.mcp-central/config/mcp-servers.json

# 验证示例配置
python3 bin/mcp_validation.py config/mcp-servers.sample.json
```

### 验证特性

- **JSON Schema 验证**：使用 JSON Schema Draft 7 标准验证配置结构
- **优雅降级**：当 \`jsonschema\` 库不可用时，仍可进行基本验证
- **详细错误信息**：提供中文错误消息，便于调试

### 开发测试

```bash
# 安装开发依赖
pip install -r requirements-dev.txt

# 运行测试
pytest -v

# 运行特定测试
pytest tests/test_validation.py -v
```

## 故障排查

### 常见问题

#### 1. npx @latest 依赖缓存问题（task-master-ai）

**症状**：在 Cursor 将 \`task-master-ai\` 配置为 \`npx -y task-master-ai@latest\` 时，日志报错：

```
Error [ERR_MODULE_NOT_FOUND]: Cannot find package '@inquirer/search' ...
```

**原因**：npx 的临时安装/缓存未完整解出最新版的 ESM 依赖

**修复方案 A（推荐）**：

1. 清理缓存：
```bash
npm cache clean --force
rm -rf ~/.npm/_npx/*
```

2. 预热（可选）：
```bash
npx -y task-master-ai@latest --help
```

3. 恢复 Cursor 的官方最小配置：
```json
"command": "npx",
"args": ["-y", "task-master-ai@latest"]
```

4. 在 Cursor 的 MCP 面板对 \`task-master-ai\` 执行"关→开"，或重启 Cursor

**修复方案 B（更快更稳）**：

```bash
# 全局安装
npm i -g task-master-ai@latest

# Cursor 改为直连二进制
"command": "task-master-ai",
"args": []
```

#### 2. Claude 注册表清理

若"文件为主"策略下仍有注册表残留：

```bash
claude mcp remove <name> -s local
claude mcp remove <name> -s user
```

#### 3. VS Code/Cursor 不生效

- 确保使用专用 MCP 文件：
  - VS Code: \`~/.config/Code/User/mcp.json\`（顶层 \`servers\`）
  - Cursor: \`~/.cursor/mcp.json\`（顶层 \`mcpServers\`）
- 不要把 MCP 配置放入 \`settings.json\`

#### 4. 一键失败排查

```bash
# 执行 npx 预热
bash scripts/npx-prewarm.sh

# 运行体检+连通性探测
mcp check --probe

# 若仅某一端/某一服务连不上：只切换该服务为全局二进制
```

### 安全迁移

已有配置不一致时的推荐流程：

1. 先运行 \`scripts/mcp-check.sh\` 只读体检，记录现状
2. 准备/确认 \`~/.mcp-central/config/mcp-servers.json\`（统一清单，未显式 false 的都视为启用）
3. IDE 侧执行 \`mcp ide-all\`（把全部 MCP 写入 IDE，后续开关在 IDE 内操作）
4. 启动某个 CLI 前，用 \`mcp apply-cli\` 或 \`mcp run\` 精确下发所需 MCP
5. 如需全量改写各目标，也可用 \`scripts/mcp-sync.sh\`

**注意事项**：
- 只改 MCP：本项目所有脚本都"仅替换 MCP 配置段"，不会触碰其它设置
- 自动备份：每次落地前都会生成 \`*.backup\`，可随时回滚
- Cursor 建议只保留 \`~/.cursor/mcp.json\`，避免把 \`mcpServers\` 放在 \`~/.config/cursor/User/settings.json\` 造成重复展示
- VS Code 使用 \`mcp.json\`（顶层 \`servers\`），不要把清单放入 \`settings.json\`

## 项目特性

### JSON Schema 配置验证

- **Schema 文件**：\`config/mcp-servers.schema.json\`
- **验证模块**：\`bin/mcp_validation.py\`
  - \`validate_mcp_servers_config()\` - 完整的配置验证
  - \`validate_server_config()\` - 单个服务器配置验证
  - \`validate_central_config_format()\` - 配置格式验证
- **自定义异常**：\`MCPValidationError\`, \`MCPSchemaError\`, \`MCPConfigError\`
- **优雅降级**：当 \`jsonschema\` 库不可用时，仍可进行基本验证

### 增强的错误处理

- 验证失败时输出警告但允许降级到基本 JSON 解析
- 详细的错误上下文信息
- 改进的异常处理，避免程序崩溃
- 更友好的错误消息（中文）

### 测试框架

- 完整的测试套件（\`tests/\` 目录）
- pytest 配置（\`pytest.ini\`）
- 开发依赖（\`requirements-dev.txt\`）

## 版本历史

详见 [CHANGELOG.md](CHANGELOG.md)

### v1.3.0 (2025-11-06)

- 重大变更：命令行工具统一为 \`mcp\`，旧命令别名已移除
- 代码：\`bin/mcp\` 由 Bash 包装器替换为 Python 主 CLI
- 文档与脚本：全面改用 \`mcp\`

### v1.2.2 (2025-11-06)

- 行为变更：安装脚本默认不再自动同步/落地 MCP
- CLI：\`mcp\` 新增 \`-n/--dry-run\` 预览模式

### v1.2.1 (2025-11-04)

- 体验：安装脚本追加 npx 预热与 \`--probe\` 连通性探测
- 体检：\`mcp-check.sh\` 支持 \`--probe\`

## 架构图

项目包含架构图文件：\`docs/mcp-architecture.png\`

重新渲染（自动检测本地渲染器，优先 Mermaid CLI→PlantUML）：
```bash
bash scripts/render-diagrams.sh
```

详细说明见：\`docs/RENDER_DIAGRAMS.md\`

## 许可证

本项目采用 MIT 许可证。

## 贡献

欢迎提交 Issue 和 Pull Request！
