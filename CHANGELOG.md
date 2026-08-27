# Changelog

本项目遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)；版本号遵循语义化版本。

## [Unreleased]

- 等待社区反馈与首个补丁版本。

## [0.4.0] - 2026-08-27

### Added

- Codex `AGENTS.md`、Claude `CLAUDE.md`、Cursor `.mdc` Rules 与 YF-Harness 指令的统一、分层发现。
- 本地 Git 感知项目索引，以路径、内容和工作区修改状态自动选择相关上下文。
- 桌面运行中后续任务队列、Plan→Execute 显式执行、会话分支与上下文 Token/来源视图。
- 会话级文件变更审查、统一 Diff 和持久化检查点的冲突安全恢复。

### Changed

- 桌面右侧检查器重构为运行、上下文、变更三个连续工作区，版本升级为 0.4.0。
- CLI JSON 运行结果增加可解释的 `context` 摘要，不包含消息正文或密钥。

### Security

- 队列在取消或失败后暂停，不会继续隐式执行后续任务。
- 恢复文件前必须匹配 Agent 修改后的 SHA-256；检测到后续编辑即拒绝覆盖。
- 跨工具项目规则只影响模型上下文，不能扩大模式、工具或审批权限。

## [0.3.0] - 2026-08-24

### Added

- PySide6 + Qt Quick 原生桌面工作区，支持会话、流式消息、Provider/模型/模式/权限设置和取消。
- 桌面工具审批桥接，复用原有 AgentRunner、SQLite、Policy 与 WorkspaceGuard。
- `yfh desktop` / `yfh-desktop` 入口，以及 `desktop` 和 `desktop-build` 可选依赖。
- macOS 图标、`pyside6-deploy` 配置与一键 `.app` 构建/签名/启动验证脚本。
- 无头 QML smoke、真实 MockProvider 桌面运行测试和脱敏的真实 Bundle 截图。

### Changed

- 产品入口由终端优先改为桌面优先；Textual TUI 与无界面 CLI 继续兼容。
- CLI 单次运行支持外部事件、审批与 Runner 回调，供桌面 Bridge 复用而不复制核心流程。

## [0.2.0] - 2026-08-24

### Added

- LangChain 1.x、LlamaIndex Workflow 和 AutoGen AgentChat 的可选原生 Agent 适配器。
- `langchain`、`llamaindex`、`autogen` 与聚合 `frameworks` 安装 extra。
- `yfh frameworks list/doctor/run`，支持 MockProvider 离线运行和已有 OpenAI-compatible 配置。
- 统一 `FrameworkRequest` / `FrameworkResult`、版本发现、缺失依赖诊断和用量归一化。
- 三套框架的真实离线对象与伪 OpenAI-compatible HTTP 端到端契约测试。

### Security

- 框架适配器不注入本地工具，不能绕过现有 Policy、Approval 和 WorkspaceGuard。
- API Key 仍只从配置指定的环境变量读取，不新增配置或持久化密钥字段。

## [0.1.0] - 2026-08-23

### Added

- Provider 中立的流式事件协议、MockProvider 与 OpenAI 兼容 Provider。
- Chat、Plan、Agent、Review 四模式的显式 Agent 状态机。
- 15 个受策略、审批和 workspace 边界保护的本地工具。
- Textual TUI、无界面 CLI、SQLite 会话与完整 Trace。
- 上下文预算、结构化压缩、只读 Replay 与 20 类离线评测。
- 跨平台配置、轮转脱敏日志、测试、学习文档和 CI。

### Quality

- CI 强制执行 80% 精确覆盖率门槛并上传 XML 报告。
- 增加 Doctor、成本计算、CLI 发现命令和会话生命周期回归测试。
- 发布元数据关联源码仓库，sdist 排除内部规划记录。
- 修正 Windows mypy 平台裁剪，并以 `taskkill /T` 终止超时命令的子进程树。
- 统一 Patch 预览/执行的换行语义，并在应用 LF 补丁后保留目标文件的 CRLF。
- 升级 CI Actions 到官方当前稳定的 Node 24 版本，消除 Node 20 弃用告警。
- 控制台入口统一使用 UTF-8 标准流，避免 Windows 重定向输出使用 cp1252 时崩溃。
