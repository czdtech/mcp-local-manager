#!/usr/bin/env bash
set -euo pipefail

# 只读健康检查（跨 macOS/Linux）

python3 - "$@" <<'PY'
import json, os, shutil, subprocess, sys, platform
from pathlib import Path

HOME = Path.home()
OS = platform.system().lower()
OK, WARN, FAIL = 'OK', 'WARN', 'FAIL'
results = []

def add(status, scope, msg):
    results.append({'status': status, 'scope': scope, 'msg': msg})

def load_json(p: Path):
    try:
        return json.loads(p.read_text(encoding='utf-8')) if p.exists() else None
    except Exception as e:
        add(FAIL, str(p), f'JSON 解析失败: {e}')
        return None

def which_ok(cmd):
    if not cmd:
        return False, '(空)'
    p = Path(cmd)
    if p.is_absolute():
        return (p.exists() and os.access(p, os.X_OK)), str(p)
    found = shutil.which(cmd)
    return (found is not None), (found or cmd)

def load_central():
    p = HOME/'.mcp-central'/'config'/'mcp-servers.json'
    if not p.exists():
        add(FAIL, 'central', f'缺少中央清单: {p}')
        return {}
    try:
        obj = json.loads(p.read_text(encoding='utf-8'))
    except Exception as e:
        add(FAIL, 'central', f'解析失败: {e}')
        return {}
    servers = {}
    for name, info in (obj.get('servers') or {}).items():
        if not info.get('enabled', False):
            continue
        servers[name] = info
    if not servers:
        add(WARN, 'central', f'中央清单为空或全部 disabled: {p}')
    return servers

central = load_central()
central_names = set(central.keys())

for name, info in central.items():
    if 'command' in info:
        ok, path = which_ok(info['command'])
        add(OK if ok else FAIL, f'central:{name}', f'command: {path}')

def cmp(center, target, scope):
    c_cmd, t_cmd = center.get('command'), target.get('command')
    c_args, t_args = center.get('args', []), target.get('args', [])
    c_env,  t_env  = center.get('env', {}),  target.get('env', {})
    if (c_cmd or '') != (t_cmd or ''):
        add(WARN, scope, f'command 不一致: central={c_cmd} != target={t_cmd}')
    if list(c_args) != list(t_args):
        add(WARN, scope, f'args 不一致: central={c_args} != target={t_args}')
    miss_env = [k for k in c_env if k not in (t_env or {})]
    if miss_env:
        add(WARN, scope, f'env 缺失: {miss_env}')

# Codex
try:
    import tomllib
    p = HOME/'.codex'/'config.toml'
    if p.exists():
        conf = tomllib.loads(p.read_text(encoding='utf-8'))
        mcp = conf.get('mcp_servers', {}) or {}
        names = {n for n in mcp.keys() if not n.endswith('.env')}
        miss = sorted(central_names - names)
        extra = sorted(names - central_names)
        add(OK if not miss and not extra else WARN, 'codex:names', f'缺少={miss or "无"}; 多出={extra or "无"}')
        for n in sorted(central_names & names):
            t = mcp.get(n) or {}
            env = t.get('env', {}) if isinstance(t, dict) else {}
            cmp(central[n], {'command': t.get('command'), 'args': t.get('args', []), 'env': env}, f'codex:{n}')
except Exception as e:
    add(WARN, 'codex', f'无法读取: {e}')

# JSON 目标
def check_json(label, p: Path, key_servers='mcpServers'):
    obj = load_json(p)
    if obj is None:
        add(WARN, label, f'未找到或无法解析: {p}')
        return
    servers = obj.get(key_servers) or obj.get('servers') or {}
    names = set(servers.keys())
    miss = sorted(central_names - names)
    extra = sorted(names - central_names)
    add(OK if not miss and not extra else WARN, f'{label}:names', f'缺少={miss or "无"}; 多出={extra or "无"}')
    for n in sorted(central_names & names):
        cmp(central[n], servers.get(n) or {}, f'{label}:{n}')

check_json('gemini', HOME/'.gemini'/'settings.json', 'mcpServers')
check_json('iflow',  HOME/'.iflow'/'settings.json',  'mcpServers')
check_json('claude(file)', HOME/'.claude'/'settings.json', 'mcpServers')
check_json('droid',  HOME/'.factory'/'mcp.json', 'mcpServers')
check_json('cursor', HOME/'.cursor'/'mcp.json', 'mcpServers')

if OS == 'darwin':
    check_json('vscode(user)', HOME/'Library'/'Application Support'/'Code'/'User'/'mcp.json', 'servers')
    check_json('vscode(insiders)', HOME/'Library'/'Application Support'/'Code - Insiders'/'User'/'mcp.json', 'servers')
else:
    check_json('vscode(user)', HOME/'.config'/'Code'/'User'/'mcp.json', 'servers')
    check_json('vscode(insiders)', HOME/'.config'/'Code - Insiders'/'User'/'mcp.json', 'servers')

# Claude 已注册
try:
    out = subprocess.run(['claude','mcp','list'], capture_output=True, text=True, timeout=8)
    text = out.stdout or ''
    reg = set()
    for line in text.splitlines():
        if ':' in line:
            reg.add(line.split(':',1)[0].strip())
    miss = sorted(central_names - reg)
    add(OK if not miss else WARN, 'claude(registered)', f'缺少已注册={miss or "无"}')
except Exception as e:
    add(WARN, 'claude(registered)', f'无法读取：{e}')

# 汇总
rank = {OK:0, WARN:1, FAIL:2}
worst = OK
for r in results:
    worst = r['status'] if rank[r['status']] > rank[worst] else worst
pad = max((len(r['scope']) for r in results), default=6)
print('MCP 健康检查报告\n')
for r in results:
    print(f"[{r['status']}] {r['scope']:<{pad}} | {r['msg']}")
print(f"\n结论: {worst}")
sys.exit(0 if worst == OK else 1)
PY

