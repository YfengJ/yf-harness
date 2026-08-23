# YF-Harness 实施计划

本项目按“每阶段保持可运行、完成后执行真实验证”的原则推进。详细的持续工作状态位于 `task_plan.md`，技术发现位于 `findings.md`。

状态：0.1.0 第一版九个阶段已于 2026-08-23 完成，验证证据见 `progress.md`。

## 阶段与里程碑

| 阶段 | 交付范围 | 阶段验收 |
|------|----------|----------|
| 0 | 仓库盘点、架构/风险/契约、计划与进度文件 | 范围、风险、验收和阶段 1 最小范围明确 |
| 1 | 包脚手架、领域模型、Provider 抽象、Mock、最小 CLI | `yfh run --provider mock "你好"` 流式成功，基础测试/静态检查通过 |
| 2 | 配置、OpenAI 兼容 Provider、SSE、重试、doctor | 假 HTTP 服务覆盖流式/错误，真实服务仅在显式环境变量下运行 |
| 3 | SQLite、迁移、Repository、会话/运行/用量、导出 | 重启恢复、interrupted 修复、Markdown/JSON 脱敏导出通过测试 |
| 4 | 文件/搜索/Patch/Shell/Git、审批、隔离、撤销 | 路径穿越/符号链接/拒绝审批/超时/脱敏安全测试通过 |
| 5 | Agent 状态机、原生/降级工具协议、预算与取消 | 工具往返、修复、循环、预算、中断等集成测试通过 |
| 6 | Textual TUI 与完整交互 | headless 测试覆盖消息、命令、切换、审批、快捷键和错误恢复 |
| 7 | ContextBuilder、指令、附件、预算和压缩 | 压缩前后关键目标/约束/修改/测试状态保持 |
| 8 | 结构化日志、Trace、统计、Eval、Replay | 无密钥 `yfh eval` 生成报告，回放默认不执行工具 |
| 9 | README、11 类学习文档、示例、CI、构建/安装 | Ruff、格式、类型、全量测试、wheel 安装和九类场景完成验收 |

## 阶段 1 最小可运行范围

阶段 1 只建立稳定核心，不提前引入数据库、真实网络、TUI 或高风险工具：

1. 标准 `pyproject.toml`、`src/yfharness`、`tests` 和控制台入口。
2. 强类型消息、内容、请求、能力、事件、工具调用/结果、用量、运行状态和统一异常。
3. Provider 抽象与注册表；MockProvider 支持固定/脚本化文本、流式增量、模拟工具调用与故障。
4. Typer 的 `run` 与基础发现命令，支持 stdout、JSON、stdin、超时和非零错误码。
5. 单元、异步、事件流与 Mock CLI 端到端测试。

## 架构原则

- 依赖方向：`cli/tui -> application services -> core <- providers/tools/storage`；核心领域不依赖 UI 或供应商字典。
- Provider 只输出统一 `ModelEvent`；Agent、TUI、存储和日志消费同一事件语义。
- 工具执行前依次经过注册、Schema 校验、模式策略、风险/审批、workspace 安全边界。
- 所有持久化经 Repository；迁移只前进且不破坏历史。
- 配置优先级固定为 CLI > 环境变量 > 项目配置 > 用户配置 > 默认值。

## 最终验收

最终必须证明：无密钥 TUI/Mock、真实兼容 Provider 配置、Plan 只读分析、Agent 审批写入与撤销、测试命令审批/超时、恶意访问阻止、上下文压缩、异常恢复，以及离线 Eval 报告九类场景。
