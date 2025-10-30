#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "$0")/.." && pwd)"
python3 "$DIR/bin/mcp-auto-sync.py" sync
echo "MCP 同步完成。"

