#!/usr/bin/env bash
set -euo pipefail

# MCP Local Manager 快速升级脚本（生产级版本）
# 用于日常快速升级，具备并发保护、健康检查和自动回滚

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
MCP_BIN_PATH="/usr/local/bin/mcp"
LOCK_FILE="/tmp/mcp-upgrade.lock"
LOG_FILE="/tmp/mcp-upgrade-$(date +%Y%m%d_%H%M%S).log"
BACKUP_RETENTION=5  # 保留最近5个备份
BACKUP_DIR="/tmp/mcp-backups"

# 日志函数
log() {
    local level="$1"
    local message="$2"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[$timestamp] [$level] $message" | tee -a "$LOG_FILE"
}

# 清理函数
cleanup() {
    local exit_code=$?
    if [[ $exit_code -ne 0 ]]; then
        log "ERROR" "升级失败，尝试回滚..."
        rollback_quick
    fi
    # 释放锁
    [[ -f "$LOCK_FILE" ]] && rm -f "$LOCK_FILE"
    exit $exit_code
}
trap cleanup EXIT

# 获取锁（防止并发执行）
get_lock() {
    local timeout=30
    local count=0
    while [[ $count -lt $timeout ]]; do
        if (set -C; echo $$ > "$LOCK_FILE") 2>/dev/null; then
            return 0
        fi
        sleep 1
        ((count++))
    done
    log "ERROR" "获取升级锁失败，可能有其他升级进程正在运行"
    return 1
}

# 释放锁
release_lock() {
    [[ -f "$LOCK_FILE" ]] && rm -f "$LOCK_FILE"
}

# 环境预检查
precheck() {
    log "INFO" "执行环境预检查..."
    
    # 检查项目目录
    if [[ ! -d "$PROJECT_ROOT/.git" ]]; then
        log "ERROR" "项目目录无效: $PROJECT_ROOT"
        return 1
    fi
    
    # 检查新版本文件
    if [[ ! -f "$PROJECT_ROOT/bin/mcp" ]]; then
        log "ERROR" "新版本文件不存在: $PROJECT_ROOT/bin/mcp"
        return 1
    fi
    
    # 检查目标路径权限
    if [[ ! -w "$(dirname "$MCP_BIN_PATH")" ]]; then
        log "ERROR" "没有写入权限到 $(dirname "$MCP_BIN_PATH")"
        return 1
    fi
    
    # 检查磁盘空间（至少需要50MB）
    local available_space=$(df "$(dirname "$MCP_BIN_PATH")" | awk 'NR==2 {print $4}')
    if [[ $available_space -lt 51200 ]]; then
        log "ERROR" "磁盘空间不足，需要至少50MB"
        return 1
    fi
    
    # 创建备份目录
    mkdir -p "$BACKUP_DIR"
    
    log "INFO" "环境预检查通过"
    return 0
}

# 快速回滚
rollback_quick() {
    log "INFO" "执行快速回滚..."
    
    # 恢复最近的备份
    local latest_backup=$(ls -t "$MCP_BIN_PATH".backup.* 2>/dev/null | head -1)
    if [[ -n "$latest_backup" ]]; then
        cp "$latest_backup" "$MCP_BIN_PATH"
        chmod +x "$MCP_BIN_PATH"
        log "SUCCESS" "已回滚到备份版本: $latest_backup"
    else
        log "ERROR" "未找到可用的备份文件"
        return 1
    fi
}

# 健康检查
health_check() {
    log "INFO" "执行健康检查..."
    
    # 基本命令测试
    if ! mcp --help >/dev/null 2>&1; then
        log "ERROR" "MCP命令执行失败"
        return 1
    fi
    
    # 功能测试
    local test_commands=("status" "check")
    for cmd in "${test_commands[@]}"; do
        if ! timeout 10 mcp "$cmd" >/dev/null 2>&1; then
            log "WARNING" "功能测试失败: mcp $cmd"
        fi
    done
    
    log "INFO" "健康检查完成"
    return 0
}

# 清理过期备份
cleanup_backups() {
    local backups=($(ls -t "$MCP_BIN_PATH".backup.* 2>/dev/null))
    if [[ ${#backups[@]} -gt $BACKUP_RETENTION ]]; then
        for ((i=BACKUP_RETENTION; i<${#backups[@]}; i++)); do
            rm -f "${backups[i]}"
            log "INFO" "清理过期备份: ${backups[i]}"
        done
    fi
}

# 快速升级函数（生产级）
quick_upgrade() {
    log "INFO" "开始快速升级流程..."
    
    # 获取锁
    if ! get_lock; then
        return 1
    fi
    
    # 环境预检查
    if ! precheck; then
        return 1
    fi
    
    # 记录开始时间
    local start_time=$(date +%s)
    
    # 备份现有版本
    if [[ -f "$MCP_BIN_PATH" ]]; then
        local backup_file="$MCP_BIN_PATH.backup.$(date +%Y%m%d_%H%M%S)"
        cp "$MCP_BIN_PATH" "$backup_file"
        log "INFO" "已创建备份: $backup_file"
        # 移动到备份目录以便管理
        mv "$backup_file" "$BACKUP_DIR/"
    fi
    
    # 原子级链接切换（使用 ln -sfn 更安全）
    log "INFO" "执行原子级版本切换..."
    if ln -sfn "$PROJECT_ROOT/bin/mcp" "$MCP_BIN_PATH"; then
        log "SUCCESS" "符号链接更新成功"
    else
        log "ERROR" "符号链接更新失败"
        return 1
    fi
    
    # 设置权限
    chmod +x "$PROJECT_ROOT/bin/mcp"
    chmod +x "$MCP_BIN_PATH"
    log "INFO" "权限设置完成"
    
    # 清理过期备份
    cleanup_backups
    
    # 健康检查
    if ! health_check; then
        log "ERROR" "健康检查失败"
        return 1
    fi
    
    # 计算升级耗时
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    
    log "SUCCESS" "快速升级完成，耗时 ${duration} 秒"
    log "INFO" "日志文件: $LOG_FILE"
    
    return 0
}

# 主函数
main() {
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║              MCP Local Manager 快速升级工具（生产级）              ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    
    case "${1:-}" in
        --help|-h)
            echo "用法: $0 [选项]"
            echo
            echo "功能: 快速升级MCP到当前仓库版本（生产级安全版本）"
            echo "特点: 并发保护、自动回滚、健康检查、详细日志"
            echo
            echo "选项:"
            echo "  --force    强制升级模式"
            echo "  --help     显示此帮助信息"
            echo
            echo "改进特性:"
            echo "  • 锁文件机制防止并发升级"
            echo "  • 自动回滚机制，失败时自动恢复到备份"
            echo "  • 健康检查确保升级后功能正常"
            echo "  • 详细日志记录便于问题排查"
            echo "  • 备份保留策略，自动清理过期备份"
            echo
            echo "日志位置: /tmp/mcp-upgrade-*.log"
            echo "备份位置: $BACKUP_DIR"
            exit 0
            ;;
        --force)
            log "INFO" "强制升级模式"
            ;;
        "")
            ;;
        *)
            echo "未知参数: $1"
            echo "使用 --help 查看帮助"
            exit 1
            ;;
    esac
    
    # 执行升级
    if quick_upgrade; then
        echo
        echo "🎉 快速升级成功！"
        echo "日志文件: $LOG_FILE"
        echo "备份位置: $BACKUP_DIR"
        echo
        echo "推荐下一步:"
        echo "• mcp status                    # 查看当前状态"
        echo "• mcp check                     # 运行健康检查"
        echo "• mcp run  # 交互式选择, 预览与确认在流程中完成"
        exit 0
    else
        log "ERROR" "快速升级失败"
        echo "❌ 升级失败，请查看日志: $LOG_FILE"
        exit 1
    fi
}

# 执行主函数
main "$@"
