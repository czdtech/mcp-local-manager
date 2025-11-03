#!/usr/bin/env bash
set -euo pipefail

# 只读健康检查（跨 macOS/Linux）

python3 - "$@" <<'PY'
import json, os, shutil, subprocess, sys, platform, re
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

def parse_codex_toml_text(text: str):
    """最小 TOML 解析：仅提取 [mcp_servers.*] 与其 .env 的 command/args/env，用于体检。
    不依赖第三方库，兼容 3.10-。
    """
    servers = {}
    cur = None
    cur_env = None
    in_env = False
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        m = re.match(r"^\[mcp_servers\.([^\]]+)\]$", line)
        if m:
            name = m.group(1)
            if name.endswith('.env'):
                # 形如 [mcp_servers.NAME.env]
                env_name = name[:-4]
                cur = servers.setdefault(env_name, {})
                cur_env = cur.setdefault('env', {})
                in_env = True
            else:
                cur = servers.setdefault(name, {})
                cur_env = cur.setdefault('env', {})
                in_env = False
            continue
        # 键值
        if cur is None:
            continue
        # env 子表的行：KEY = "VAL"
        if in_env and re.match(r'^[A-Za-z_][A-Za-z0-9_]*\s*=\s*"', line):
            k, v = line.split('=', 1)
            k = k.strip()
            v = v.strip()
            if v.startswith('"') and v.endswith('"'):
                v = v[1:-1]
            cur_env[k] = v
            continue
        # 顶层键
        if line.startswith('command'):
            m2 = re.match(r'^command\s*=\s*"(.*)"\s*$', line)
            if m2:
                cur['command'] = m2.group(1)
        elif line.startswith('args'):
            m3 = re.match(r'^args\s*=\s*(\[.*\])\s*$', line)
            if m3:
                try:
                    cur['args'] = json.loads(m3.group(1))
                except Exception:
                    cur['args'] = []
    # 规范化
    for v in servers.values():
        v.setdefault('args', [])
        v.setdefault('env', {})
    return servers

# Codex（带 tomllib 回退到轻量解析）
try:
    p = HOME/'.codex'/'config.toml'
    if p.exists():
        text = p.read_text(encoding='utf-8')
        try:
            import tomllib  # Py3.11+
            conf = tomllib.loads(text)
            mcp = conf.get('mcp_servers', {}) or {}
            parsed = {}
            for n, t in mcp.items():
                if n.endswith('.env'):
                    continue
                env = mcp.get(f'{n}.env', {}) if isinstance(mcp, dict) else {}
                parsed[n] = {
                    'command': (t or {}).get('command'),
                    'args': (t or {}).get('args', []),
                    'env': env or {}
                }
        except Exception:
            parsed = parse_codex_toml_text(text)

        names = set(parsed.keys())
        miss = sorted(central_names - names)
        extra = sorted(names - central_names)
        add(OK if not miss and not extra else WARN, 'codex:names', f'缺少={miss or "无"}; 多出={extra or "无"}')
        for n in sorted(central_names & names):
            cmp(central[n], parsed.get(n) or {}, f'codex:{n}')
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

def claude_registered_names():
    # 优先 JSON，更稳健
    try:
        out = subprocess.run(['claude','mcp','list','--json'], capture_output=True, text=True, timeout=8)
        if out.returncode == 0 and (out.stdout or '').strip().startswith('['):
            arr = json.loads(out.stdout)
            return { (item.get('name') or '').strip() for item in arr if isinstance(item, dict) and item.get('name') }
    except Exception:
        pass
    # 回退到纯文本解析
    try:
        out = subprocess.run(['claude','mcp','list'], capture_output=True, text=True, timeout=30)
        text = (out.stdout or '') + "\n" + (out.stderr or '')
        reg = set()
        for line in text.splitlines():
            if ':' in line:
                reg.add(line.split(':',1)[0].strip())
        return reg
    except Exception:
        return set()

reg = claude_registered_names()
miss = sorted(central_names - reg)
add(OK if not miss else WARN, 'claude(registered)', f'缺少已注册={miss or "无"}')

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
