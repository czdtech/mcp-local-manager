#!/usr/bin/env bash
set -euo pipefail

# 自动渲染 docs 架构图：本地优先，哪个工具就用哪个
# 优先顺序：Mermaid CLI (mmdc) → PlantUML (plantuml)

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DOCS="$ROOT_DIR/docs"
MMD="$DOCS/mcp-architecture.mmd"
PUML="$DOCS/mcp-architecture.puml"
OUT_PNG="$DOCS/mcp-architecture.png"

log() { printf "[render] %s\n" "$*"; }
err() { printf "[render][ERR] %s\n" "$*" >&2; }

have() { command -v "$1" >/dev/null 2>&1; }

render_with_mmdc() {
  if ! have mmdc; then return 1; fi
  if [ ! -f "$MMD" ]; then return 1; fi
  # 选择本地 Chrome：优先 env CHROME_PATH；否则常见路径；否则 CFT
  CHROME_PATH_CAND=(
    "${CHROME_PATH:-}"
    "/home/jiang/.local/chrome-for-testing/chrome-linux/chrome"
    "$(command -v google-chrome 2>/dev/null || true)"
    "$(command -v chromium-browser 2>/dev/null || true)"
    "$(command -v chromium 2>/dev/null || true)"
  )
  SEL=""
  for p in "${CHROME_PATH_CAND[@]}"; do
    [ -n "${p:-}" ] && [ -x "$p" ] && SEL="$p" && break || true
  done
  if [ -z "$SEL" ]; then
    err "未找到本地 Chrome，可设置 CHROME_PATH=/path/to/chrome 或安装 google-chrome/chromium。"
    return 1
  fi
  cfg="$DOCS/puppeteer.config.json"
  cat >"$cfg" <<JSON
{"executablePath":"$SEL","args":["--no-sandbox","--disable-gpu","--disable-dev-shm-usage"]}
JSON
  export PUPPETEER_SKIP_DOWNLOAD=1
  log "Mermaid: $MMD -> $OUT_PNG (chrome=$SEL)"
  if mmdc -i "$MMD" -o "$OUT_PNG" -b transparent -s 1.2 -p "$cfg"; then
    if [ -s "$OUT_PNG" ]; then
      log "done: $OUT_PNG"
      return 0
    fi
  fi
  err "Mermaid 渲染失败或生成空文件，尝试 PlantUML..."
  return 1
}

render_with_plantuml() {
  if ! have plantuml; then return 1; fi
  if [ ! -f "$PUML" ]; then return 1; fi
  log "PlantUML: $PUML -> $OUT_PNG"
  if plantuml -tpng -pipe < "$PUML" > "$OUT_PNG" 2>/dev/null; then
    if [ -s "$OUT_PNG" ]; then
      log "done: $OUT_PNG"
      return 0
    fi
  fi
  err "PlantUML 渲染失败。"
  return 1
}

main() {
  if render_with_mmdc; then exit 0; fi
  if render_with_plantuml; then exit 0; fi
  err "未检测到可用渲染器：请安装 @mermaid-js/mermaid-cli 或 plantuml，或参考 docs/RENDER_DIAGRAMS.md。"
  exit 1
}

main "$@"
