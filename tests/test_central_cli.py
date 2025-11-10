#!/usr/bin/env python3
"""
中央清单管理（mcp central）集成测试。
依赖 tests/conftest.py 提供的 HOME 隔离与最小 central。
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

BIN = str(Path(__file__).resolve().parents[1] / 'bin' / 'mcp')


def run_cmd(args: list[str]):
    return subprocess.run([BIN] + args, text=True, capture_output=True, timeout=30)


def test_central_list_and_show_json():
    r = run_cmd(['central', 'list', '--json'])
    assert r.returncode == 0
    out = json.loads(r.stdout)
    assert 'servers' in out

    # pick a known from sample if present; fallback to first
    name = out['servers'][0]['name'] if out['servers'] else None
    if name:
        r2 = run_cmd(['central', 'show', name, '--json'])
        assert r2.returncode == 0
        j = json.loads(r2.stdout)
        assert name in j


def test_central_add_update_enable_disable_remove(tmp_path):
    # add
    r = run_cmd(['central', 'add', 'x1', '--command', 'npx', '--args', 'pkg@latest', '--json'])
    assert r.returncode == 0
    j = json.loads(r.stdout)
    assert j['added'] == 'x1'
    # update append arg and set env
    r = run_cmd(['central', 'update', 'x1', '--append-arg', 'foo', '--set-env', 'A=1', '--json'])
    assert r.returncode == 0
    j = json.loads(r.stdout)
    assert j['updated'] == 'x1'
    # enable/disable
    r = run_cmd(['central', 'disable', 'x1', '--json'])
    assert r.returncode == 0
    r = run_cmd(['central', 'enable', 'x1', '--json'])
    assert r.returncode == 0
    # dup
    r = run_cmd(['central', 'dup', 'x1', 'x2', '--json'])
    assert r.returncode == 0
    j = json.loads(r.stdout)
    assert j['duplicated']['to'] == 'x2'
    # remove
    r = run_cmd(['central', 'remove', 'x2', '--json'])
    assert r.returncode == 0


def test_central_template_and_export_import(tmp_path):
    # template create fs2
    r = run_cmd(['central', 'template', 'filesystem', '--name', 'fs2', '--args', '~/code', '~/.mcp-central', '--json'])
    assert r.returncode == 0
    j = json.loads(r.stdout)
    assert j['created'] == 'fs2'
    # export
    out = tmp_path / 'central-export.json'
    r = run_cmd(['central', 'export', '--file', str(out)])
    assert r.returncode == 0
    assert out.exists()
    # import merge prefer incoming (fs2 will be same, but should succeed)
    r = run_cmd(['central', 'import', '--file', str(out), '--json'])
    assert r.returncode == 0


def test_central_validate_and_doctor_json():
    r = run_cmd(['central', 'validate', '--json'])
    assert r.returncode in (0, 1)  # 根据环境可能缺少 jsonschema
    j = json.loads(r.stdout)
    assert 'ok' in j
    r = run_cmd(['central', 'doctor', '--json'])
    # doctor 可能因为命令缺失返回 1（failed），但应有结构化输出
    assert r.returncode in (0, 1)
    j = json.loads(r.stdout)
    assert 'status' in j and 'servers' in j


def test_central_interactive_menu_quit():
    # 打开中央管理主菜单后直接退出
    r = subprocess.run([BIN, 'central'], input='0\n', text=True, capture_output=True, timeout=30)
    assert r.returncode == 0
