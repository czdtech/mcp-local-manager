# Changelog

## v1.1.1 (2025-11-04)

- CLI: 兼容 Python 3.9（添加 `from __future__ import annotations` 延迟注解求值）。
- 清理：移除未使用的 nvm 相关遗留代码与未定义引用。
- 行为：无破坏性变更；可用子命令不变（status/apply-cli/pick/ide-all/run/check）。
- 升级建议：
  - 重新链接或更新 PATH 到最新 `bin/mcpctl`。
  - 执行 `mcpctl -h` 验证；如需，运行 `mcpctl check` 做只读体检。

> 注：当前仓库基线采用显式最新版（`npx -y <package>@latest`）；如需稳定，可在中央清单对单个服务改回固定版本（`@x.y.z`）。
