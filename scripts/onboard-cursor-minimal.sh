#!/usr/bin/env bash
set -euo pipefail

# 目标：一键为新人完成“最小落地”
# - 仅 Cursor 启用：context7 + task-master-ai
# - 其它 CLI/IDE 全部裸奔（清空文件端、注册表与项目级覆盖）

HERE="$(cd "$(dirname "$0")/.." && pwd)"
export PATH="$HOME/.local/bin:$PATH"

echo "[1/4] 链接 mcp 到 ~/.local/bin ..."
mkdir -p "$HOME/.local/bin"
ln -sf "$HERE/bin/mcp" "$HOME/.local/bin/mcp"
command -v mcp >/dev/null 2>&1 || { echo "mcp 未就绪"; exit 1; }

echo "[2/4] Cursor 最小落地（无需手写 central）..."
mcp onboard --client cursor --preset cursor-minimal --yes

echo "[3/4] 清空其它 CLI/IDE（裸奔）..."
mcp clear \
  --client claude \
  --client codex \
  --client gemini \
  --client iflow \
  --client droid \
  --client vscode-user \
  --client vscode-insiders \
  --yes || true

echo "[4/4] 复验 ..."
mcp status --client cursor
mcp status --client claude-file
mcp status --client claude-reg
mcp status --client codex
echo ""
echo "完成：仅 Cursor 启用 context7+task-master-ai，其它均裸奔。"
