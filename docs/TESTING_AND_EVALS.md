# 测试与 Evals

测试分为四层：纯领域/解析/策略单元测试；SQLite、假 HTTP、CLI 和 Textual 集成测试；路径、符号链接、审批与脱敏安全回归；20 类离线 Eval。普通验证不访问真实模型，因而快速、确定且不会消耗费用。

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest
uv run pytest --cov=yfharness --cov-report=term-missing
uv run yfh eval --output eval-report.json
uv build
```

Eval 检查回答、工具选择、参数、拒绝、超限、协议修复、路径安全、压缩和取消等行为，输出机器可读 JSON。它不是单元测试替代品：失败报告用于定位系统行为，细节仍由邻近测试固定。Replay 默认只读，用保存的 Trace 检查历史；只有显式 `--execute` 并确认才重放工具。

真实 Provider smoke 应由维护者在隔离环境手动启用，使用短请求、费用上限和专用 Key；CI 不要求秘密也不录制远端响应中的敏感信息。

## 我应该理解什么

单元测试验证局部契约，Eval 验证完整行为；二者失败的诊断粒度不同。

## 我可以修改什么来做实验

给 Eval 添加一个故障脚本，对比报告字段和对应单元测试。

## 常见 Bug

Eval 依赖共享临时目录、测试意外联网、只断言退出码、快照掩盖安全差异。

## 面试可能如何提问

Agent 系统如何做确定性测试？Evals 与传统测试怎样分工？

## 一个动手练习

新增一个“审批拒绝后无文件变化”的 Eval，并验证报告可重复。
