#!/usr/bin/env python3
"""
MCP Auto Sync (macOS/Linux)
只改 MCP 配置：
- Codex:   ~/.codex/config.toml              [mcp_servers.*] + *.env 子表
- Gemini:  ~/.gemini/settings.json           mcpServers + mcp.allowed
- iFlow:   ~/.iflow/settings.json            mcpServers
- Claude:  ~/.claude/settings.json           mcpServers（命令兜底仅补缺项）
- Droid:   ~/.factory/mcp.json               mcpServers
- Cursor:  ~/.cursor/mcp.json                mcpServers
- VS Code: macOS ~/Library/Application Support/Code*/User/mcp.json 顶层 servers
          Linux ~/.config/Code*/User/mcp.json 顶层 servers

与最新 ~/.mcp-central 对齐：
- 不使用 wrappers；Node 生态 server 统一采用 npx 显式最新版（@latest）。
- Claude 命令兜底时，环境变量必须位于 name 与 "--" 之间：
  claude mcp add --transport stdio <name> -e KEY=VAL ... -- <command> <args>
"""

import json, os, re, shutil, subprocess, sys, platform
from pathlib import Path

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
    ts = __import__('datetime').datetime.now().strftime('%Y%m%d_%H%M%S')
    b = p.with_suffix(f'.{ts}.backup')
    shutil.copy2(p, b)
    log_info(f'已备份: {b.name}')
    return b

def load_central():
    if not CENTRAL.exists():
        log_err(f'缺少统一清单: {CENTRAL}')
        sys.exit(1)
    return json.loads(CENTRAL.read_text(encoding='utf-8')).get('servers', {})

SERVERS = load_central()

def kv(obj, k, default):
    v = obj.get(k)
    return v if v is not None else default

# ------------ Codex (TOML) ------------
def sync_codex():
    p = HOME/'.codex'/'config.toml'
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
        # Codex: 增加启动超时，避免默认 10s 超时（npx 首次拉取较慢）
        lines.append("startup_timeout_sec = 60")
        lines.append(f"command = \"{info.get('command','')}\"")
        args = info.get('args') or []
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
def write_json(path: Path, obj: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    backup(path)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding='utf-8')

def build_mcpServers():
    out = {}
    for name,info in SERVERS.items():
        if not info.get('enabled', True):
            continue
        entry = {}
        for k in ('command','args','env','url','headers','type'):
            if k in info and info[k] not in (None, {} , []):
                entry[k] = info[k]
        out[name]=entry
    return out

def sync_json_map(label, p: Path, key='mcpServers', allowed=False):
    obj = {}
    if p.exists():
        try:
            obj = json.loads(p.read_text(encoding='utf-8'))
        except Exception as e:
            log_warn(f'{label} 解析失败，将重写: {e}')
            obj = {}
    obj[key] = build_mcpServers()
    if allowed:
        obj.setdefault('mcp', {})['allowed'] = sorted(obj[key].keys())
    write_json(p, obj)
    log_ok(f'{label} 配置已更新: {p}')
    return True

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
    for p in paths:
        write_json(p, {'servers': servers})
        log_ok(f'VS Code 配置已更新: {p}')
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
        # 环境变量必须在 name 与 -- 之间
        for k,v in (info.get('env') or {}).items():
            cmd.extend(['-e', f'{k}={v}'])
        cmd += ['--', info.get('command','')]
        cmd += info.get('args', [])
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
