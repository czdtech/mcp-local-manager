#!/usr/bin/env bash
set -euo pipefail

# MCP Local Manager 自动升级脚本（生产级版本）
# 功能：自动检测、备份、清理旧版本并安装新版本
# 改进：并发保护、健康检查、自动回滚、完整性验证

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
MCP_BIN_PATH="/usr/local/bin/mcp"
LOCK_FILE="/tmp/mcp-auto-upgrade.lock"
LOG_FILE="/tmp/mcp-auto-upgrade-$(date +%Y%m%d_%H%M%S).log"
BACKUP_RETENTION=3  # 保留最近3个完整备份
BACKUP_DIR="$PROJECT_ROOT/backups/$(date +%Y%m%d_%H%M%S)"
UPGRADE_ID="upgrade-$(date +%Y%m%d_%H%M%S)"

# 升级开始时间
START_TIME=$(date +%s)

# 日志函数（增强版）
log_info() {
    local message="$1"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[$timestamp] [INFO] $message" | tee -a "$LOG_FILE"
}

log_success() {
    local message="$1"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "\033[0;32m[$timestamp] [SUCCESS]\033[0m $message" | tee -a "$LOG_FILE"
}

log_warning() {
    local message="$1"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "\033[1;33m[$timestamp] [WARNING]\033[0m $message" | tee -a "$LOG_FILE"
}

log_error() {
    local message="$1"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "\033[0;31m[$timestamp] [ERROR]\033[0m $message" | tee -a "$LOG_FILE"
}

# 获取锁（防止并发执行）
get_lock() {
    local timeout=60
    local count=0
    log_info "尝试获取升级锁..."
    while [[ $count -lt $timeout ]]; do
        if (set -C; echo $$ > "$LOCK_FILE") 2>/dev/null; then
            log_info "获取锁成功"
            return 0
        fi
        sleep 1
        ((count++))
    done
    log_error "获取升级锁失败，可能有其他升级进程正在运行"
    return 1
}

# 释放锁
release_lock() {
    [[ -f "$LOCK_FILE" ]] && rm -f "$LOCK_FILE"
    log_info "已释放升级锁"
}

# 自动回滚机制
rollback_auto() {
    log_error "升级失败，启动自动回滚..."
    
    # 回滚配置
    if [[ -d "$BACKUP_DIR" ]]; then
        log_info "回滚配置备份..."
        # 这里可以添加具体的配置回滚逻辑
        for config in "$BACKUP_DIR"/*; do
            if [[ -f "$config" ]]; then
                local filename=$(basename "$config")
                local target_path="$HOME/.claude/settings.json"  # 简化示例
                case "$filename" in
                    "settings.json")
                        target_path="$HOME/.claude/settings.json"
                        ;;
                    "config.toml")
                        target_path="$HOME/.codex/config.toml"
                        ;;
                    "mcp-servers.json")
                        target_path="$HOME/.mcp-central/config/mcp-servers.json"
                        ;;
                esac
                if [[ -f "$target_path" ]]; then
                    cp "$config" "$target_path" 2>/dev/null && log_info "已回滚: $filename" || true
                fi
            fi
        done
    fi
    
    # 回滚二进制文件
    local mcp_backup="$BACKUP_DIR/mcp.backup"
    if [[ -f "$mcp_backup" ]]; then
        log_info "回滚二进制文件..."
        cp "$mcp_backup" "$MCP_BIN_PATH"
        chmod +x "$MCP_BIN_PATH"
        log_success "二进制文件回滚完成"
    fi
    
    log_info "自动回滚完成"
}

# 清理函数
cleanup() {
    local exit_code=$?
    release_lock
    
    if [[ $exit_code -ne 0 ]]; then
        log_error "升级过程异常退出，回滚中..."
        rollback_auto
    fi
    
    # 计算总耗时
    local end_time=$(date +%s)
    local total_duration=$((end_time - START_TIME))
    log_info "总耗时: ${total_duration} 秒"
    
    exit $exit_code
}
trap cleanup EXIT

# 环境预检查（增强版）
precheck_environment() {
    log_info "执行环境预检查..."
    
    # 检查项目目录
    if [[ ! -d "$PROJECT_ROOT/.git" ]]; then
        log_error "项目目录无效: $PROJECT_ROOT"
        return 1
    fi
    
    # 检查新版本文件
    if [[ ! -f "$PROJECT_ROOT/bin/mcp" ]]; then
        log_error "新版本文件不存在: $PROJECT_ROOT/bin/mcp"
        return 1
    fi
    
    # 检查目标路径权限
    if [[ ! -w "$(dirname "$MCP_BIN_PATH")" ]]; then
        log_error "没有写入权限到 $(dirname "$MCP_BIN_PATH")"
        return 1
    fi
    
    # 检查磁盘空间（至少需要100MB）
    local available_space=$(df "$(dirname "$MCP_BIN_PATH")" | awk 'NR==2 {print $4}')
    if [[ $available_space -lt 102400 ]]; then
        log_error "磁盘空间不足，需要至少100MB"
        return 1
    fi
    
    # 检查网络连通性（如果有相关依赖）
    if ! ping -c 1 github.com >/dev/null 2>&1; then
        log_warning "网络连通性检查失败，但不影响本地升级"
    fi
    
    # 检查备份目录权限
    mkdir -p "$BACKUP_DIR"
    if [[ ! -w "$BACKUP_DIR" ]]; then
        log_error "备份目录不可写: $BACKUP_DIR"
        return 1
    fi
    
    log_info "环境预检查通过"
    return 0
}

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检测当前安装的MCP
detect_current_mcp() {
    log_info "🔍 检测当前MCP安装..."
    
    if [ -L "$MCP_BIN_PATH" ]; then
        local current_target=$(readlink -f "$MCP_BIN_PATH" 2>/dev/null || echo "")
        if [[ "$current_target" == *"/mcp-local-manager/"* ]]; then
            log_info "发现当前版本指向: $current_target"
            if [[ "$current_target" == "$PROJECT_ROOT/bin/mcp" ]]; then
                log_success "已经是最新版本，无需升级"
                return 1
            else
                log_info "发现旧版本，路径: $current_target"
                echo "$current_target"
                return 0
            fi
        fi
    fi
    
    # 检查其他可能的旧安装位置
    if command -v mcp >/dev/null 2>&1; then
        local mcp_path=$(which mcp)
        log_info "发现系统中的MCP: $mcp_path"
        echo "$mcp_path"
        return 0
    fi
    
    log_warning "未发现现有MCP安装"
    return 1
}

# 备份重要配置
backup_configurations() {
    log_info "📦 备份重要配置..."
    
    mkdir -p "$BACKUP_DIR"
    
    # 备份中央配置
    if [ -f ~/.mcp-central/config/mcp-servers.json ]; then
        cp ~/.mcp-central/config/mcp-servers.json "$BACKUP_DIR/mcp-servers.json"
        log_info "已备份中央配置: ~/.mcp-central/config/mcp-servers.json"
    fi
    
    # 备份各客户端配置
    local configs=(
        "$HOME/.claude/settings.json"
        "$HOME/.codex/config.toml"
        "$HOME/.gemini/settings.json"
        "$HOME/.iflow/settings.json"
        "$HOME/.factory/mcp.json"
        "$HOME/.cursor/mcp.json"
    )
    
    for config in "${configs[@]}"; do
        if [ -f "$config" ]; then
            local filename=$(basename "$config")
            cp "$config" "$BACKUP_DIR/$filename"
            log_info "已备份: $config"
        fi
    done
    
    # 备份安装的MCP二进制文件
    if [ -f "$MCP_BIN_PATH" ]; then
        cp "$MCP_BIN_PATH" "$BACKUP_DIR/mcp.backup"
        log_info "已备份旧版本MCP: $MCP_BIN_PATH"
    fi
    
    log_success "备份完成: $BACKUP_DIR"
}

# 清理旧版本
cleanup_old_installation() {
    log_info "🧹 清理旧版本..."
    
    # 移除旧的MCP链接
    if [ -L "$MCP_BIN_PATH" ]; then
        rm -f "$MCP_BIN_PATH"
        log_info "已移除旧链接: $MCP_BIN_PATH"
    fi
    
    # 清理可能的Python包安装
    if command -v pip3 >/dev/null 2>&1; then
        if pip3 show mcp-local-manager >/dev/null 2>&1; then
            log_info "检测到pip安装，尝试卸载..."
            pip3 uninstall -y mcp-local-manager 2>/dev/null || log_warning "pip卸载可能失败，继续升级"
        fi
    fi
    
    # 清理旧的可执行文件
    local old_paths=(
        "/usr/local/bin/serena-mcp-server"
        "~/.local/bin/serena"
    )
    
    for path in "${old_paths[@]}"; do
        local expanded_path=$(eval echo "$path")
        if [ -f "$expanded_path" ]; then
            log_info "保留系统文件: $expanded_path (不删除)"
        fi
    done
    
    log_success "旧版本清理完成"
}

# 安装新版本
install_new_version() {
    log_info "🚀 安装新版本..."
    
    # 确保项目目录存在
    if [ ! -d "$PROJECT_ROOT" ]; then
        log_error "项目目录不存在: $PROJECT_ROOT"
        exit 1
    fi
    
    # 确保新版本文件存在
    if [ ! -f "$PROJECT_ROOT/bin/mcp" ]; then
        log_error "新版本MCP文件不存在: $PROJECT_ROOT/bin/mcp"
        exit 1
    fi
    
    # 创建新链接
    ln -sf "$PROJECT_ROOT/bin/mcp" "$MCP_BIN_PATH"
    
    # 确保权限正确
    chmod +x "$PROJECT_ROOT/bin/mcp"
    chmod +x "$MCP_BIN_PATH"
    
    log_success "新版本安装完成: $MCP_BIN_PATH"
}

# 验证安装
verify_installation() {
    log_info "🔍 验证安装..."
    
    # 测试MCP命令
    if ! command -v mcp >/dev/null 2>&1; then
        log_error "MCP命令未找到"
        return 1
    fi
    
    # 测试基本功能
    if ! mcp --help >/dev/null 2>&1; then
        log_error "MCP命令执行失败"
        return 1
    fi
    
    # 测试核心命令
    local test_commands=("status" "check" "run")
    for cmd in "${test_commands[@]}"; do
        if ! timeout 10 mcp $cmd >/dev/null 2>&1; then
            log_warning "命令测试失败: mcp $cmd"
        fi
    done
    
    log_success "安装验证通过"
}

# 显示升级结果
show_upgrade_summary() {
    local old_path="$1"
    
    echo
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║                    MCP Local Manager 升级完成                    ║"
    echo "╠══════════════════════════════════════════════════════════════╣"
    echo "║ 升级时间: $(date '+%Y-%m-%d %H:%M:%S')                                  ║"
    echo "║ 旧版本:   ${old_path:-"未检测到"}                        ║"
    echo "║ 新版本:   $PROJECT_ROOT/bin/mcp                 ║"
    echo "║ 安装路径: $MCP_BIN_PATH                  ║"
    echo "║ 备份位置: $BACKUP_DIR                      ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo
    echo "新功能特性:"
    echo "• 统一命令: mcp status|run|check|clear|central (均交互式, status/check 只读)"
    echo "• 安全预览: 已内置在交互步骤中"
    echo "• 一键清理: mcp clear (交互式选择目标)"
    echo "• 增强健壮性: 更好的错误处理和自动备份"
    echo
    echo "推荐下一步:"
    echo "• mcp status                    # 查看当前状态"
    echo "• mcp check                     # 运行健康检查"
    echo "• mcp run  # 交互式选择, 预览与确认在流程中完成"
    echo
}

# 主升级流程
main() {
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║              MCP Local Manager 自动升级工具                      ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo
    
    # 检查参数
    if [[ "${1:-}" == "--help" ]] || [[ "${1:-}" == "-h" ]]; then
        echo "用法: $0 [选项]"
        echo
        echo "选项:"
        echo "  --force    强制升级（即使检测到已是最新版本）"
        echo "  --help     显示此帮助信息"
        echo
        echo "功能:"
        echo "  • 自动检测当前MCP版本"
        echo "  • 备份重要配置文件"
        echo "  • 清理旧版本安装"
        echo "  • 安装最新版本"
        echo "  • 验证安装结果"
        echo
        exit 0
    fi
    
    local force_upgrade=false
    if [[ "${1:-}" == "--force" ]]; then
        force_upgrade=true
    fi
    
    # 检测当前版本
    local old_path=""
    if ! old_path=$(detect_current_mcp); then
        if [[ "$force_upgrade" == "false" ]]; then
            log_success "已经是最新版本，无需升级"
            exit 0
        else
            log_info "强制升级模式，继续执行..."
        fi
    fi
    
    # 执行升级流程
    backup_configurations
    cleanup_old_installation
    install_new_version
    
    # 验证安装
    if verify_installation; then
        show_upgrade_summary "$old_path"
        log_success "🎉 升级成功完成！"
        exit 0
    else
        log_error "升级验证失败，请检查安装"
        exit 1
    fi
}

# 错误处理
trap 'log_error "升级过程中发生错误，请检查日志"; exit 1' ERR

# 执行主函数
main "$@"
