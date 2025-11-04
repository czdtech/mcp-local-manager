#!/usr/bin/env bash
set -euo pipefail

echo "[health] Claude CLI"
if command -v claude >/dev/null 2>&1; then
  claude mcp list || true
else
  echo "[health] claude 不在 PATH，跳过"
fi

echo
echo "[health] Gemini CLI"
if command -v gemini >/dev/null 2>&1; then
  gemini mcp list || true
else
  echo "[health] gemini 不在 PATH，跳过"
fi
