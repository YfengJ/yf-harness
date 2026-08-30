# Changelog

本项目遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)；版本号遵循语义化版本。

## [Unreleased]

- 等待社区反馈与首个补丁版本。

## [0.8.0] - 2026-08-31

### Added

- Composer 内 Agent/Plan 快速切换、当前 Provider 模型选择器与真实上下文概览。
- 会话级 `/goal`：支持设置、查看、完成和清除，并随会话/分支持久化。
- SQLite v4 Goal 字段与 ContextSnapshot 结构化桌面属性。

### Changed

- Plan、模型和上下文从右侧控制台的低频设置提升到输入框底栏；控制台继续保留完整高级配置。
- 上下文入口展示真实 Token 预算、使用比例、来源数量和压缩状态，新会话明确显示待刷新。
- macOS 构建脚本统一校验短版本和 Bundle 构建版本，避免发布元数据缺项。

### Security

- 活动 Goal 作为显式会话上下文注入，但不能扩大 mode、Workflow、Hook、审批或 WorkspaceGuard 权限。
- Plan 快捷切换继续使用现有只读工具边界，必须经过显式 Plan→Execute 才能进入写入模式。

## [0.7.0] - 2026-08-30

### Changed

- 原生桌面 App 完整重构为“精密编辑台”：紧凑任务导航、项目标题栏、编辑稿式回答和更聚焦的 Composer。
- Provider、模型、工作流、上下文和文件变更移入按需控制台，默认不再持续挤压主对话画布。
- 空会话改为任务启动台；项目技能、图片、队列、审批和安全边界保持原有执行契约。

### Added

- `Ctrl+.` 快速打开或收起控制台；`Esc` 在运行中继续优先取消任务。
- 打包截图支持按预览标签自动展开控制台，并新增真实 Inspector 截图回归测试。

## [0.6.0] - 2026-08-30

### Added

- 统一发现 YF-Harness、Codex、Claude Code 与 Cursor 的工作区项目技能/命令。
- 桌面输入框 `$` 技能面板，支持实时过滤、键盘选择、鼠标选择和来源说明。
- CLI `skills list/show`、`run --skill`，以及 TUI `/skills`、`/skill`。
- 按 Agent run 整组恢复文件变更，支持同一路径多次修改的逆序回退。
- 原生项目文件夹选择器、最近 workspace 恢复和 workspace 级会话隔离。
- 两个经过校验的仓库示例技能：变更审查与发布准备。

### Changed

- 上下文 Trace 只保存组成、Token 与压缩元数据，不再保存完整消息、附件或技能正文。
- 桌面变更面板同时提供单文件撤销和整次运行撤销；版本与 Bundle 元数据升级为 0.6.0。

### Security

- 只扫描工作区技能，不读取用户主目录；拒绝符号链接、无效名称、二进制和超限文件。
- 完整技能正文仅在显式调用后加载进模型上下文；同名技能要求 `source:name` 消歧。
- 技能的工具声明不能扩大 Workflow、Policy、审批或 WorkspaceGuard，附带脚本不会自动执行。
- 整组撤销先模拟全部哈希状态；任一冲突会在写入前取消，数据库状态成组提交。
- SQLite v3 为新会话记录 workspace；桌面/TUI 不再把其他项目历史混入当前工作区。

## [0.5.0] - 2026-08-28

### Added

- 版本化 Workflow Profile，统一模式、审批、工具 allow/deny 和声明式 Pre/Post Hook。
- CLI、TUI 和桌面工作台的 Workflow 选择与可见工具说明。
- PNG/JPEG/GIF/WebP 附件，支持本地记录和显式授权的 OpenAI-compatible 图片输入。
- 最小 MCP stdio 发现/调用层，以及 workspace 内静态插件 manifest 发现。

### Changed

- 自动文件上下文使用独立 Token 份额，大项目中会截断而不是挤爆整个请求。
- 项目索引缓存文件样本，并按 mtime/大小使缓存失效。
- macOS 部署明确排除 WebEngine/Quick3D 等未使用 Qt 模块，增加 320 MiB 体积门禁。

### Security

- Hook `allow` 不能覆盖 Policy 的 `ask`/`deny`，Post Hook 仅观察已发生结果。
- 图片发送前重新校验 workspace、魔数、大小与 SHA-256；默认不上传。
- MCP 服务必须显式启用；工具强制高风险审批，且仅传入配置的环境变量名。
- 插件始终以 `review_required` 发现，不自动执行 MCP、Hook 或声明权限。

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
