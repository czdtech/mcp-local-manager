# MCP 故障排查与最佳实践（mcp-local-manager）

面向使用本仓库统一管理本机 MCP 的团队，整理从“首次安装 → 多客户端落地 → 体检与联调”全过程中遇到的典型坑与标准做法。建议新同学先通读一遍，再按“标准流程”执行。

---

## 一、单一来源与体检

- 单一来源
  - 路径：`~/.mcp-central/config/mcp-servers.json`
  - 作用：所有客户端配置均由此渲染“仅 MCP 段”，不会触碰其它设置。
- 安装与同步
  - 首次安装（macOS）：`bash scripts/install-mac.sh`
  - 修改清单后：`bash scripts/mcp-sync.sh` → `bash scripts/mcp-check.sh`
  - 每次落地前，脚本会生成时间戳备份（`*.YYYYMMDD_HHMMSS.backup`）。
- 体检脚本改进点（已内置在本仓库）
  - Codex TOML 兼容：缺少 Python 3.11 的 `tomllib` 时，使用轻量解析器回退，仅读取 `[mcp_servers.*]` 与 `.env` 段。
  - Claude 注册表解析：自动适配 `claude mcp list` 输出（无 `--json` 也能解析），且延长超时，减少误报。

---

## 二、命名与版本规范

- 统一命名（小写-连字符）
  - 例如：`sequential-thinking`、`task-master-ai`、`chrome-devtools`、`context7`、`playwright`、`filesystem`、`serena`
  - 常见历史别名：`sequentialthinking`、`taskmaster`、`Playwright`（首字母大写）——请移除。
- 版本与调用
  - 避免 `@latest` 带来不兼容；能固定则固定：`chrome-devtools-mcp@0.9.0`。
  - 避免 wrappers（如 `~/.mcp/bin/*`），优先“本地二进制或固定版本 npx”。
  - 本项目最终基线（可按需微调）：
    - `codex-cli`：`npx -y @cexll/codex-mcp-server`（只保留一个 Codex 实例）
    - `chrome-devtools`：`chrome-devtools-mcp`（本地可执行，推荐；需先全局安装）
    - 其它常用：优先本地二进制（`context7-mcp`、`mcp-server-filesystem`、`mcp-server-sequential-thinking`、`serena`）
    - `playwright`：本地二进制 + `--browser chrome`（详见下一节）

### Chrome DevTools 本地部署（推荐）

- 全局安装/锁定版本
  - 安装最新版：`npm i -g chrome-devtools-mcp`
  - 指定版本：`npm i -g chrome-devtools-mcp@0.9.0`
- 验证
  - `which chrome-devtools-mcp`、`chrome-devtools-mcp --help`
- 中央清单示例
  - `command: "chrome-devtools-mcp"`
  - `args: []`
  - `env` 建议：
    - `CHROME_DEVTOOLS_MCP_DISABLE_SANDBOX=1`
    - `CHROME_DEVTOOLS_MCP_EXTRA_ARGS="--disable-dev-shm-usage --disable-gpu"`
- 注册表示例
  - Claude：
    - `claude mcp add --transport stdio chrome-devtools -e CHROME_DEVTOOLS_MCP_DISABLE_SANDBOX=1 -e CHROME_DEVTOOLS_MCP_EXTRA_ARGS='--disable-dev-shm-usage --disable-gpu' -- chrome-devtools-mcp`
  - Droid：
    - `droid mcp add --type stdio chrome-devtools -- chrome-devtools-mcp`

---

## 三、各客户端落地要点

### 1) Claude（文件为主 + 注册表兜底）
- 文件：`~/.claude/settings.json` 顶层 `mcpServers`（推荐主来源）。
- 注册表：`claude mcp add/remove` 会写入内部“注册表”，`/mcp` 会合并显示它与文件配置。
- 清理重复与历史别名（支持作用域）：
  - 移除：`claude mcp remove <name> -s local`、`-s user`（或不加 `-s` 逐级尝试）。
- 注册写法（务必注意 `-e ... --` 顺序）：
  - `claude mcp add --transport stdio <name> -e KEY=VAL ... -- <command> <args>`

### 2) Droid（factory.ai CLI）
- 交互式 `/mcp` 读取的是“注册表”，仅有 `~/.factory/mcp.json` 或项目级 `.factory/mcp.json` 不足以在会话内显示。
- 注册写法（务必使用 `--` 分隔）：
  - `droid mcp add --type stdio <name> -- <command> <args>`
  - 例如（本地二进制）：
    - `droid mcp add --type stdio playwright -- /Users/<you>/.nvm/versions/node/vXX/bin/mcp-server-playwright --headless --no-sandbox --browser chrome --output-dir ~/.mcp-central/logs/playwright`
  - 传递环境：`--env PATH="/opt/node/bin:/usr/local/bin:/usr/bin:/bin"`
- 配置文件（兜底来源）
  - 全局：`~/.factory/mcp.json`
  - 项目级：`.factory/mcp.json`

### 3) VS Code / Cursor
- VS Code：
  - 稳定用法：`~/Library/Application Support/Code/User/mcp.json` 顶层 `servers`（Insiders 路径不同）。
  - 不要把 MCP 放进 `settings.json`，否则可能重复或不生效。
- Cursor：`~/.cursor/mcp.json` 顶层 `mcpServers`。

### 4) Kilo Code（VS Code 插件）
- 全局文件：`~/Library/Application Support/Code/User/globalStorage/kilocode.kilo-code/settings/mcp_settings.json`
- 项目级（可选）：`.kilocode/mcp.json`
- 结构：顶层 `mcpServers` 映射，项内 `command`、可选 `args`、`env`、`disabled`。

### 5) Codex（TOML）
- 文件：`~/.codex/config.toml` 的 `[mcp_servers.*]` 与 `*.env` 子表。
- 若本机 Python < 3.11：体检脚本已内置轻量解析，无需安装 `tomllib`。

---

## 四、Playwright 专项排障

常见现象与原因：
- “命令无输出一直卡着”并非错误：STDIO 服务器会在前台等待 MCP 客户端握手，通常没有 stdout/stderr 输出。
- “Disconnected”：多由可执行路径/参数/环境导致，非服务本体 bug。

推荐做法（本地二进制 + 浏览器通道）：
- 注册为：`mcp-server-playwright --headless --no-sandbox --browser chrome --output-dir ~/.mcp-central/logs/playwright`
- 避免 `--executable-path` 路径差异；必要时显式注入 PATH。
- 目录需存在：`~/.mcp-central/logs/playwright`（脚本已自动创建）。
- 需要诊断时追加：`--save-session --save-trace`，产物落盘便于分析。

自检命令（5 秒采样终止，仅验证能正常进入“等待连接”状态）：
```bash
/Users/<you>/.nvm/versions/node/vXX/bin/mcp-server-playwright \
  --headless --no-sandbox --browser chrome \
  --output-dir ~/.mcp-central/logs/playwright
# 无输出属正常；Ctrl+C 结束
```

---

## 五、常见坑与修复

- `unknown option '-y'`（droid）：未使用 `--` 分隔，`-y` 被 droid 自身解析。
- `No module named 'tomllib'`：体检脚本已内置回退；或升级到 Python 3.11+。
- `缺少已注册`（Claude）：若“文件为主”，可忽略；或用 `claude mcp add` 兜底补齐。
- VS Code/Kilo/Cursor 不生效：路径写错或放入 `settings.json`；改为其 MCP 专用文件。
- 名称重复/大小写不一致：统一成小写-连字符；清理历史注册项（Claude/Droid）。
- PATH/二进制差异：必要时在 `env.PATH` 显式包含 Node bin 与系统路径；优先绝对路径。

---

## 六、标准流程（Runbook）

1) 体检 → 同步 → 再体检
- `bash scripts/mcp-check.sh`
- `bash scripts/mcp-sync.sh`（包含 droid 自动重注册 + 目标端 env 精简；未安装 droid 时自动跳过）
- `bash scripts/mcp-check.sh`

2) 清理历史别名与重复注册
- Claude：`claude mcp remove <name> -s local|user`
- Droid：`droid mcp remove <name>`；确保后续统一用 `--` 分隔注册命令与参数。

(已自动化) mcp-sync：
- 同步后自动为 droid 批量重注册（/mcp 面板读取注册表）
- 同步后自动精简目标端 env（清除冗长 PATH，仅 DevTools 保留必要键）

3) Playwright 稳定化（如断开）
- 改为：本地二进制 + `--browser chrome`（无需 `--executable-path`）
- 显式 `env.PATH` / 绝对路径 / 创建 `~/.mcp-central/logs/playwright`

4) 命名与版本一致性
- 统一命名（小写-连字符）；Chrome DevTools 推荐本地安装，如需锁定可用 `npm i -g chrome-devtools-mcp@0.9.0`
- Codex MCP 仅保留一个：`codex-cli => npx -y @cexll/codex-mcp-server`

---

## 七、命令速查（示例）

- Claude（注册，注意 `-e` 在 `--` 之前）
```bash
claude mcp add --transport stdio codex-cli \
  -e PATH="$PATH" -- npx -y @cexll/codex-mcp-server
claude mcp remove codex-cli -s local  # 作用域示例
```

- Droid（注册，必须用 `--` 分隔）
```bash
# DevTools 本地二进制
droid mcp add --type stdio chrome-devtools -- \
  chrome-devtools-mcp

# 可选：传环境参数（与中央清单保持一致）
# --env CHROME_DEVTOOLS_MCP_DISABLE_SANDBOX=1 \
# --env CHROME_DEVTOOLS_MCP_EXTRA_ARGS='--disable-dev-shm-usage --disable-gpu'

# Playwright 本地二进制 + 浏览器通道（推荐）
droid mcp add --type stdio playwright -- \
  /Users/<you>/.nvm/versions/node/vXX/bin/mcp-server-playwright \
  --headless --no-sandbox --browser chrome \
  --output-dir ~/.mcp-central/logs/playwright
```

- VS Code / Cursor / Kilo 文件位置
  - VS Code：`~/Library/Application Support/Code/User/mcp.json`（Insiders 路径不同）
  - Cursor：`~/.cursor/mcp.json`
  - Kilo：`~/Library/Application Support/Code/User/globalStorage/kilocode.kilo-code/settings/mcp_settings.json`

---

## 八、结语

- “单一来源 + 仅写 MCP 段 + 体检回路”能极大减少漂移与重复劳动。
- 若遇到复杂兼容性问题（尤其是 Playwright/浏览器路径），优先使用“本地二进制 + `--browser chrome` + 显式 PATH + 绝对路径”。
- 欢迎把更多踩坑补充到本文档，保持团队知识同步。

***

最后更新：以实际脚本为准（`scripts/install-mac.sh`、`scripts/mcp-sync.sh`、`scripts/mcp-check.sh`）。

