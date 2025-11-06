#!/usr/bin/env bash
set -euo pipefail

# 预热 npx 缓存：按中央清单尝试拉取常见 MCP 包的 @latest，避免首次启用时因依赖解析失败。

CENTRAL="$HOME/.mcp-central/config/mcp-servers.json"

log() { printf "[prewarm] %s\n" "$*"; }
warn() { printf "[prewarm][WARN] %s\n" "$*" >&2; }

if [[ ! -f "$CENTRAL" ]]; then
  warn "缺少中央清单: $CENTRAL"
  exit 1
fi

# jq 依赖：若缺失，友好提示并直接成功退出，不阻塞主流程
if ! command -v jq >/dev/null 2>&1; then
  warn "未安装 jq，跳过 npx 预热（建议安装 jq 以获得更好体验）"
  exit 0
fi

pkgs=()
mapfile -t pkgs < <(jq -r '.servers|to_entries[]|.value.args|select(type=="array")|map(tostring)|.[]' "$CENTRAL" 2>/dev/null | awk -F@ '/@/{print $1"@latest"}' | sed -E 's/^@(-y)?$//;t;')

if [[ ${#pkgs[@]} -eq 0 ]]; then
  warn "未发现需要预热的 npx 包（根据 args 推断）"
  exit 0
fi

log "预热包列表(${#pkgs[@]}): ${pkgs[*]}"
for p in "${pkgs[@]}"; do
  [[ -z "$p" ]] && continue
  log "npx -y $p --help"
  npx -y "$p" --help >/dev/null 2>&1 || true
done

log "完成。若遇到 @latest 启动错误，请参考 docs/troubleshooting-mcp.md。"
