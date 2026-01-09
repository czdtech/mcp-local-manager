#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
用法：bash scripts/qa.sh [--install] [--fast] [--fix]

用途：本地质检入口（不依赖线上 CI）。默认执行：ruff → black --check → pytest → 配置验证 → CLI 冒烟。

选项：
  --install   安装/更新开发依赖（requirements-dev.txt）
  --fast      跳过 pytest（仅做静态检查 + 验证脚本 + CLI 冒烟）
  --fix       尝试自动修复（ruff --fix + black 格式化；会改动代码）
  -h, --help  显示帮助
EOF
}

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

log() { printf "[qa] %s\n" "$*"; }
warn() { printf "[qa][WARN] %s\n" "$*" >&2; }
die() { printf "[qa][ERR] %s\n" "$*" >&2; exit 2; }

INSTALL=0
FAST=0
FIX=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --install) INSTALL=1; shift ;;
    --fast) FAST=1; shift ;;
    --fix) FIX=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) die "未知参数：$1（使用 -h 查看帮助）" ;;
  esac
done

if ! command -v python3 >/dev/null 2>&1; then
  die "缺少 python3，请先安装 Python 3.11+"
fi

PY="python3"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PY="$ROOT/.venv/bin/python"
fi

if [[ "$INSTALL" -eq 1 ]] && [[ ! -x "$ROOT/.venv/bin/python" ]]; then
  log "创建虚拟环境：.venv（避免 PEP 668 的系统 Python 限制）..."
  python3 -m venv .venv
  PY="$ROOT/.venv/bin/python"
fi

log "Python: $("$PY" --version 2>/dev/null || true)"

if [[ "$INSTALL" -eq 1 ]]; then
  log "安装开发依赖（requirements-dev.txt）..."
  "$PY" -m pip install --upgrade pip
  "$PY" -m pip install -r requirements-dev.txt
fi

need_mod() {
  local mod="$1"
  "$PY" - <<PY >/dev/null 2>&1
import importlib
importlib.import_module("$mod")
PY
}

require_mod() {
  local mod="$1"
  local err="$2"
  if ! need_mod "$mod"; then
    die "$err"
  fi
}

require_mod ruff "缺少依赖：ruff（先运行：bash scripts/qa.sh --install）"
require_mod black "缺少依赖：black（先运行：bash scripts/qa.sh --install）"
if [[ "$FAST" -eq 0 ]]; then
  require_mod pytest "缺少依赖：pytest（先运行：bash scripts/qa.sh --install 或使用 --fast）"
fi

if [[ "$FIX" -eq 1 ]]; then
  log "ruff（自动修复）..."
  "$PY" -m ruff check mcp_cli --fix
  log "black（格式化）..."
  "$PY" -m black mcp_cli
else
  log "ruff（只检查）..."
  "$PY" -m ruff check mcp_cli
  log "black（只检查）..."
  "$PY" -m black --check mcp_cli
fi

if [[ "$FAST" -eq 0 ]]; then
  log "pytest（全量）..."
  "$PY" -m pytest -q
else
  warn "跳过 pytest（--fast）"
fi

log "配置验证（sample config）..."
"$PY" bin/mcp_validation.py config/mcp-servers.sample.json >/dev/null

log "CLI 冒烟（--help）..."
"$PY" bin/mcp --help >/dev/null

log "完成 ✅"
