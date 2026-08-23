# Changelog

本项目遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)；版本号遵循语义化版本。

## [Unreleased]

- 等待社区反馈与首个补丁版本。

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
