# Changelog

本项目遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)；版本号遵循语义化版本。

## [Unreleased]

- 等待社区反馈与首个补丁版本。

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
