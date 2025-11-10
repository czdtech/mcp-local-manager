#!/usr/bin/env bash
set -euo pipefail

if ! command -v black >/dev/null 2>&1; then
  echo "[format] black 未安装，尝试: pip install -r requirements-dev.txt" >&2
  exit 1
fi

black mcp_cli "$@"

