#!/usr/bin/env python3
"""
Pytest 全局夹具：为所有测试隔离 HOME，避免写入真实用户目录。

说明：
- 许多测试会通过子进程调用 bin/mcp 或 mcp-auto-sync.py，并对
  如 ~/.cursor/mcp.json、~/.claude/settings.json 等文件进行读写。
- 这里用 autouse fixture 将 HOME 指向 pytest 提供的 tmp_path，
  确保所有子进程默认继承该环境，避免污染真实环境。
- 单个用例若需要覆盖，可在 subprocess.run(..., env=...) 中自行传入 HOME。
"""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import json
import pytest


@pytest.fixture(autouse=True)
def _isolate_home(tmp_path, monkeypatch):
    # 统一将 HOME 指向 pytest 的临时目录；子进程会继承该环境
    monkeypatch.setenv("HOME", str(tmp_path))
    # 交给测试用例执行
    # 为测试准备最小中心清单 ~/.mcp-central/config/mcp-servers.json
    central = Path(tmp_path) / '.mcp-central' / 'config' / 'mcp-servers.json'
    central.parent.mkdir(parents=True, exist_ok=True)
    # 使用仓库示例作为基线，保证包含 'filesystem' 等常用条目
    sample = Path(__file__).resolve().parents[1] / 'config' / 'mcp-servers.sample.json'
    if sample.exists():
        shutil.copy2(sample, central)
    else:
        # 兜底：写入一个极简的可用配置（仅 filesystem）
        minimal = {
            "version": "1.1.0",
            "description": "pytest minimal",
            "servers": {
                "filesystem": {"command": "npx", "args": ["-y", "mcp-server-filesystem@latest", "~/work"]}
            },
        }
        central.write_text(json.dumps(minimal), encoding='utf-8')
    yield
