#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "$0")/.." && pwd)"
python3 "$DIR/bin/mcp-auto-sync.py" sync

# --- 追加：按中央清单为 droid 批量重注册（交互式 /mcp 面板读取注册表） ---
python3 - <<'PY'
import json, os, shutil, subprocess, sys
from pathlib import Path

home = Path.home()
central = home/'.mcp-central'/'config'/'mcp-servers.json'

def info(msg):
    print(f"[droid-sync] {msg}")

if shutil.which('droid') is None:
    info('跳过：未检测到 droid CLI（不在 PATH）。')
    sys.exit(0)

if not central.exists():
    info(f'跳过：缺少中央清单 {central}')
    sys.exit(0)

try:
    obj = json.loads(central.read_text(encoding='utf-8'))
except Exception as e:
    info(f'跳过：中央清单解析失败：{e}')
    sys.exit(0)

servers = obj.get('servers') or {}
items = [(k,v) for k,v in servers.items() if (v or {}).get('enabled', True)]
items.sort(key=lambda x: x[0])

# 兜底：playwright 输出目录
(home/'.mcp-central'/'logs'/'playwright').mkdir(parents=True, exist_ok=True)

ok, fail = 0, []
for name, info_map in items:
    cmd = (info_map or {}).get('command') or ''
    args = (info_map or {}).get('args') or []
    env_map = (info_map or {}).get('env') or {}

    # 先尝试移除（忽略错误）
    try:
        subprocess.run(['droid','mcp','remove',name], check=False,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
    except Exception:
        pass

    add = ['droid','mcp','add','--type','stdio', name]
    for k,v in env_map.items():
        add += ['--env', f'{k}={v}']
    add += ['--', cmd]
    add += list(map(str, args))

    try:
        r = subprocess.run(add, check=False, capture_output=True, text=True, timeout=45)
        if r.returncode == 0:
            ok += 1
        else:
            fail.append((name, r.returncode, (r.stderr or r.stdout or '').strip()))
    except Exception as e:
        fail.append((name, -1, str(e)))

if fail:
    info(f'完成：成功 {ok}，失败 {len(fail)} 项：')
    for n, rc, msg in fail:
        info(f'  - {n}: rc={rc} msg={msg[:200]}')
else:
    info(f'完成：成功 {ok}，全部就绪。')
PY

# --- 追加：目标端 env 精简（移除冗长 PATH，只保留必要键） ---
python3 - <<'PY'
import json, os, shutil
from pathlib import Path

home = Path.home()
targets = [
    home/'.cursor'/'mcp.json',
    home/'.gemini'/'settings.json',
    home/'.iflow'/'settings.json',
    home/'.claude'/'settings.json',
    home/'.factory'/'mcp.json',
]
# VS Code / Insiders
targets.append(home/'Library'/'Application Support'/'Code'/'User'/'mcp.json')
targets.append(home/'Library'/'Application Support'/'Code - Insiders'/'User'/'mcp.json')

def compact_env(obj: dict):
    # 支持两种顶层键：mcpServers / servers
    key = 'mcpServers' if isinstance(obj.get('mcpServers'), dict) else 'servers'
    servers = obj.get(key)
    if not isinstance(servers, dict):
        return False
    changed = False
    for name, entry in servers.items():
        if not isinstance(entry, dict):
            continue
        env = entry.get('env')
        if not isinstance(env, dict):
            continue
        keep = {}
        if name == 'chrome-devtools':
            for k in ('CHROME_DEVTOOLS_MCP_DISABLE_SANDBOX','CHROME_DEVTOOLS_MCP_EXTRA_ARGS'):
                if k in env:
                    keep[k] = env[k]
        # 其它服务不保留 env
        if keep:
            entry['env'] = keep
        else:
            entry.pop('env', None)
        changed = True
    return changed

changed_files = []
for p in targets:
    if not p.exists():
        continue
    try:
        data = json.loads(p.read_text(encoding='utf-8'))
    except Exception:
        continue
    if compact_env(data):
        # 备份一次
        try:
            shutil.copy2(p, p.with_suffix(p.suffix+'.envbak'))
        except Exception:
            pass
        p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        changed_files.append(str(p))

print('[env-compact] 已精简 env 于以下文件：')
for f in changed_files:
    print('[env-compact]  -', f)
if not changed_files:
    print('[env-compact] 无需变更')
PY

echo "MCP 同步完成（含 droid 重注册 + env 精简）。"
