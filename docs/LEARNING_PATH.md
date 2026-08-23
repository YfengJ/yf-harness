# 学习路线

推荐用一个 Mock 请求贯穿代码，每阶段都先运行邻近测试，再做一个小实验并检查 Trace。

## 阶段 1：领域模型与事件

- 目标：认识跨模块稳定语言。
- 核心概念：Message、ModelEvent、ToolCall、ToolResult、Usage、错误归一化。
- 相关文件：`core/models.py`、`core/events.py`、`core/exceptions.py`。
- 实践题：给 Usage 增加一个可选展示字段而不污染 Provider 原始数据。
- 验收问题：为什么供应商响应字典不能成为 UI 契约？

## 阶段 2：Provider 适配

- 目标：理解外部 HTTP/SSE 如何变成统一事件。
- 核心概念：异步生成器、SSE 分片、能力声明、首事件前重试、Mock。
- 相关文件：`providers/base.py`、`mock.py`、`openai_compatible.py`、`registry.py`。
- 实践题：让 Mock 以不同分片输出同一文本，确认最终结果不变。
- 验收问题：流式输出一半后为什么通常不能自动重试？

## 阶段 3：Agent Loop

- 目标：能逐状态解释一次完整运行。
- 核心概念：状态机、工具回填、修复、取消、步骤/时间/Token/成本预算、循环检测。
- 相关文件：`core/agent.py`、`core/agent_events.py`、`core/tool_protocol.py`。
- 实践题：降低最大步骤数并构造重复工具脚本。
- 验收问题：如何证明工具副作用没有因重试执行两次？

## 阶段 4：工具与安全

- 目标：区分“格式正确”和“获准执行”。
- 核心概念：Schema、注册表、Policy、Approval、WorkspaceGuard、原子写入、进程组。
- 相关文件：`tools/`、`core/policies.py`、`tui/screens/approval.py`。
- 实践题：新增只读行数统计工具，并补正常、未知参数和越界测试。
- 验收问题：符号链接为何会绕过朴素字符串前缀检查？

## 阶段 5：持久化与恢复

- 目标：理解运行事实如何保存、导出与恢复。
- 核心概念：增量迁移、Repository、事务、interrupted、文件变更、只读 Replay。
- 相关文件：`storage/database.py`、`migrations.py`、`repositories.py`。
- 实践题：创建会话、运行一次 Mock、导出并逐字段对应数据库记录。
- 验收问题：为什么不能在 CLI 中散落 SQL？崩溃后 running 如何处理？

## 阶段 6：上下文工程

- 目标：知道模型实际看到了什么以及为何被选择。
- 核心概念：指令优先级、附件、自动提及、Token 估算、八字段压缩。
- 相关文件：`core/context.py`、`core/compaction.py`、`core/prompts.py`。
- 实践题：构造超预算历史，验证关键禁止项和测试状态仍保留。
- 验收问题：摘要如何减少语义漂移？为什么不能默认加入整个仓库？

## 阶段 7：CLI 与 TUI

- 目标：理解两个界面如何共享同一核心。
- 核心概念：Typer 命令、Textual 消息循环、异步 Worker、流式渲染、Modal、响应式布局。
- 相关文件：`cli.py`、`tui/application.py`、`tui/commands.py`、`tui/screens/`。
- 实践题：增加一个只读状态栏字段并编写 headless pilot 测试。
- 验收问题：为什么 UI 主线程不能执行 Shell？`Ctrl+C` 应取消哪一层？

## 阶段 8：观测、测试与发布

- 目标：把产品行为与可重复证据连接起来。
- 核心概念：递归脱敏、Trace、用量/成本、Replay、单元/集成/安全测试、Eval、wheel。
- 相关文件：`observability/`、`evals/`、`tests/`、`.github/workflows/ci.yml`。
- 实践题：新增一个“审批拒绝且文件不变”的离线 Eval，构建 wheel 后在新 venv 验证。
- 验收问题：Eval 与单元测试如何分工？哪些真实 Provider 测试不应进入普通 CI？

完成路线后，应能从用户输入开始解释：上下文如何形成、Provider 如何流式、谁批准副作用、状态如何落库、失败如何恢复、最终证据在哪里。

## 我应该理解什么

从边界到状态机、从副作用到证据的完整因果链，而不是孤立类名。

## 我可以修改什么来做实验

依次修改 Mock 分片、步骤预算和只读工具，每次只改变一个变量并比较测试与 Trace。

## 常见 Bug

只看 TUI 猜业务、从真实 API 开始调试、同时修改多个边界导致无法归因。

## 面试可能如何提问

请从用户输入开始描述一次 Agent 运行，包含错误、审批、持久化和取消。

## 一个动手练习

运行一次 Mock CLI，导出会话，再用代码和文档逐字段解释完整生命周期。
