#!/usr/bin/env bash
set -euo pipefail

echo "[1/5] 检测系统与路径..."
OS="$(uname -s)"
if [[ "$OS" == "Darwin" ]]; then
  VSCODE_USER_DIR="$HOME/Library/Application Support/Code/User"
  VSCODE_INSIDERS_USER_DIR="$HOME/Library/Application Support/Code - Insiders/User"
else
  VSCODE_USER_DIR="$HOME/.config/Code/User"
  VSCODE_INSIDERS_USER_DIR="$HOME/.config/Code - Insiders/User"
fi
CURSOR_GLOBAL="$HOME/.cursor/mcp.json"
MCP_CENTRAL_DIR="$HOME/.mcp-central/config"
mkdir -p "$MCP_CENTRAL_DIR"

echo "[2/5] 探测 Node 可执行路径..."
NODE_BIN=""
if command -v node >/dev/null 2>&1; then
  NODE_BIN="$(dirname "$(command -v node)")"
elif [[ -d "$HOME/.nvm" ]]; then
  CAND=$(ls -1d "$HOME/.nvm/versions/node"/*/bin 2>/dev/null | tail -n1 || true)
  [[ -n "$CAND" ]] && NODE_BIN="$CAND"
fi
if [[ -z "$NODE_BIN" ]] && command -v brew >/dev/null 2>&1; then
  NODE_BIN="$(brew --prefix)/bin"
fi
if [[ -z "$NODE_BIN" ]]; then
  echo "未找到 node，请先安装（nvm 或 brew）。"; exit 1
fi
echo "NODE_BIN=$NODE_BIN"

echo "[3/5] 探测 Chromium/Chrome 可执行..."
CHROME_EXEC=""
if [[ "$OS" == "Darwin" ]]; then
  CFT="$HOME/Library/Application Support/chrome-for-testing/chrome-mac/Chromium.app/Contents/MacOS/Chromium"
  [[ -x "$CFT" ]] && CHROME_EXEC="$CFT"
  [[ -z "$CHROME_EXEC" && -x "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" ]] && CHROME_EXEC="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
else
  CFT="$HOME/.local/chrome-for-testing/chrome-linux/chrome"
  [[ -x "$CFT" ]] && CHROME_EXEC="$CFT"
  [[ -z "$CHROME_EXEC" && -x "/usr/bin/google-chrome" ]] && CHROME_EXEC="/usr/bin/google-chrome"
fi
if [[ -z "$CHROME_EXEC" ]]; then
  echo "未检测到 Chrome/Chromium，可先继续，Playwright 将尝试自带浏览器。"
fi
echo "CHROME_EXEC=${CHROME_EXEC:-'(未设置)'}"

echo "[4/5] 生成统一清单 ~/.mcp-central/config/mcp-servers.json ..."
LOG_DIR="$HOME/.mcp-central/logs"
mkdir -p "$LOG_DIR/playwright"
cat > "$MCP_CENTRAL_DIR/mcp-servers.json" <<JSON
{
  "version": "1.1.0",
  "description": "统一 MCP Server 配置",
  "servers": {
    "chrome-devtools": {
      "enabled": true,
      "type": "local",
      "command": "npx",
      "args": ["-y","chrome-devtools-mcp@latest"],
      "env": {
        "CHROME_DEVTOOLS_MCP_DISABLE_SANDBOX": "1",
        "CHROME_DEVTOOLS_MCP_EXTRA_ARGS": "--disable-dev-shm-usage --disable-gpu"
      }
    },
    "sequential-thinking": {
      "enabled": true,
      "type": "local",
      "command": "npx",
      "args": ["-y","@modelcontextprotocol/server-sequential-thinking@latest"]
    },
    "playwright": {
      "enabled": true,
      "type": "local",
      "command": "npx",
      "args": ["-y","@playwright/mcp@latest","--headless","--isolated","--no-sandbox","--output-dir","$LOG_DIR/playwright","--executable-path","${CHROME_EXEC}"]
    },
    "serena": {
      "enabled": true,
      "type": "local",
      "command": "${HOME}/.local/bin/serena",
      "args": ["start-mcp-server","--context","desktop-app","--enable-web-dashboard","false","--enable-gui-log-window","false"],
      "env": {}
    },
    "filesystem": {
      "enabled": true,
      "type": "local",
      "command": "npx",
      "args": ["-y","mcp-server-filesystem@latest","${HOME}/work","${HOME}/.mcp-central"]
    },
    "codex-cli": {
      "enabled": true,
      "type": "local",
      "command": "npx",
      "args": ["-y","@cexll/codex-mcp-server@latest"]
    },
    "context7": {
      "enabled": true,
      "type": "local",
      "command": "npx",
      "args": ["-y","@upstash/context7-mcp@latest"]
    }
  }
}
JSON

echo "[5/5] 同步并体检..."
DIR="$(cd "$(dirname "$0")/.." && pwd)"
python3 "$DIR/bin/mcp-auto-sync.py" sync
bash "$DIR/scripts/mcp-check.sh"

echo "完成。若结论为 OK，则可开始使用；若为 WARN/FAIL，请按提示项逐一处理。"
