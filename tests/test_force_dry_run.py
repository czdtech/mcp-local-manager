#!/usr/bin/env python3
"""交互式模式的可调用性（不再支持全局 dry-run/verbose）。"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

BIN = str(Path(__file__).resolve().parents[1] / 'bin' / 'mcp')


def _run_env(args: list[str], input_str: str = ''):
    return subprocess.run([BIN] + args, text=True, capture_output=True, input=input_str, timeout=30)


def test_run_interactive_callable():
    r = _run_env(['run'], input_str='\n\n\n')
    assert r.returncode in (0,1)


def test_clear_interactive_callable():
    r = _run_env(['clear'], input_str='\n'+'n\n')
    assert r.returncode == 0
