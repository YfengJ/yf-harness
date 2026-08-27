# 项目智能、队列与恢复

YF-Harness 0.4 吸收 Codex、Claude Code 和 Cursor 的高价值工作流，但不复制会扩大权限或上传代码的
默认行为。核心目标是让“为什么读取这些内容、接下来会执行什么、修改了哪些文件、能否安全恢复”都可见。

## 项目规则链

有效规则按低到高优先级组装：

1. 用户配置目录的 `instructions.md`
2. 工作区 `YF_HARNESS.md`
3. 从工作区到相关文件目录的 `CLAUDE.md`
4. `.cursor/rules/*.mdc` 中 `alwaysApply: true` 或 glob 命中的规则
5. 从工作区到相关文件目录的 `AGENTS.override.md` / `AGENTS.md`
6. `.yfh/instructions.md` 本地覆盖

同一目录中 `AGENTS.override.md` 会替代 `AGENTS.md`。嵌套规则只在用户明确引用或本地索引选中该子树
文件时加载。每条来源、路径、作用域和估算 Token 都显示在桌面“上下文”标签。

规则文本属于不可信上下文：它可以指导模型，但不能跳过 `AgentMode`、`ApprovalPolicy`、工具 Schema、
`WorkspaceGuard` 或删除/Shell 的强制审批。

## 本地项目索引

索引优先使用 `git ls-files` 和 Git ignore 语义；非 Git 目录降级为有限文件遍历。排序信号包括文件名、
相对路径、UTF-8 文本样本中的词法命中，以及已修改文件的小幅加权。构建产物、虚拟环境、依赖目录、
二进制和大型归档默认排除。索引没有网络请求、embedding 服务或持久化上传。

自动选择只补充上下文，不替代 Agent 自己使用搜索/读取工具。选择结果进入 `ContextSnapshot.sources`，
CLI JSON 与桌面都能检查。

## Plan、队列与分支

- Plan 和 Review 模式只获得只读工具。Plan 输出完成后，只有用户点击“执行此计划”才以 Agent 模式运行。
- 运行时发送的新消息进入 FIFO 队列，不会改变正在执行的工具调用。当前运行成功后自动取下一项。
- 取消或失败会暂停队列，避免错误状态连锁扩散；用户可以继续或清空。
- 会话分支复制消息并生成全新消息 ID，不复制工作区，也不会自动还原文件。

## 变更审查与恢复

工具写入、删除或移动时，YF-Harness 已把 before/after bytes 与 SHA-256 记录到 SQLite。审查层由这些
事实生成统一 Diff。恢复满足以下条件才执行：记录尚未撤销、类型可单独恢复、路径仍在 workspace、当前
内容哈希等于该记录的 after_hash。任何条件不满足都拒绝恢复，尤其不会覆盖 Agent 之后的人工编辑。

检查点是本地恢复工具，不等同于 Git commit；长期版本管理仍应使用 Git。
