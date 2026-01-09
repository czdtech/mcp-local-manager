#!/usr/bin/env python3
"""
MCP Auto Sync (macOS/Linux)
只改 MCP 配置：
- Codex:   ~/.codex/config.toml              [mcp_servers.*] + *.env 子表
- Gemini:  ~/.gemini/settings.json           mcpServers + mcp.allowed
- iFlow:   ~/.iflow/settings.json            mcpServers
- Claude Code: ~/.claude/settings.json       mcpServers（user scope，全局稳定；兼容旧版 ~/.claude.json）
             + ~/.claude.json                projects.*.mcpServers（local scope / 按目录）
- Droid:   ~/.factory/mcp.json               mcpServers
- Cursor:  ~/.cursor/mcp.json                mcpServers
- VS Code: macOS ~/Library/Application Support/Code*/User/mcp.json 顶层 servers
          Linux ~/.config/Code*/User/mcp.json 顶层 servers

与最新 ~/.mcp-central 对齐：
- 不使用 wrappers；Node 生态 server 统一采用 npx 显式最新版（@latest）。
- Claude 命令兜底时，建议显式指定 scope=user（全局），并注意参数顺序：
  claude mcp add --transport stdio --env KEY=VAL ... -s user <name> -- <command> <args>
"""

import json, os, re, shutil, subprocess, sys, platform
from pathlib import Path
import time
import logging

# 复用主 CLI 的 per-client 映射逻辑（client_overrides / type 映射 / timeout 过滤）。
# 兼容脚本从任意目录运行：将仓库根目录加入 sys.path，避免 import 失败。
try:
    _REPO_ROOT = Path(__file__).resolve().parents[1]
    if str(_REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(_REPO_ROOT))
    from mcp_cli import utils as _CLI_U  # type: ignore
except Exception:
    _CLI_U = None

# Import validation module with graceful fallback
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
    # Fallback when validation module is not available
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
    # 单槽备份（覆盖写），避免备份堆积；可用 `mcp undo <file>.backup` 回滚
    b = p.with_name(p.name + '.backup')
    shutil.copy2(p, b)
    log_info(f'已备份: {b.name}')
    return b

def load_central():
    """Load central MCP servers configuration with validation and retry logic."""
    if not CENTRAL.exists():
        log_err(f'缺少统一清单: {CENTRAL}')
        sys.exit(1)
    
    # Try to validate the configuration
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
            # Fall back to basic JSON loading
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
    
    # Validate individual servers if validation is available
    if VALIDATION_AVAILABLE and validation_passed:
        from mcp_validation import validate_server_config
        for server_name, server_info in servers.items():
            try:
                validate_server_config(server_name, server_info)
            except MCPValidationError as e:
                log_warn(f'服务器配置警告 - {server_name}: {e}')
    
    return servers

def _load_central_fallback():
    """Fallback function to load central configuration without validation."""
    try:
        return json.loads(CENTRAL.read_text(encoding='utf-8'))
    except json.JSONDecodeError as e:
        log_err(f'中央配置文件 JSON 格式错误: {e}')
        log_err(f'错误位置: 行 {e.lineno}, 列 {e.colno}')
        sys.exit(1)
    except Exception as e:
        log_err(f'读取中央配置文件失败: {e}')
        sys.exit(1)

# Global servers configuration with enhanced error handling
try:
    SERVERS = load_central()
except Exception as e:
    log_err(f'加载中央配置失败: {e}')
    SERVERS = {}

def kv(obj, k, default):
    v = obj.get(k)
    return v if v is not None else default

def _expand_tilde(v):
    """Expand leading '~' in strings; keep non-str intact."""
    if isinstance(v, str):
        try:
            return os.path.expanduser(v)
        except Exception:
            return v
    return v

def _expand_cmd_args(info: dict):
    """Return (command, args) with user tilde expansion applied."""
    cmd = _expand_tilde(info.get('command', ''))
    raw_args = info.get('args') or []
    args = []
    for a in raw_args:
        # keep types, only expand str
        args.append(_expand_tilde(a))
    return cmd, args

def _to_target(info: dict, client: str | None) -> dict:
    """应用 central 的 client_overrides + type 映射（若可用）。"""
    if _CLI_U is None:
        return info or {}
    try:
        return _CLI_U.to_target_server_info(info or {}, client=client)
    except Exception:
        return info or {}

# ------------ Codex (TOML) ------------
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
        info = _to_target(info or {}, client="codex")
        lines.append(f"\n[mcp_servers.{name}]")
        # Codex 默认 startup=10s/tool=60s 对索引型 MCP 偏紧：优先尊重 central 的 timeout（秒）。
        timeout = (info or {}).get("timeout")
        try:
            timeout_sec = int(timeout) if timeout is not None else 60
        except Exception:
            timeout_sec = 60
        if timeout_sec < 1:
            timeout_sec = 60
        lines.append(f"startup_timeout_sec = {timeout_sec}")
        lines.append(f"tool_timeout_sec = {timeout_sec}")
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
    # 1) 移除所有旧的 MCP 标记块（Local Manager / Central）
    for pat in [
        r"\n*# === MCP Servers 配置（由 MCP Local Manager 生成）===\n(?:.|\n)*?(?=\n?# ===|\Z)",
        r"\n*# === MCP Servers 配置（由 MCP Central 生成）===\n(?:.|\n)*?(?=\n?# ===|\Z)"
    ]:
        content = re.sub(pat, "\n", content)
    # 2) 保险起见：清理所有 [mcp_servers.*] 段
    content = re.sub(r"(?ms)^\[mcp_servers\.[^\]]+\][\s\S]*?(?=^\[|\Z)", "", content)
    # 3) 追加一次新的块
    content = content.rstrip()+"\n"+new_block+"\n"
    p.write_text(content, encoding='utf-8')
    log_ok(f'Codex 配置已更新: {p}')
    return True

# ------------ JSON helpers ------------
def write_json(path: Path, obj: dict, max_retries: int = 3, retry_delay: float = 0.1):
    """Write JSON file with retry logic and enhanced error handling.
    
    Args:
        path: Path to write the file
        obj: Dictionary to serialize to JSON
        max_retries: Maximum number of retry attempts
        retry_delay: Delay between retries in seconds
    """
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
                time.sleep(retry_delay * (2 ** attempt))  # Exponential backoff
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
    """Write JSON file with retry logic and logging.
    
    Args:
        path: Path to write the file
        obj: Dictionary to serialize to JSON
        label: Label for logging purposes
        max_retries: Maximum number of retry attempts
    """
    success = write_json(path, obj, max_retries)
    if success:
        if label:
            log_ok(f'{label} 配置已更新: {path}')
        else:
            log_ok(f'配置已更新: {path}')
    return success

def build_mcpServers(client: str | None = None):
    out = {}
    for name,info in SERVERS.items():
        if not (info or {}).get('enabled', True):
            continue
        mapped = _to_target(info or {}, client=client)
        entry = {}
        for k in ('command','args','env','url','headers','type','timeout'):
            if k in mapped and mapped[k] not in (None, {} , []):
                entry[k] = mapped[k]

        # Droid: 官方格式中 type 固定为 stdio（与 mcp_cli.commands.run 逻辑一致）
        if client == "droid":
            entry["type"] = "stdio"

        # 统一展开 ~，避免目标文件中出现未展开路径
        if 'command' in entry:
            entry['command'] = _expand_tilde(entry['command'])
        if 'args' in entry and isinstance(entry['args'], list):
            entry['args'] = [_expand_tilde(a) for a in entry['args']]
        out[name]=entry
    return out

def sync_json_map(label, p: Path, key='mcpServers', allowed=False, key_client: str | None = None):
    """Sync JSON configuration with enhanced error handling and retry logic.
    
    Args:
        label: Label for logging
        p: Path to the configuration file
        key: Key to use for MCP servers
        allowed: Whether to set allowed list for Gemini
        
    Returns:
        bool: True if successful
    """
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
    obj[key] = build_mcpServers(client=key_client)
    if allowed:
        obj.setdefault('mcp', {})['allowed'] = sorted(obj[key].keys())
    
    # Use retry-enabled write function
    return write_json_with_retry(p, obj, label)

def sync_gemini():
    return sync_json_map(
        'Gemini', HOME/'.gemini'/'settings.json', 'mcpServers', allowed=True, key_client="gemini"
    )

def sync_iflow():
    return sync_json_map('iFlow', HOME/'.iflow'/'settings.json', 'mcpServers', key_client="iflow")

def sync_droid():
    return sync_json_map('Droid', HOME/'.factory'/'mcp.json', 'mcpServers', key_client="droid")

def sync_cursor():
    return sync_json_map('Cursor', HOME/'.cursor'/'mcp.json', 'mcpServers', key_client="cursor")

def sync_vscode():
    """Sync VS Code configuration with enhanced error handling."""
    if OS=='darwin':
        targets = [
            ("vscode-user", HOME/'Library'/'Application Support'/'Code'/'User'/'mcp.json'),
            ("vscode-insiders", HOME/'Library'/'Application Support'/'Code - Insiders'/'User'/'mcp.json'),
        ]
    else:
        targets = [
            ("vscode-user", HOME/'.config'/'Code'/'User'/'mcp.json'),
            ("vscode-insiders", HOME/'.config'/'Code - Insiders'/'User'/'mcp.json'),
        ]
    success_count = 0
    
    for client, p in targets:
        servers = build_mcpServers(client=client)
        success = write_json_with_retry(
            p, {'servers': servers}, f'VS Code ({p.parent.parent.name})'
        )
        if success:
            success_count += 1
    
    if success_count == 0:
        log_err('所有 VS Code 配置更新失败')
        return False
    elif success_count < len(targets):
        log_warn(f'部分 VS Code 配置更新失败: {success_count}/{len(targets)}')
    return True

# ------------ Claude (文件为主，命令兜底) ------------
def sync_claude_file():
    p = HOME/'.claude'/'settings.json'
    obj = {}
    if p.exists():
        try:
            obj = json.loads(p.read_text(encoding='utf-8'))
        except Exception as e:
            log_warn(f'Claude settings 解析失败，将重写: {e}')
            obj = {}
    obj['mcpServers'] = build_mcpServers(client="claude-file")
    write_json(p, obj)
    log_ok(f'Claude(文件) 配置已更新: {p}')
    return True


def _claude_scope() -> str:
    if _CLI_U is not None and hasattr(_CLI_U, "claude_registry_scope"):
        try:
            return str(_CLI_U.claude_registry_scope())
        except Exception:
            pass
    scope = (os.environ.get("MCP_CLAUDE_SCOPE") or "user").strip().lower()
    return scope if scope in ("local", "user", "project") else "user"


def _claude_user_mcp_servers() -> set[str]:
    # 避免模块级 HOME 常量在测试/子进程中被提前绑定；这里动态读取 Path.home()
    home = Path.home()

    # 1) 优先读取官方 settings 文件：~/.claude/settings.json
    p = home / ".claude" / "settings.json"
    if p.exists():
        try:
            obj = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            obj = None
        m = obj.get("mcpServers") if isinstance(obj, dict) else None
        if isinstance(m, dict) and m:
            return set(m.keys())

    # 2) 兼容旧版：~/.claude.json
    p = home / ".claude.json"
    if not p.exists():
        return set()
    try:
        obj = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return set()
    m = obj.get("mcpServers") if isinstance(obj, dict) else None
    return set(m.keys()) if isinstance(m, dict) else set()

def claude_registered():
    scope = _claude_scope()
    if scope == "user":
        return _claude_user_mcp_servers()
    try:
        out = subprocess.run(['claude','mcp','list'], capture_output=True, text=True, timeout=10)
        text = (out.stdout or '') + "\n" + (out.stderr or '')
        reg = set()
        for line in text.splitlines():
            line = (line or '').strip()
            if not line or line.startswith('plugin:'):
                continue
            if ':' in line:
                reg.add(line.split(':',1)[0].strip())
        return reg
    except Exception:
        return set()

def sync_claude_cmd():
    scope = _claude_scope()
    want = {k for k,v in SERVERS.items() if v.get('enabled', True)}
    have = claude_registered()
    missing = sorted(want - have)
    ok = True
    for name in missing:
        info = _to_target(SERVERS[name] or {}, client="claude-reg")
        cmd = ['claude','mcp','add','--transport','stdio']
        for k,v in (info.get('env') or {}).items():
            cmd.extend(['--env', f'{k}={v}'])
        cmd += ['-s', scope, name]
        # 展开路径中的 ~，并保证 args 为字符串
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

# ------------ main ------------
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
        # 兼容性：测试会调用 status，这里输出轻量提示
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
""")
        sys.exit(0)
    else:
        log_err(f"未知命令: {cmd}")
        sys.exit(2)

if __name__ == '__main__':
    main()
