import os
import subprocess
from pathlib import Path

BIN = str(Path(__file__).resolve().parents[1] / 'bin' / 'mcp')


def _run(env: dict, args: list[str]):
    e = os.environ.copy()
    e.update(env)
    return subprocess.run([BIN] + args, text=True, capture_output=True, env=e)


def test_help_has_clear():
    r = _run({}, ['-h'])
    assert r.returncode == 0
    # 确认新增加的 clear 子命令出现在帮助信息中
    assert 'clear' in r.stdout


def test_help_has_run():
    r = _run({}, ['-h'])
    assert r.returncode == 0
    assert 'run' in r.stdout


def test_clear_dry_run_all_linux(tmp_path: Path):
    env = {
        'HOME': str(tmp_path),
        'MCP_OS': 'linux',
    }
    r = subprocess.run([BIN, 'clear'], input='\n'+'y\n', text=True, capture_output=True, env=env)
    assert r.returncode == 0
    # 核心路径（Linux）应出现
    assert str(tmp_path / '.config' / 'Code' / 'User' / 'mcp.json') in r.stdout
    assert str(tmp_path / '.config' / 'Code - Insiders' / 'User' / 'mcp.json') in r.stdout


def test_clear_dry_run_all_macos(tmp_path: Path):
    env = {
        'HOME': str(tmp_path),
        'MCP_OS': 'darwin',
    }
    r = subprocess.run([BIN, 'clear'], input='\n'+'y\n', text=True, capture_output=True, env=env)
    assert r.returncode == 0
    # 核心路径（macOS）应出现
    assert str(tmp_path / 'Library' / 'Application Support' / 'Code' / 'User' / 'mcp.json') in r.stdout
    assert str(tmp_path / 'Library' / 'Application Support' / 'Code - Insiders' / 'User' / 'mcp.json') in r.stdout
