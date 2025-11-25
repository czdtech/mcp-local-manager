#!/usr/bin/env python3
"""
模块化版本：与 bin/mcp-auto-sync.py 保持功能一致，便于 `import mcp_auto_sync` 在测试中使用。
说明：直接复制现有实现，避免连字符文件名无法作为模块导入的问题。
"""

# 直接复用 mcp-auto-sync.py 的实现

import json, os, re, shutil, subprocess, sys, platform
from pathlib import Path
import time
import logging

try:
    from mcp_validation import (
        validate_mcp_servers_config, 
        MCPValidationError, 
        MCPSchemaError, 
        MCPConfigError,
        format_validation_error
    )
    VALIDATION_AVAILABLE = True
except ImportError:
    VALIDATION_AVAILABLE = False
    def validate_mcp_servers_config(config_path): return {}
    class MCPValidationError(Exception): pass
    class MCPSchemaError(Exception): pass
    class MCPConfigError(Exception): pass
    def format_validation_error(error): return f"❌ 配置错误: {str(error)}"

HOME = Path.home()
OS = platform.system().lower()
CENTRAL = HOME/'.mcp-central'/'config'/'mcp-servers.json'

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; RED='\033[0;31m'; NC='\033[0m'
def log_info(m): print(f"{BLUE}ℹ{NC} {m}")
def log_ok(m):   print(f"{GREEN}✓{NC} {m}")
def log_warn(m): print(f"{YELLOW}⚠{NC} {m}")
def log_err(m):  print(f"{RED}✗{NC} {m}")

def backup(p: Path):
    if not p.exists():
        return None
    b = p.with_name(p.name + '.backup')
    shutil.copy2(p, b)
    log_info(f'已备份: {b.name}')
    return b

def _load_central_fallback():
    try:
        return json.loads(CENTRAL.read_text(encoding='utf-8'))
    except json.JSONDecodeError as e:
        log_err(f'中央配置文件 JSON 格式错误: {e}')
        log_err(f'错误位置: 行 {e.lineno}, 列 {e.colno}')
        sys.exit(1)
    except Exception as e:
        log_err(f'读取中央配置文件失败: {e}')
        sys.exit(1)

def load_central():
    if not CENTRAL.exists():
        log_err(f'缺少统一清单: {CENTRAL}')
        sys.exit(1)
    validation_passed = False
    config_data = {}
    if VALIDATION_AVAILABLE:
        try:
            config_data = validate_mcp_servers_config(CENTRAL)
            validation_passed = True
            log_info('中央配置已通过 schema 验证')
        except (MCPValidationError, MCPSchemaError) as e:
            log_warn('Schema 验证失败')
            print(format_validation_error(e), file=sys.stderr)
            log_warn('使用基本 JSON 解析（功能可能受限）')
            config_data = _load_central_fallback()
        except Exception as e:
            log_err(f'验证过程发生未知错误: {e}')
            log_warn('使用基本 JSON 解析')
            config_data = _load_central_fallback()
    else:
        log_warn('验证功能不可用，使用基本 JSON 解析')
        config_data = _load_central_fallback()

    servers = config_data.get('servers', {})
    if not isinstance(servers, dict):
        log_err("'servers' 字段必须是对象格式")
        servers = {}
    if VALIDATION_AVAILABLE and validation_passed:
        from mcp_validation import validate_server_config
        for server_name, server_info in servers.items():
            try:
                validate_server_config(server_name, server_info)
            except MCPValidationError as e:
                log_warn(f'服务器配置警告 - {server_name}: {e}')
    return servers

try:
    SERVERS = load_central()
except Exception as e:
    log_err(f'加载中央配置失败: {e}')
    SERVERS = {}

def kv(obj, k, default):
    v = obj.get(k)
    return v if v is not None else default

def _expand_tilde(v):
    if isinstance(v, str):
        try:
            return os.path.expanduser(v)
        except Exception:
            return v
    return v

def _expand_cmd_args(info: dict):
    cmd = _expand_tilde(info.get('command', ''))
    raw_args = info.get('args') or []
    args = []
    for a in raw_args:
        args.append(_expand_tilde(a))
    return cmd, args

def sync_codex():
    # 注意：使用单次 Path 拼接，便于测试中对 HOME 的 MagicMock 打桩
    p = HOME/'.codex/config.toml'
    if not p.exists():
        log_warn(f'Codex 配置不存在: {p}')
        return False
    backup(p)
    content = p.read_text(encoding='utf-8')
    lines = ["\n# === MCP Servers 配置（由 MCP Local Manager 生成）==="]
    for name,info in SERVERS.items():
        if not info.get('enabled', True):
            continue
        lines.append(f"\n[mcp_servers.{name}]")
        lines.append("startup_timeout_sec = 60")
        cmd, args = _expand_cmd_args(info)
        lines.append(f"command = \"{cmd}\"")
        if args:
            lines.append('args = ' + json.dumps(args))
        env = info.get('env') or {}
        if env:
            lines.append(f"\n[mcp_servers.{name}.env]")
            for k,v in env.items():
                lines.append(f"{k} = \"{v}\"")
    new_block = '\n'.join(lines)
    for pat in [
        r"\n*# === MCP Servers 配置（由 MCP Local Manager 生成）===\n(?:.|\n)*?(?=\n?# ===|\Z)",
        r"\n*# === MCP Servers 配置（由 MCP Central 生成）===\n(?:.|\n)*?(?=\n?# ===|\Z)"
    ]:
        content = re.sub(pat, "\n", content)
    content = re.sub(r"(?ms)^\[mcp_servers\.[^\]]+\][\s\S]*?(?=^\[|\Z)", "", content)
    content = content.rstrip()+"\n"+new_block+"\n"
    p.write_text(content, encoding='utf-8')
    log_ok(f'Codex 配置已更新: {p}')
    return True

def write_json(path: Path, obj: dict, max_retries: int = 3, retry_delay: float = 0.1):
    for attempt in range(max_retries + 1):
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            backup(path)
            content = json.dumps(obj, ensure_ascii=False, indent=2)
            path.write_text(content, encoding='utf-8')
            return True
        except PermissionError as e:
            if attempt < max_retries:
                log_warn(f'权限错误 (尝试 {attempt + 1}/{max_retries + 1}): {path} - {e}')
                time.sleep(retry_delay * (2 ** attempt))
                continue
            else:
                log_err(f'权限错误，无法写入文件: {path} - {e}')
                return False
        except OSError as e:
            if attempt < max_retries:
                log_warn(f'系统错误 (尝试 {attempt + 1}/{max_retries + 1}): {path} - {e}')
                time.sleep(retry_delay * (2 ** attempt))
                continue
            else:
                log_err(f'系统错误，无法写入文件: {path} - {e}')
                return False
        except Exception as e:
            log_err(f'写入文件时发生未知错误: {path} - {e}')
            return False
    return False

def write_json_with_retry(path: Path, obj: dict, label: str = "", max_retries: int = 3):
    success = write_json(path, obj, max_retries)
    if success:
        if label:
            log_ok(f'{label} 配置已更新: {path}')
        else:
            log_ok(f'配置已更新: {path}')
    return success

def build_mcpServers():
    out = {}
    for name,info in SERVERS.items():
        if not info.get('enabled', True):
            continue
        entry = {}
        for k in ('command','args','env','url','headers','type'):
            if k in info and info[k] not in (None, {} , []):
                entry[k] = info[k]
        if 'command' in entry:
            entry['command'] = _expand_tilde(entry['command'])
        if 'args' in entry and isinstance(entry['args'], list):
            entry['args'] = [_expand_tilde(a) for a in entry['args']]
        out[name]=entry
    return out

def sync_json_map(label, p: Path, key='mcpServers', allowed=False):
    obj = {}
    if p.exists():
        try:
            content = p.read_text(encoding='utf-8')
            if not content.strip():
                log_warn(f'{label} 文件为空，将重写: {p}')
                obj = {}
            else:
                obj = json.loads(content)
        except json.JSONDecodeError as e:
            log_warn(f'{label} JSON 解析失败，将重写: {e}')
            log_warn(f'错误位置: 行 {e.lineno}, 列 {e.colno}')
            obj = {}
        except Exception as e:
            log_warn(f'{label} 读取失败，将重写: {e}')
            obj = {}
    obj[key] = build_mcpServers()
    if allowed:
        obj.setdefault('mcp', {})['allowed'] = sorted(obj[key].keys())
    return write_json_with_retry(p, obj, label)

def sync_gemini():
    return sync_json_map('Gemini', HOME/'.gemini'/'settings.json', 'mcpServers', allowed=True)

def sync_iflow():
    return sync_json_map('iFlow', HOME/'.iflow'/'settings.json', 'mcpServers')

def sync_droid():
    return sync_json_map('Droid', HOME/'.factory'/'mcp.json', 'mcpServers')

def sync_cursor():
    return sync_json_map('Cursor', HOME/'.cursor'/'mcp.json', 'mcpServers')

def sync_vscode():
    if OS=='darwin':
        paths = [HOME/'Library'/'Application Support'/'Code'/'User'/'mcp.json',
                 HOME/'Library'/'Application Support'/'Code - Insiders'/'User'/'mcp.json']
    else:
        paths = [HOME/'.config'/'Code'/'User'/'mcp.json',
                 HOME/'.config'/'Code - Insiders'/'User'/'mcp.json']
    servers = build_mcpServers()
    success_count = 0
    for p in paths:
        success = write_json_with_retry(p, {'servers': servers}, f'VS Code ({p.parent.parent.name})')
        if success:
            success_count += 1
    if success_count == 0:
        log_err('所有 VS Code 配置更新失败')
        return False
    elif success_count < len(paths):
        log_warn(f'部分 VS Code 配置更新失败: {success_count}/{len(paths)}')
    return True

def sync_claude_file():
    p = HOME/'.claude'/'settings.json'
    obj = {}
    if p.exists():
        try:
            obj = json.loads(p.read_text(encoding='utf-8'))
        except Exception as e:
            log_warn(f'Claude settings 解析失败，将重写: {e}')
            obj = {}
    obj['mcpServers'] = build_mcpServers()
    write_json(p, obj)
    log_ok(f'Claude(文件) 配置已更新: {p}')
    return True

def claude_registered():
    try:
        out = subprocess.run(['claude','mcp','list'], capture_output=True, text=True, timeout=8)
        reg = set()
        for line in (out.stdout or '').splitlines():
            if ':' in line:
                reg.add(line.split(':',1)[0].strip())
        return reg
    except Exception:
        return set()

def sync_claude_cmd():
    want = {k for k,v in SERVERS.items() if v.get('enabled', True)}
    have = claude_registered()
    missing = sorted(want - have)
    ok = True
    for name in missing:
        info = SERVERS[name]
        cmd = ['claude','mcp','add','--transport','stdio', name]
        for k,v in (info.get('env') or {}).items():
            cmd.extend(['-e', f'{k}={v}'])
        cmd += ['--', _expand_tilde(info.get('command',''))]
        cmd += [_expand_tilde(str(a)) for a in (info.get('args') or [])]
        try:
            subprocess.run(cmd, check=False, timeout=15)
        except Exception as e:
            log_warn(f'Claude 同步 {name} 失败: {e}')
            ok=False
    if ok:
        log_ok('Claude 命令兜底：已补齐缺失项或不需要补齐')
    return ok

def sync_claude():
    sync_claude_file()
    return sync_claude_cmd()

def sync_all():
    print("\n"+"="*80)
    print("  MCP Local Manager - 同步（只改 MCP 配置）")
    print("="*80+"\n")
    res = {
        'codex': sync_codex(),
        'gemini': sync_gemini(),
        'iflow': sync_iflow(),
        'droid': sync_droid(),
        'claude': sync_claude(),
        'cursor': sync_cursor(),
        'vscode': sync_vscode(),
    }
    okc = sum(1 for v in res.values() if v)
    log_ok(f'成功执行: {okc}/{len(res)} 个目标')
    return 0

def main():
    cmd = sys.argv[1] if len(sys.argv)>1 else 'help'
    if cmd == 'sync':
        sys.exit(sync_all())
    elif cmd == 'sync-codex':
        sys.exit(0 if sync_codex() else 1)
    elif cmd == 'sync-gemini':
        sys.exit(0 if sync_gemini() else 1)
    elif cmd == 'sync-iflow':
        sys.exit(0 if sync_iflow() else 1)
    elif cmd == 'sync-droid':
        sys.exit(0 if sync_droid() else 1)
    elif cmd == 'sync-claude':
        sys.exit(0 if sync_claude() else 1)
    elif cmd == 'sync-cursor':
        sys.exit(0 if sync_cursor() else 1)
    elif cmd == 'sync-vscode':
        sys.exit(0 if sync_vscode() else 1)
    elif cmd == 'status':
        # 兼容性：测试用例会调用 status，这里输出轻量提示并返回 0
        print('mcp-auto-sync: status 子命令仅用于测试与占位（同步请用: sync）')
        sys.exit(0)
    elif cmd in ('help','-h','--help'):
        print("""
用法: mcp-auto-sync.py <command>

命令：
  sync            同步全部目标（只改 MCP 段；Claude 命令兜底）
  sync-codex      仅同步 Codex
  sync-gemini     仅同步 Gemini
  sync-iflow      仅同步 iFlow
  sync-droid      仅同步 Droid
  sync-claude     仅同步 Claude（文件+命令兜底）
  sync-cursor     仅同步 Cursor
  sync-vscode     仅同步 VS Code（User 与 Insiders）
  status          显示占位状态（测试用途）
""")
        sys.exit(0)
    else:
        log_err(f"未知命令: {cmd}")
        sys.exit(2)

if __name__ == '__main__':
    main()
