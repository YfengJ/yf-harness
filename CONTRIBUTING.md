# 贡献指南

感谢参与 YF-Harness。提交前请先阅读 `docs/ARCHITECTURE.md`、`docs/SECURITY_MODEL.md` 和相关子系统文档。

## 开发环境

```bash
uv sync --extra dev
uv run ruff format .
uv run ruff check .
uv run mypy src
uv run pytest
uv run yfh eval
uv build
```

也可以使用 Python 3.12+ 的 venv 和 `pip install -e '.[dev]'`。测试必须离线可运行，不得依赖真实 API Key。

## 变更规则

- Provider 只能通过统一 `ModelEvent` 暴露输出；供应商原始字典不得穿透核心边界。
- 工具必须声明 Pydantic Schema、风险等级与只读属性；写入工具必须考虑 Diff、审批、原子性和撤销。
- SQLite 变更必须新增增量迁移，不能改写已发布迁移的含义。
- 公共 CLI、配置键、导出结构或默认策略变化需要文档、测试和 Changelog。
- 修复安全问题必须至少加入一个拒绝路径回归测试。

## Pull Request

说明用户可见行为、影响契约、风险、测试证据和已知限制。保持提交聚焦，不提交 `.env`、数据库、日志、构建产物或真实密钥。发布流程是：更新版本与 Changelog，运行完整质量门，构建 sdist/wheel，在全新环境安装验证，再创建带签名标签和 release notes 的版本。
