# 贡献指南（Contributing）

感谢你愿意贡献！本项目面向 macOS/Linux，目标是“稳定不出错”，因此我们更看重：可复现、可回滚、可诊断。

## 开始之前

- 优先先开 Issue（Bug/需求）再提 PR，避免重复劳动。
- PR 尽量小而聚焦：一次解决一个问题。

## 开发环境

- Python：建议 3.11+（`bin/mcp` 会在旧版本上直接提示升级）。
- Node/npx：仅在你要运行 npx 启动的 MCP 服务时需要。

推荐使用 venv：

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements-dev.txt
```

## 本地质检（必做）

本仓库**不依赖线上 CI**，提交前请在本地跑完：

```bash
bash scripts/qa.sh
```

常用选项：

- 快速检查（跳过测试）：`bash scripts/qa.sh --fast`
- 自动修复（会改代码）：`bash scripts/qa.sh --fix`
- 一键安装依赖：`bash scripts/qa.sh --install`

## 测试与隔离

- 测试会通过 `tests/conftest.py` 将 `HOME` 指向临时目录，避免污染真实环境。
- 修 Bug 时：请补一个能复现的测试用例，防止回归。

## 代码/脚本约定

- Python 代码主要在 `mcp_cli/`，格式化/静态检查默认只作用于该目录（避免扰动 `bin/` 与脚本）。
- 引入“写盘/外部命令”逻辑时：必须支持 `--dry-run` 或至少提供清晰的预览输出，并在写入前备份 `*.backup`。

## 提交说明

- 如果改动影响用户行为/默认配置，请更新 `CHANGELOG.md`。
- PR 描述里请包含：改动目的、验证方式（运行了哪些命令）、可能的边界/风险。
