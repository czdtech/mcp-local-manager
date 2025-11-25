# 开发指南（mcp-local-manager）

本项目自 v1.3 起逐步模块化，将 CLI 逻辑迁移至 `mcp_cli` 包，`bin/mcp` 仅负责参数解析与子命令分发。

## 目录结构

- bin/mcp：CLI 主入口（argparse）。将参数委托到 mcp_cli.commands.*。
- mcp_cli/
  - utils.py：通用工具与平台/路径/注册表探测函数（纯函数或可预测副作用）。
  - commands/
    - status.py：只读状态查看。
    - check.py：只读健康检查。
    - run.py：落地 MCP 配置（写入 + 可选外部命令）。
- bin/mcp-auto-sync.py：脚本版；bin/mcp_auto_sync.py：模块版（供测试导入）。

## 约定与设计

- 统一来源：~/.mcp-central/config/mcp-servers.json。
- 只改 MCP 段：不同目标仅写 MCP 专属字段，不触碰其他设置；写入前自动备份 *.backup。
- 交互优先：所有配置/管理操作均在交互中完成；预览与确认也在交互步骤内进行（不再提供 -n/--dry-run 全局参数）。
- Claude/Droid 注册表：实际对齐采用“remove → add”，DRY-RUN 输出预览命令。

## 开发环境

pip install -r requirements-dev.txt   # 包含 pytest / ruff / black / jsonschema

快速检查：

bash scripts/format.sh   # 仅格式化 mcp_cli
bash scripts/lint.sh     # 仅 lint mcp_cli
pytest -q                # 全量测试（tests/conftest.py 已隔离 HOME）

说明：pyproject.toml 限定 black/ruff 仅作用在 mcp_cli/，避免一次性扰动 bin/ 与测试脚本。

## 测试策略

- 单元：优先直接 import mcp_cli（例如 mcp_cli.utils、mcp_cli.commands.run）。
- 黑盒：保留对子进程 bin/mcp 的集成测试，覆盖 CLI 解析与用户输出。
- 环境隔离：tests/conftest.py 将 HOME 指向临时目录，并写入最小中心清单，避免污染真实环境。

## 迁移路线

- 阶段 1（完成）：status/check 模块化。
- 阶段 3（完成）：run 模块化。
- 后续（进行中）：逐步移除 bin/mcp 中历史兼容转发函数，并将相关单测从 bin 迁到 mcp_cli。

## 贡献约定

- 仅变更 mcp_cli/ 时，请运行 bash scripts/format.sh && bash scripts/lint.sh。
- 新增命令：在 mcp_cli/commands/<name>.py 实现并在 bin/mcp 中分发。
- 引入外部命令时，务必为 DRY-RUN 分支提供“预览命令输出”。
- 写盘前一律 backup()；异常需吞吐并打印中文提示，避免 CLI 崩溃。
