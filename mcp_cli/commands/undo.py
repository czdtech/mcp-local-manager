#!/usr/bin/env python3
"""undo 子命令实现：从 *.backup 恢复原始配置。"""

from __future__ import annotations

import re
import shutil
from pathlib import Path


def run(args) -> int:
    """从 *.backup 恢复；若未提供 dest，尝试基于文件名推断原路径。"""
    backup_path = Path(args.backup).expanduser()
    dest = Path(args.dest).expanduser() if getattr(args, "dest", None) else None
    if not backup_path.exists():
        print(f"[ERR] 备份文件不存在: {backup_path}")
        return 1

    if dest is None:
        name = backup_path.name
        # 先去掉 .backup 尾缀
        if name.endswith(".backup"):
            name = name[:-7]
        # 兼容旧格式：config.json.20251125_143022.backup / config.20251125_143022.backup
        m = re.match(r"^(?P<base>.+)\.(?P<ts>\d{8}_\d{6})$", name)
        base = m.group("base") if m else name
        dest = backup_path.with_name(base)

    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(backup_path, dest)
        print(f"[OK] 已恢复到: {dest}")
        return 0
    except Exception as e:
        print(f"[ERR] 恢复失败: {e}")
        return 1
