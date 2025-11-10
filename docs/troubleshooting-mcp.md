# MCP 故障排查与最佳实践（mcp-local-manager）

面向使用本仓库统一管理本机 MCP 的团队，整理从“首次安装 → 多客户端落地 → 体检与联调”全过程中遇到的典型坑与标准做法。建议新同学先通读一遍，再按“标准流程”执行。

---

## 一、单一来源与体检（默认不自动同步）

- 单一来源
  - 路径：`~/.mcp-central/config/mcp-servers.json`
  - 作用：所有客户端配置均由此渲染“仅 MCP 段”，不会触碰其它设置。
- 安装与同步
  - 首次安装（macOS/Linux）：`bash scripts/install-mac.sh`（不落地 MCP，仅渲染统一清单与体检）
  - 推荐日常：使用 `mcp` 按需落地而非全量同步：
    - 查看某客户端集合：`mcp status codex` / `mcp status claude`
    - 仅对某个 CLI 下发：`mcp run --client claude --servers context7,serena`
    - 下发后直接启动：`mcp run --client claude --servers context7,serena -- claude`
    - 为 VS Code/Cursor 按需落地：`mcp run --client cursor --servers task-master-ai,context7` / `mcp run --client vscode-user --servers filesystem`
  - 可选脚本路径：`bash scripts/mcp-sync.sh` → `bash scripts/mcp-check.sh`（仅当你需要一次性全量落地时使用）
  - 每次落地前，脚本会生成时间戳备份（`*.YYYYMMDD_HHMMSS.backup`）。
- 体检脚本改进点（已内置在本仓库）
  - Codex TOML 兼容：缺少 Python 3.11 的 `tomllib` 时，使用轻量解析器回退，仅读取 `[mcp_servers.*]` 与 `.env` 段。
  - Claude 注册表解析：自动适配 `claude mcp list` 输出（无 `--json` 也能解析），且延长超时，减少误报；当文件端已完整覆盖时，不再因注册表缺项告警。
  - 默认全部启用：中央清单未显式 `enabled: false` 的服务均视为启用；是否真正“加载”，由你对目标 CLI/IDE 的落地决定。

---

## 二、命名与版本规范

- 统一命名（小写-连字符）
  - 例如：`sequential-thinking`、`task-master-ai`、`chrome-devtools`、`context7`、`playwright`、`filesystem`、`serena`
  - 常见历史别名：`sequentialthinking`、`taskmaster`、`Playwright`（首字母大写）——请移除。
- 版本与调用
  - 统一采用显式最新版：优先 `npx -y <package>@latest`，便于持续获取更新。
  - 避免 wrappers（如 `~/.mcp/bin/*`），优先官方包或本地二进制。
  - 本项目基线（可按需微调）：
    - `codex-cli`：`npx -y @cexll/codex-mcp-server@latest`
    - `chrome-devtools`：`npx -y chrome-devtools-mcp@latest`
    - `context7`：`npx -y @upstash/context7-mcp@latest`
    - `filesystem`：`npx -y mcp-server-filesystem@latest`
    - `sequential-thinking`：`npx -y @modelcontextprotocol/server-sequential-thinking@latest`
    - `playwright`：`npx -y @playwright/mcp@latest -- --browser chrome`（根据需要追加参数）

### Chrome DevTools（npx 最新版）

- 使用 npx：`npx -y chrome-devtools-mcp@latest`
- 可选本地安装：`npm i -g chrome-devtools-mcp@latest`
- 一般无需为 npx 配置 PATH/npm_config_prefix 等环境变量；仅在特殊场景（权限/企业镜像）下按需设置。
- 验证
  - `which chrome-devtools-mcp`、`chrome-devtools-mcp --help`
- 中央清单示例
  - `command: "npx"`
  - `args: ["-y","chrome-devtools-mcp@latest"]`
  - `env` 建议：
    - `CHROME_DEVTOOLS_MCP_DISABLE_SANDBOX=1`
    - `CHROME_DEVTOOLS_MCP_EXTRA_ARGS="--disable-dev-shm-usage --disable-gpu"`
- 注册表示例
  - Claude：
    - `claude mcp add --transport stdio chrome-devtools -e CHROME_DEVTOOLS_MCP_DISABLE_SANDBOX=1 -e CHROME_DEVTOOLS_MCP_EXTRA_ARGS='--disable-dev-shm-usage --disable-gpu' -- npx -y chrome-devtools-mcp@latest`
  - Droid：
    - `droid mcp add chrome-devtools "npx -y chrome-devtools-mcp@latest"`

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
- 配置文件（官方）：`~/.factory/mcp.json` 顶层 `mcpServers`，项内 `command`、可选 `args`、`env`，常见 `type: stdio`。
- 交互式 `/mcp` 与 `droid mcp add/remove` 操作同一注册表；通常文件更新会热加载，若未生效可重启会话。
- 本项目行为：`mcp run --client droid --servers ...` 将“先 remove 再 add”强制对齐注册表，并同步写入 `mcpServers`，与中央清单保持一致。
- 注册写法（CLI）：
  - `droid mcp add <name> "<command and args>" [--env KEY=VAL ...]`
  - 例如（npx 最新版）：
    - `droid mcp add playwright "npx -y @playwright/mcp@latest --headless --no-sandbox --browser chrome --output-dir ~/.mcp-central/logs/playwright"`
  - 可选环境（若 droid 找不到 npx 再考虑添加）：`--env PATH="/opt/node/bin:/usr/local/bin:/usr/bin:/bin"`

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
- 注册为：`npx -y @playwright/mcp@latest --headless --no-sandbox --browser chrome --output-dir ~/.mcp-central/logs/playwright`
- 避免 `--executable-path` 路径差异；必要时显式注入 PATH。
- 目录需存在：`~/.mcp-central/logs/playwright`（脚本已自动创建）。
- 需要诊断时追加：`--save-session --save-trace`，产物落盘便于分析。

自检命令（5 秒采样终止，仅验证能正常进入“等待连接”状态）：
```bash
npx -y @playwright/mcp@latest \
  --headless --no-sandbox --browser chrome \
  --output-dir ~/.mcp-central/logs/playwright
# 无输出属正常；Ctrl+C 结束
```

---

## 五、常见坑与修复（含 mcp 提示）

- `unknown option '-y'`（droid）：未使用 `--` 分隔，`-y` 被 droid 自身解析。
- `No module named 'tomllib'`：体检脚本已内置回退；或升级到 Python 3.11+。
- `缺少已注册`（Claude）：若“文件为主”，可忽略；或用 `claude mcp add` 兜底补齐。
- VS Code/Kilo/Cursor 不生效：路径写错或放入 `settings.json`；改为其 MCP 专用文件。
- 名称重复/大小写不一致：统一成小写-连字符；清理历史注册项（Claude/Droid）。
- PATH/二进制差异：必要时在 `env.PATH` 显式包含 Node bin 与系统路径；优先绝对路径。
- 只想查看单一客户端状态：用 `mcp status codex|claude|vscode|cursor`，而不是读中央清单。
- 启动前只加载少量 MCP：用 `mcp run --client <cli> --servers <list> -- <启动命令>`。

提示（dry-run 预览变更）：
- 在 `mcp` 任意子命令追加 `-n/--dry-run` 可只预览将发生的写入/注册/启动动作，不做任何修改。
- 示例：`mcp run -n --client claude --servers context7,serena`、`mcp run -n --client claude --servers context7,serena -- claude`。

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
- 改为：`npx -y @playwright/mcp@latest -- --browser chrome`（必要时追加参数）
- 若环境找不到 npx，再考虑显式 `--env PATH=...` 或绝对路径。

4) 命名与版本一致性
- 统一命名（小写-连字符）；Chrome DevTools 推荐使用 npx 或安装最新版 `npm i -g chrome-devtools-mcp@latest`
- Codex MCP 仅保留一个：`codex-cli => npx -y @cexll/codex-mcp-server`

---

## 七、命令速查（示例）

- Claude（注册；一般无需传 PATH）
```bash
claude mcp add --transport stdio codex-cli -- npx -y @cexll/codex-mcp-server
claude mcp remove codex-cli -s local  # 作用域示例
```

- Droid（注册）
```bash
# DevTools（npx 最新版）
droid mcp add chrome-devtools "npx -y chrome-devtools-mcp@latest"

# 可选：传环境参数（与中央清单保持一致）
# --env CHROME_DEVTOOLS_MCP_DISABLE_SANDBOX=1 \
# --env CHROME_DEVTOOLS_MCP_EXTRA_ARGS='--disable-dev-shm-usage --disable-gpu'

# Playwright（npx 最新版）
droid mcp add playwright "npx -y @playwright/mcp@latest --headless --no-sandbox --browser chrome --output-dir ~/.mcp-central/logs/playwright"
```

- VS Code / Cursor / Kilo 文件位置
  - VS Code：`~/Library/Application Support/Code/User/mcp.json`（Insiders 路径不同）
  - Cursor：`~/.cursor/mcp.json`
  - Kilo：`~/Library/Application Support/Code/User/globalStorage/kilocode.kilo-code/settings/mcp_settings.json`

---

## 八、实战踩坑录（2025-11-05）

本仓库在一次“旧版 → 最新版”的现场升级过程中，暴露出若干典型问题，已在脚本与 CLI 中修复或形成标准操作。记录如下，便于新人“一次成功”。

- Claude 项目级覆盖导致“清不干净”
  - 现象：`mcp status` 显示 `Claude(register)` 仍有某项（如 `codex-cli`），`claude mcp list` 也显示 Connected；但已清空 `~/.claude/settings.json` 与注册表。
  - 根因：`~/.claude.json` 内 `projects.*.mcpServers` 会覆盖/合并显示注册表与文件端。
  - 处置：清空 `~/.claude.json` 中所有 `projects.*.mcpServers`；已将此步骤自动化到 `scripts/onboard-cursor-minimal.sh`，并增强 `mcp` 的注册表读取稳健性（延长超时、合并 stdout+stderr）。

- 误用系统 `cc` 导致“连通性探测”异常输出
  - 现象：体检脚本打印 `[cc] Claude Code: cc mcp list`，随后出现 clang 报错。
  - 根因：`cc` 为系统 C 编译器，非 Claude CLI。早期脚本误用了 `cc` 名称。
  - 处置：`scripts/mcp-check.sh` 已更正为 `claude mcp list`，不再触发编译器。

- `serena` 路径与中央清单不一致
  - 现象：中央清单默认使用 `~/.local/bin/serena`，本机真实在 `/usr/local/bin/serena`，体检 FAIL。
  - 处置：探测实际路径后写回中央清单并同步；建议团队预置一条“探测并回写”的校准脚本或在安装手册明确路径。

- `task-master-ai` 在 Gemini 端偶发 Disconnected
  - 建议：采用“混合策略”——仅在 Gemini 端切为全局二进制直连（`npm i -g task-master-ai@latest`，将 Gemini 的 `command` 改为 `task-master-ai`、`args: []`）。体检已放宽该差异校验，不会告警。

- 新人一次成活的最小落地
  - 方案：运行 `bash scripts/onboard-cursor-minimal.sh`，仅为 Cursor 启用 `context7` 与 `task-master-ai`，其它 CLI/IDE 保持“裸奔”。
  - 复验：`mcp status cursor` 应仅列出上述两项；`claude mcp list` 应为空。

## 八、结语

- “单一来源 + 仅写 MCP 段 + 体检回路”能极大减少漂移与重复劳动。
- 若遇到复杂兼容性问题（尤其是 Playwright/浏览器路径），优先使用“本地二进制 + `--browser chrome` + 显式 PATH + 绝对路径”。
- 欢迎把更多踩坑补充到本文档，保持团队知识同步。

***

最后更新：以实际脚本为准（`scripts/install-mac.sh`、`scripts/mcp-sync.sh`、`scripts/mcp-check.sh`）。

---

## 九、npx @latest 常见问题与修复（task-master-ai）

症状：在 Cursor 将 `task-master-ai` 配置为 `npx -y task-master-ai@latest` 时，日志报错：

```
Error [ERR_MODULE_NOT_FOUND]: Cannot find package '@inquirer/search' ...
```

原因：npx 的临时安装/缓存未完整解出最新版的 ESM 依赖（`@inquirer/search` 等），导致运行时解析失败。旧缓存版本（不写 `@latest`）可能不触发此问题。

推荐修复（方案A，保持官方最小配置）：

1) 清理缓存（用户目录下的 npx/npm 缓存）：

```
npm cache clean --force
rm -rf ~/.npm/_npx/*
```

2) 预热（可选）：手动拉取最新版以填充缓存（首次可能较慢）：

```
npx -y task-master-ai@latest --help  # 或 --version
```

3) 恢复 Cursor 的官方最小配置：

```
"command": "npx",
"args": ["-y", "task-master-ai@latest"]
```

4) 在 Cursor 的 MCP 面板对 `task-master-ai` 执行“关→开”，或重启 Cursor。

备选（方案B，更快更稳，仍保持最新版）：

- 全局安装：`npm i -g task-master-ai@latest`
- Cursor 改为直连二进制：`"command": "task-master-ai"`, `"args": []`
- 后续升级：周期性执行 `npm i -g task-master-ai@latest`

混合策略建议：
- 优先使用 npx（配置简单、始终最新）。
- 针对个别客户端/服务（如 Gemini + task-master-ai）若出现 Disconnected 或依赖解析异常，切换为全局二进制直连；其它仍保留 npx，不必“一刀切”。

提示：
- 请至少配置一个可用 Provider 的 API Key（如 `OPENAI_API_KEY` 或 `ANTHROPIC_API_KEY`），否则最新版可能直接退出。
- Node v22 出现 `punycode` 的 DeprecationWarning 可忽略。
- 网络镜像导致的解析/超时问题，可清缓存后重试或先行“预热”。
