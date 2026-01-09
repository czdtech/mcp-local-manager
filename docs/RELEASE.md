# 发版指南（维护者）

本项目默认跟随 `npx ...@latest`，稳定性更多依赖“发布流程 + 快速回滚/修复”。本指南给出一个最小、可复现的发版步骤。

## 发版前检查（必做）

1) 本地质检：

```bash
bash scripts/qa.sh
```

2) 冒烟验证（建议至少覆盖一次）：

- 全新目录 `git clone` 后运行安装脚本：`bash scripts/install-mac.sh`
- 关键命令：`mcp --help`、`mcp check`、`mcp status <client>`、`mcp doctor --client <client>`

> 提示：脚本名为 `install-mac.sh`，但内部会按 `uname` 分支处理 Linux 路径；如你要正式承诺 Linux 支持，建议在 Linux 环境也跑一遍冒烟。

## 版本号与 Changelog

- 版本号建议使用语义化版本：`vMAJOR.MINOR.PATCH`
  - PATCH：修 bug/兼容性/排障
  - MINOR：新增功能（向后兼容）
  - MAJOR：破坏性变更
- 更新 `CHANGELOG.md`：新增一节并写清楚“对用户的影响”和“升级注意事项”。

## 打 Tag / 发布

（示例）

```bash
git tag vX.Y.Z
git push origin vX.Y.Z
```

发布说明建议直接复用 `CHANGELOG.md` 对应版本的要点。

## 当 `@latest` 上游破坏时怎么处理

优先级建议：

1) 能在项目侧规避：补兼容/降级逻辑，发 PATCH。
2) 不能规避：在文档里给出临时 pin 方案（把对应 `npx` 包从 `@latest` 改为固定版本），并在下一版恢复。
3) 给用户明确回滚方式：利用 `*.backup` + `mcp undo`。
