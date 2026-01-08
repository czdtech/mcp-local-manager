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
不想记命令：直接 `mcp ui`（Web 界面：列表 + 开关，实时落地）；
新手：优先用 `mcp onboard` 一键上手；遇到问题先跑 `mcp doctor`；
进阶：`mcp run` / `mcp clear` / `mcp localize` / `mcp central`；
只读：`mcp status` / `mcp check`。
```

### 新手路径（场景包，数字即用）
- `mcp onboard` → 选择客户端 → 选择预设包（回车=推荐默认包）→ 一次确认完成下发。
- 想要非交互：`mcp onboard --client cursor --yes`（可先 `--dry-run` 预览差异）。
- 诊断一把梭：`mcp doctor --client cursor`（central 是否健康、目标端是否漂移、下一步怎么做）。
- 需要清空：`mcp clear --client claude`（或交互选择）；支持 `--dry-run` 预览、`--yes` 自动确认。
- 加速启动：`mcp localize` 一键本地化 npx 服务，`--upgrade` 升级本地版本，`--prune` 清理本地镜像；也可以在单次下发时使用 `mcp run --localize ...` 只为本次选择的 npx 服务做本地安装。

### 交互预览与确认

所有写入操作在交互步骤中提供“变更摘要 + 最终确认”，不再提供全局 `-n/--dry-run` 参数；需要预览时，请在具体子命令上使用 `--dry-run`（如 `mcp run --dry-run` / `mcp clear --dry-run`）。

### 新人一键最小落地（可选，推荐）

```bash
# 仅为 Cursor 启用 context7 + task-master-ai，其它 CLI/IDE 保持"裸奔"
mcp onboard --client cursor --yes
# 复验：
mcp status cursor
```

更多文档：
- `docs/README.md`：文档索引（先看这个）
- `docs/QUICKSTART.md`：北极星路径（新手只看这个）
- `docs/mcp.md`：命令参考（全量选项）
- `docs/troubleshooting-mcp.md`：故障排查与最佳实践

## 核心理念

- **统一来源**：\`~/.mcp-central/config/mcp-servers.json\`
- **仅改 MCP 段**：不同目标只写入各自 MCP 部分（如 Codex 的 \`[mcp_servers.*]\`、Gemini 的 \`mcpServers\` 等），不触碰其它设置
- **Claude Code**：注册表为主（\`claude mcp add/remove -s user\` 写入 \`~/.claude.json\` 顶层 \`mcpServers\`）；同时镜像写入 \`~/.claude/settings.json\` 的 \`mcpServers\`
- **默认全部启用**：清单里未显式写 \`enabled: false\` 的服务都视为启用；是否真正"加载"，由你对某个 CLI/IDE 的落地选择决定
  - 行为约束：\`mcp run\` 仅允许下发“已启用”的服务；\`enabled: false\` 的条目会被跳过/拒绝（需先在 central 启用）
  - 状态基线：\`mcp status\` 的 on/off 以“已启用”集合为基线；若目标端仍配置了 central 已禁用的服务，会提示告警
- **安装默认不落地**：\`scripts/install-mac.sh\` 不会执行同步，需使用 \`mcp\` 按需选择后落地

## 推荐基线

- Node 生态 MCP 一律使用 \`npx -y <package>@latest\`，便于获得上游修复（如 \`task-master-ai\`）
- 仅 \`serena\` 走本地二进制（\`~/.local/bin/serena\`）
- \`augment-context-engine\` 需要用户自行安装 \`auggie\` 命令行工具（https://github.com/augmentcode/augment-context-engine），并建议在 central 使用 \`client_overrides\` 为 Cursor 注入 \`WORKSPACE_FOLDER_PATHS\`（见 \`config/mcp-servers.sample.json\`）
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
# 1. 克隆项目
git clone <repository-url>
cd mcp-local-manager

# 2. 运行安装脚本
bash scripts/install-mac.sh

# 3. 配置 PATH（二选一）
# 方式 A：添加到 shell 配置文件（推荐）
echo "export PATH=\"$(pwd)/bin:\$PATH\"" >> ~/.zshrc
source ~/.zshrc

# 方式 B：创建全局符号链接
sudo ln -sf "$(pwd)/bin/mcp" /usr/local/bin/mcp

# 4. 验证安装
mcp --help
```

脚本会自动：
- 生成/更新统一清单（不对各客户端落地）
- 可选预热 npx 缓存（减少首次拉包失败）
- 运行轻量体检（检查关键路径与配置文件存在性）；如需深度体检（连通性探测等），请执行 `scripts/mcp-check.sh`

**注意**：如果你将项目克隆到其他位置，请将上述 PATH 中的路径替换为实际的项目路径。

### 统一清单位置

- 脚本会生成/使用：\`~/.mcp-central/config/mcp-servers.json\`（安装不落地）
- 你也可以用本仓库的 \`config/mcp-servers.sample.json\` 作参考，然后复制到 \`~/.mcp-central/config/mcp-servers.json\` 后再执行同步

### 目标落地位置（仅改 MCP 部分）

- **Codex**: \`~/.codex/config.toml\` - 仅 \`[mcp_servers.*]\` 与 \`*.env\`
- **Gemini**: \`~/.gemini/settings.json\` - 仅 \`mcpServers\` + \`mcp.allowed\`
- **iFlow**: \`~/.iflow/settings.json\` - 仅 \`mcpServers\`
- **Claude Code**: \`~/.claude.json\` - 通过 \`claude mcp add/remove -s user\` 落地（全局）；同时镜像写入 \`~/.claude/settings.json\` 的 \`mcpServers\`
- **Droid**: \`~/.factory/mcp.json\` - 仅 \`mcpServers\`；在 `mcp run` 的交互中选择 Droid 后，会对所选集合执行“remove → add”强制对齐注册表。
- **Cursor**: \`~/.cursor/mcp.json\` - 仅 \`mcpServers\`
- **VS Code**: CLI 会按平台自动选择路径：
  - macOS: \`~/Library/Application Support/Code/User/mcp.json\` 与 \`~/Library/Application Support/Code - Insiders/User/mcp.json\`
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

### 交互入口

`mcp run` / `mcp central` 进入交互式选择与确认流程。

### run

运行后按提示选择客户端与要启用的 MCP 集合；可选输入要启动的命令，或直接回车跳过。

### check

只读健康检查：

```bash
mcp check
```

说明：`mcp check` 为轻量只读体检；深度体检请运行 `scripts/mcp-check.sh`。

### clear

交互/非交互清理各客户端 MCP 配置（含 Claude 注册表；写入前有摘要与确认）。

说明：
- 支持 `--client` 多选、`--dry-run` 预览、`--yes` 自动确认。
- 会对相关配置文件做单槽备份（`.backup`），便于 `mcp undo` 回滚；覆盖范围：Claude(文件+注册表)、Codex、Gemini、iFlow、Droid、Cursor、VS Code(User/Insiders)。

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

注意：本项目已提供最小 GitHub Actions CI（ruff/black/pytest），但仍建议你在本地跑一遍 `pytest -q` 作为最终确认。

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

#### 2. task-master-ai MCP 启动超时/握手失败

**症状**：`task-master-ai` 在 Cursor/Gemini 等客户端显示 `⚠ MCP client ... failed to start`、`handshaking with MCP server failed: connection closed: initialize response`，或一直停留在“加载工具/0 tools enabled”。

**根因**：官方默认会一次性加载 36 个工具（约 2.1 万 tokens），且 MCP 默认仅等待 60 秒。一旦 `npx` 首次安装过慢或工具初始化超过 60 秒，客户端就会直接断开握手。

**修复步骤（摘自 Task Master 官方配置文档《Configuration》→“MCP Tool Loading Configuration”与“MCP Timeout Configuration”）：**

1. 在中央清单或客户端配置中为 `task-master-ai` 增加 `"timeout": 300`（单位秒，可按需调到 600），例如：
   ```jsonc
   "task-master-ai": {
     "command": "npx",
     "args": ["-y", "task-master-ai@latest"],
     "timeout": 300,
     "env": {
       "TASK_MASTER_TOOLS": "standard"
     }
   }
   ```
2. 视项目体量将 `TASK_MASTER_TOOLS` 设为 `standard`（15 个常用工具，≈10k tokens）或 `core/lean`（7 个核心工具，≈5k tokens），可显著缩短初始化时间。
3. 通过 `mcp run` 重新对目标客户端落地配置，或在 Cursor MCP 面板关闭/再开启 `task-master-ai`。
4. 如仍报错，执行 `npx -y task-master-ai@latest --version` 确认最新版是否能本地启动，并排查 API Key 是否至少配置一项。

> 以上 timeout / 工具集开关均由 task-master 官方提供，详见 https://docs.task-master.dev/（若页面返回 404，可参阅仓库 `docs/configuration.md` 同步内容）。本项目提供 `mcp central doctor` 体检命令，会对 `task-master-ai` 条目的 `timeout` 与 `TASK_MASTER_TOOLS` 做专项检查：缺少/过小/设为 `all` 时会标记为 failed 并给出修复建议。

#### 3. Claude 注册表清理

若"文件为主"策略下仍有注册表残留：

```bash
claude mcp remove <name> -s local
claude mcp remove <name> -s user
```

#### 4. VS Code/Cursor 不生效

- 确保使用专用 MCP 文件：
  - VS Code: \`~/.config/Code/User/mcp.json\`（顶层 \`servers\`）
  - Cursor: \`~/.cursor/mcp.json\`（顶层 \`mcpServers\`）
- 不要把 MCP 配置放入 \`settings.json\`

#### 5. 一键失败排查

```bash
# 执行 npx 预热
bash scripts/npx-prewarm.sh

# 运行轻量体检（如需深度体检请执行 scripts/mcp-check.sh）
mcp check

# 若仅某一端/某一服务连不上：只切换该服务为全局二进制
```

### 安全迁移

已有配置不一致时的推荐流程：

1. 先运行 `scripts/mcp-check.sh` 只读体检，记录现状
2. 准备/确认 `~/.mcp-central/config/mcp-servers.json`（统一清单，未显式 false 的都视为启用）
4. 启动某个 CLI 前，用 `mcp run` 精确下发所需 MCP
5. 如需全量改写各目标，也可用 `scripts/mcp-sync.sh`

**注意事项**：
- 只改 MCP：本项目所有脚本都"仅替换 MCP 配置段"，不会触碰其它设置
- 自动备份：每个目标文件仅保留一个 \`*.backup\`（单槽覆盖），可用 \`mcp undo <backup>\` 回滚
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

本 README 仅描述当前版本的行为和用法；如果需要查看完整的版本演进与历史变更，请参考 [CHANGELOG.md](CHANGELOG.md)。

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
