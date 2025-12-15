# QUICKSTART（北极星路径）

目标：把“会配置 MCP”变成“敢用、用得稳”。

> 推荐只记 2 个入口：  
> - **喜欢界面**：`mcp ui`（列表 + 开关，实时生效）  
> - **喜欢命令**：`mcp onboard` → `mcp status` → `mcp doctor`

---

## 0) 前置（最少）

- 已安装 `python3`（建议 3.11+）
- 已安装 `node` / `npx`（若要使用 npx 启动的 MCP 服务）

---

## 1) 一键上手（推荐）

### Web UI（不想记命令就用它）

```bash
mcp ui
```

打开终端输出的本地链接后：选择目标客户端 → 拨动开关 → 立即写入；遇到异常看页面的“操作日志”和“提示框”。

### Cursor（推荐新手）

```bash
mcp onboard --client cursor --yes
mcp status cursor
mcp doctor --client cursor
```

### Claude

```bash
mcp onboard --client claude --preset claude-basic --yes
mcp status claude
mcp doctor --client claude
```

### VS Code

```bash
mcp onboard --client vscode-user --preset vscode-user-basic --yes
mcp status vscode
mcp doctor --client vscode
```

---

## 2) 常见增强

### 预览差异（不写入）

```bash
mcp onboard --client cursor --dry-run
```

### 加速启动（本地化 npx）

```bash
mcp onboard --client cursor --localize --yes
```

---

## 3) 什么时候用 `mcp run`？

当你需要“自选服务集合”或“非预设组合”时：

```bash
mcp run
```

---

## 4) 什么时候用 `scripts/mcp-check.sh`？

当你需要更深的本地体检（如更严格的对比、更多探测逻辑）：

```bash
bash scripts/mcp-check.sh --probe
```
