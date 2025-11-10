# MCP Local Manager 自动升级指南

## 概述

为了解决每次升级都需要手动清理旧版本的麻烦，我们提供了两个自动升级脚本：

1. **`auto-upgrade.sh`** - 完整自动升级脚本
2. **`quick-upgrade.sh`** - 快速升级脚本

## 🚀 快速升级（推荐日常使用）

```bash
# 简单快速升级（推荐）
bash scripts/quick-upgrade.sh

# 强制升级（覆盖现有链接）
bash scripts/quick-upgrade.sh --force
```

**特点：**
- ⚡ 执行快速（几秒完成）
- 🔧 简单直接，适合日常升级
- 📋 自动备份旧版本文件
- ✅ 自动验证安装

**适用场景：**
- 日常版本更新
- 快速测试新功能
- 开发者日常使用

---

## 🛡️ 完整自动升级（推荐重大更新）

```bash
# 完整升级（推荐重要版本更新）
bash scripts/auto-upgrade.sh

# 强制升级（即使检测到最新版本）
bash scripts/auto-upgrade.sh --force
```

**特点：**
- 🔍 智能检测当前版本
- 📦 自动备份所有重要配置
- 🧹 全面清理旧版本残留
- 🛡️ 完整的安装验证
- 📊 详细的升级报告

**适用场景：**
- 重大版本升级
- 从其他项目迁移
- 系统环境变更
- 需要完整审计的场景

---

## 📁 备份管理

### 自动备份位置

升级过程会自动创建备份：

- **快速升级备份**：`/usr/local/bin/mcp.backup.YYYYMMDD_HHMMSS`
- **完整升级备份**：`项目目录/backups/YYYYMMDD_HHMMSS/`

### 备份内容

完整升级会备份以下文件：
- `~/.mcp-central/config/mcp-servers.json` - 中央配置
- `~/.claude/settings.json` - Claude配置
- `~/.codex/config.toml` - Codex配置
- `~/.gemini/settings.json` - Gemini配置
- `~/.iflow/settings.json` - iFlow配置
- `~/.factory/mcp.json` - Droid配置
- `~/.cursor/mcp.json` - Cursor配置
- 原始mcp可执行文件

### 手动备份

```bash
# 手动备份所有配置
cp -r ~/.mcp-central/config backups/mcp-central-config-$(date +%Y%m%d)

# 手动备份特定客户端
cp ~/.claude/settings.json backups/claude-settings-$(date +%Y%m%d).json
```

---

## 🔧 使用示例

### 场景1：开发者日常更新

```bash
# 拉取最新代码
git pull origin main

# 快速升级到最新版本
bash scripts/quick-upgrade.sh

# 验证功能
mcp status
mcp check
```

### 场景2：从其他版本升级

```bash
# 克隆或更新到项目目录
git clone <repo-url> mcp-local-manager
cd mcp-local-manager

# 完整自动升级
bash scripts/auto-upgrade.sh

# 检查升级结果
mcp --help
mcp status
```

### 场景3：系统迁移

```bash
# 在新系统上安装最新版本
bash scripts/auto-upgrade.sh

# 如果有旧配置备份
cp backups/mcp-servers.json ~/.mcp-central/config/

# 重新应用配置（交互式选择）
mcp run
```

---

## 🛠️ 故障排除

### 升级失败

```bash
# 检查权限
ls -la /usr/local/bin/mcp

# 手动重新链接
ln -sf /path/to/mcp-local-manager/bin/mcp /usr/local/bin/mcp
chmod +x /usr/local/bin/mcp

# 恢复备份
cp /usr/local/bin/mcp.backup.* /usr/local/bin/mcp
```

### 验证安装

```bash
# 基本验证
mcp --help

# 功能验证
mcp status
mcp check

# 深度验证
bash scripts/mcp-check.sh --probe
```

### 清理问题

```bash
# 清理过期的备份文件
find /usr/local/bin -name "mcp.backup.*" -mtime +30 -delete

# 清理备份目录
rm -rf backups/
```

---

## 🔒 安全注意事项

1. **备份重要性**
   - 升级前请确保重要配置已备份
   - 定期清理过期备份文件

2. **权限检查**
   - 确保对 `/usr/local/bin/` 有写入权限
   - 升级后验证文件权限正确

3. **测试建议**
   - 建议先在测试环境验证
   - 升级后执行完整的功能测试

4. **回滚方案**
   - 保留最近的备份文件
   - 记录升级前的版本信息

---

## 📞 支持

如果升级过程中遇到问题：

1. 检查升级脚本的输出日志
2. 验证备份文件完整性
3. 参考故障排除部分
4. 如需帮助，请提供详细的错误信息

---

**推荐工作流：**

```bash
# 1. 日常快速更新
git pull && bash scripts/quick-upgrade.sh

# 2. 重要版本完整更新
git pull && bash scripts/auto-upgrade.sh

# 3. 验证功能
mcp status && mcp check
```
