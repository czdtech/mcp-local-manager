#!/usr/bin/env bash
set -euo pipefail

if ! command -v ruff >/dev/null 2>&1; then
  echo "[lint] ruff 未安装，尝试: pip install -r requirements-dev.txt" >&2
  exit 1
fi

ruff check mcp_cli "$@"

