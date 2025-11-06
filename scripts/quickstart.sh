#!/usr/bin/env bash
set -euo pipefail

# 60 秒引导：安装 mcp、准备统一清单、为 IDE 写入全部 MCP

REPO_URL="https://github.com/czdtech/mcp-local-manager.git"
REPO_DIR="${REPO_DIR:-$PWD/mcp-local-manager}"

log() { printf "\033[1;32m[OK]\033[0m %s\n" "$*"; }
info() { printf "\033[1;34m[+]\033[0m %s\n" "$*"; }
warn() { printf "\033[1;33m[!]\033[0m %s\n" "$*"; }

ensure_repo() {
  if [ -d "$REPO_DIR/.git" ]; then
    info "已检测到仓库: $REPO_DIR"
    return 0
  fi
  if [ -d "$PWD/mcp-local-manager/.git" ]; then
    REPO_DIR="$PWD/mcp-local-manager"; return 0
  fi
  info "正在克隆仓库..."
  git clone "$REPO_URL" "$REPO_DIR" >/dev/null
}

ensure_central() {
  mkdir -p "$HOME/.mcp-central/config"
  local dst="$HOME/.mcp-central/config/mcp-servers.json"
  if [ ! -f "$dst" ]; then
    cp "$REPO_DIR/config/mcp-servers.sample.json" "$dst"
    log "已生成统一清单: $dst"
  else
    info "已存在统一清单: $dst"
  fi
}

install_mcp() {
  mkdir -p "$HOME/.local/bin"
  ln -sf "$REPO_DIR/bin/mcp" "$HOME/.local/bin/mcp"
  chmod +x "$REPO_DIR/bin/mcp"
  case "$SHELL" in
    */zsh) RC="$HOME/.zshrc" ;;
    *)     RC="$HOME/.bashrc" ;;
  esac
  LINE='if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then export PATH="$HOME/.local/bin:$PATH"; fi'
  if [ -f "$RC" ] && grep -F "$HOME/.local/bin" "$RC" >/dev/null 2>&1; then
    info "PATH 已在 $RC 中配置"
  else
    echo "$LINE" >> "$RC"
    log "已写入 PATH 到 $RC（新终端生效）"
  fi
  export PATH="$HOME/.local/bin:$PATH"
  command -v mcp >/dev/null && log "mcp 就绪: $(command -v mcp)" || warn "未找到 mcp"
}

ide_full() {
  info "为 IDE 写入全部 MCP（VS Code/Cursor）..."
  mcp ide-all >/dev/null || warn "mcp ide-all 执行失败，请稍后重试"
}

main() {
  ensure_repo
  ensure_central
  install_mcp
  ide_full
  log "完成。下一步建议："
  printf "\n- 仅对 Claude 下发并启动：\n  mcp run --client claude --servers context7,serena -- claude\n"
  printf "- 查看某个客户端集合：\n  mcp status codex  # 或 claude / vscode / cursor\n\n"
}

main "$@"

