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
    assert 'run' in r.stdout


def test_help_has_run():
    r = _run({}, ['-h'])
    assert r.returncode == 0
    assert 'run' in r.stdout
