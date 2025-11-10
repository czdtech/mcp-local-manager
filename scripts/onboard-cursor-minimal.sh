#!/usr/bin/env bash
set -euo pipefail

# 目标：一键为新人完成“最小落地”
# - 仅 Cursor 启用：context7 + task-master-ai
# - 其它 CLI/IDE 全部裸奔（清空文件端、注册表与项目级覆盖）

HERE="$(cd "$(dirname "$0")/.." && pwd)"
export PATH="$HOME/.local/bin:$PATH"

echo "[1/6] 链接 mcp 到 ~/.local/bin ..."
mkdir -p "$HOME/.local/bin"
ln -sf "$HERE/bin/mcp" "$HOME/.local/bin/mcp"
command -v mcp >/dev/null 2>&1 || { echo "mcp 未就绪"; exit 1; }

echo "[2/6] 准备中央清单（若缺失则创建仅含两项）..."
CENTRAL="$HOME/.mcp-central/config/mcp-servers.json"
export CENTRAL
mkdir -p "$(dirname "$CENTRAL")"
if [[ ! -f "$CENTRAL" ]]; then
  cat >"$CENTRAL" <<JSON
{
  "version":"1.2.1",
  "servers":{
    "context7":{
      "enabled":true,
      "type":"local",
      "command":"npx",
      "args":["-y","@upstash/context7-mcp@latest"]
    },
    "task-master-ai":{
      "enabled":true,
      "type":"local",
      "command":"npx",
      "args":["-y","task-master-ai@latest"]
    }
  }
}
JSON
  echo "  - 已创建最小中央清单：$CENTRAL"
else
  # 若已存在，确保包含两项
  python3 - <<'PY'
import json,os
from pathlib import Path
p=Path(os.environ['CENTRAL'])
obj=json.loads(p.read_text(encoding='utf-8')) if p.exists() else {"servers":{}}
srv=obj.setdefault('servers',{})
srv.setdefault('context7', {"enabled":True,"type":"local","command":"npx","args":["-y","@upstash/context7-mcp@latest"]})
srv.setdefault('task-master-ai', {"enabled":True,"type":"local","command":"npx","args":["-y","task-master-ai@latest"]})
p.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
print('[ok] 已确保中央清单包含 context7 与 task-master-ai')
PY
fi

echo "[3/6] 仅为 Cursor 落地两项 ..."
echo "[info] 进入交互选择，将 Cursor 下发所需 MCP："
mcp run

echo "[4/6] 清空其它 CLI/IDE（裸奔）..."
clean_json(){
  local path="$1" key="$2"
  [[ -f "$path" ]] && cp -p "$path" "$path.minbackup" || true
  python3 - "$path" "$key" <<'PY'
import json,sys,os
p=sys.argv[1]; key=sys.argv[2]
obj={}
if os.path.exists(p):
  try: obj=json.loads(open(p,'r',encoding='utf-8').read())
  except Exception: obj={}
if key=='servers': obj['servers']={}
else: obj['mcpServers']={}
open(p,'w',encoding='utf-8').write(json.dumps(obj,ensure_ascii=False,indent=2))
PY
}
clean_json "$HOME/.gemini/settings.json" mcpServers || true
clean_json "$HOME/.iflow/settings.json" mcpServers || true
clean_json "$HOME/.factory/mcp.json"   mcpServers || true
clean_json "$HOME/.claude/settings.json" mcpServers || true
clean_json "$HOME/Library/Application Support/Code/User/mcp.json" servers || true
clean_json "$HOME/Library/Application Support/Code - Insiders/User/mcp.json" servers || true

echo "[5/6] 清理 Codex MCP 段与 Claude 注册表/项目级覆盖 ..."
# Codex
python3 - <<'PY'
import re,shutil
from pathlib import Path
p=Path.home()/'.codex'/'config.toml'
if p.exists():
  old=p.read_text(encoding='utf-8')
  new=re.sub(r'(?ms)^\[mcp_servers\.[^\]]+\][\s\S]*?(?=^\[|\Z)','',old)
  new=re.sub(r"\n*# === MCP Servers 配置（由 MCP (?:Local Manager|Central) 生成）===\n(?:.|\n)*?(?=\n?# ===|\Z)","\n",new)
  if new!=old:
    shutil.copy2(p, p.with_suffix('.minbackup'))
    p.write_text(new,encoding='utf-8')
    print('[ok] 清空 Codex MCP 段')
  else:
    print('[ok] Codex 无需变更')
PY
# Claude 注册表
if command -v claude >/dev/null 2>&1; then
  for n in context7 task-master-ai codex-cli chrome-devtools filesystem playwright sequential-thinking serena; do
    claude mcp remove "$n" -s local >/dev/null 2>&1 || true
    claude mcp remove "$n" -s user  >/dev/null 2>&1 || true
    claude mcp remove "$n"          >/dev/null 2>&1 || true
  done
fi
# 项目级覆盖（~/.claude.json -> projects.*.mcpServers 清空）
python3 - <<'PY'
import json,os
from pathlib import Path
p=Path.home()/'.claude.json'
if p.exists():
  try:
    obj=json.loads(p.read_text(encoding='utf-8'))
  except Exception:
    obj=None
  if isinstance(obj, dict) and isinstance(obj.get('projects'), dict):
    changed=False
    for k,v in obj['projects'].items():
      if isinstance(v, dict) and isinstance(v.get('mcpServers'), dict):
        if v['mcpServers']:
          v['mcpServers']={}
          changed=True
    if changed:
      import shutil
      shutil.copy2(p, p.with_suffix('.projects.minbackup'))
      p.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
      print('[ok] 清空 ~/.claude.json projects.*.mcpServers')
PY

echo "[6/6] 复验 ..."
mcp status --client cursor
mcp status --client claude-file
mcp status --client claude-reg
mcp status --client codex
echo "\n完成：仅 Cursor 启用 context7+task-master-ai，其它均裸奔。"
