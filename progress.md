# YF-Harness 项目进度

## 当前状态

- 当前阶段：第一版完成
- 整体状态：可安装、可运行、可测试、可发布
- 初始仓库：空目录、非 Git 仓库
- 当前风险：P1（安全边界、子进程、持久化、CLI/TUI 公共契约）

## 已完成

- 完整解析项目规格和完成定义。
- 建立阶段 0–9 的实施顺序、阶段验收与最终验收映射。
- 建立变更简报、风险基线、公共契约和安全契约。
- 确认阶段 1 的最小可运行范围。
- 完成阶段 0 的规划、风险、契约和验收基线。

## 当前进行

- 已搭建 `pyproject.toml`、`src/yfharness` 和 `tests`。
- 已实现领域模型、统一事件、Provider 抽象/注册表、MockProvider 和最小 Typer CLI。
- 阶段 1 的静态检查、15 项测试和 Mock CLI 验收均通过。
- 阶段 2 已实现配置、环境插值/脱敏、OpenAI 兼容流式/非流式、重试和 Doctor。
- 阶段 2 的静态检查、23 项测试和 CLI 回归均通过。
- 阶段 3 已实现 SQLite schema/迁移、Repository、CLI 会话恢复/搜索/归档/删除/导出与 interrupted 恢复。
- 阶段 3 的静态检查、28 项测试和 Doctor schema smoke 均通过。
- 阶段 4 已实现 15 个真实工具、审批策略、原子写入/撤销、路径和符号链接隔离、Shell 超时/环境脱敏及变更持久化接口。
- 阶段 4 的静态检查、47 项测试、真实 Git 与工具发现 smoke 均通过。
- 阶段 5 已实现显式状态机、原生/严格降级工具协议、修复/重试、步骤/工具/时间/Token/成本预算、循环检测和取消。
- CLI 已切换到 AgentRunner；全量 64 项测试与真实 CLI/持久化 smoke 通过。
- 阶段 6 已实现 Textual 三栏响应式界面、多行输入/历史、会话、流式回答、工具折叠、审批 Diff、设置、诊断、帮助和完整 Slash Command 分发。
- TUI headless MockProvider 与小终端行为测试通过；全量 70 项测试通过。
- 阶段 7 已实现三层项目指令、手动/自动文件上下文、Token 预算、自动和手动结构化压缩，并接入 CLI/TUI。
- 上下文关键约束/文件/测试/下一步保持测试通过；全量 75 项测试通过。
- 阶段 8 已实现轮转文本/JSONL 脱敏日志、Trace、请求/工具/审批/用量/上下文记录、只读 Replay 和 20 类离线 Eval。
- 实际 `yfh eval` 20/20 通过；全量 78 项测试、Ruff、mypy 通过。
- 阶段 9 已完成 README、Changelog、贡献说明、13 份学习/设计文档、截图约定和 3 OS × 2 Python 的 CI。
- `run --file` 与无 TUI `chat` 已补齐并纳入集成测试。
- 第一版九类验收由 80 项测试、20 类 Eval、CLI/TUI smoke、构建和全新 venv wheel 安装共同覆盖。

## 实际验证记录

| 日期 | 命令/检查 | 结果 |
|------|-----------|------|
| 2026-08-23 | 初始文件盘点 | 目录为空 |
| 2026-08-23 | Git 状态 | 当前目录不是 Git 仓库 |
| 2026-08-23 | Change Radar 初扫 | 启发式 P3/0；因目标风险人工校准为 P1 |
| 2026-08-23 | `uv sync --extra dev` | 成功，安装 40 个包并构建 editable 项目 |
| 2026-08-23 | `uv run pytest -q` | 15 passed |
| 2026-08-23 | `uv run mypy src` | Success，无类型错误 |
| 2026-08-23 | Ruff 第一轮 | 11 个 lint/15 个格式问题，正在修复 |
| 2026-08-23 | `uv run ruff check .` | All checks passed |
| 2026-08-23 | `uv run ruff format --check .` | 20 files already formatted |
| 2026-08-23 | 修正后 `uv run mypy src` | Success，无类型错误 |
| 2026-08-23 | 修正后 `uv run pytest -q` | 15 passed in 0.07s |
| 2026-08-23 | `uv run yfh run --provider mock "你好"` | 成功流式输出离线回答 |
| 2026-08-23 | 阶段 2 `uv run ruff check .` | All checks passed |
| 2026-08-23 | 阶段 2 `uv run ruff format --check .` | 28 files already formatted |
| 2026-08-23 | 阶段 2 `uv run mypy src` | Success，17 个源码文件无错误 |
| 2026-08-23 | 阶段 2 `uv run pytest -q` | 23 passed in 0.34s |
| 2026-08-23 | 阶段 3 `uv run ruff check .` | All checks passed |
| 2026-08-23 | 阶段 3 `uv run mypy src` | Success，22 个源码文件无错误 |
| 2026-08-23 | 阶段 3 `uv run pytest -q` | 28 passed in 0.38s |
| 2026-08-23 | 阶段 4 `uv run ruff check .` | All checks passed |
| 2026-08-23 | 阶段 4 `uv run mypy src` | Success，33 个源码文件无错误 |
| 2026-08-23 | 阶段 4 `uv run pytest -q` | 47 passed in 1.40s |
| 2026-08-23 | `uv run yfh tools list` | 15 个要求工具均已注册并显示风险/只读属性 |
| 2026-08-23 | 阶段 5 `uv run ruff check .` / mypy | 全部通过，37 个源码文件无类型错误 |
| 2026-08-23 | 阶段 5 `uv run pytest -q` | 64 passed in 1.72s |
| 2026-08-23 | `uv run yfh run --no-save --mode agent` | AgentRunner CLI 流式成功 |
| 2026-08-23 | 阶段 6 TUI 专项 | 6 passed，含真实 Mock run、快捷键和响应式布局 |
| 2026-08-23 | 阶段 6全量 `pytest` | 70 passed in 2.51s；Ruff/mypy 同时通过 |
| 2026-08-23 | 阶段 7专项 | 17 passed，覆盖指令优先级、附件隔离、预算压缩、Agent/TUI 回归 |
| 2026-08-23 | 阶段 7全量 | 75 passed in 2.43s；Ruff/mypy 通过 |
| 2026-08-23 | 实际 `yfh eval` | 20/20，通过率 100%，约 0.098s，生成 JSON 报告 |
| 2026-08-23 | 阶段 8全量 | 78 passed in 2.63s；53 个源码文件 mypy 无错误，Ruff 通过 |
| 2026-08-23 | 最终 Ruff/格式/mypy | 全部通过；95 个文件格式正确，53 个源码文件无类型错误 |
| 2026-08-23 | 最终 `pytest -q` | 80 passed in 2.62s |
| 2026-08-23 | 最终覆盖率 | 80 passed；全项目 80%，核心 Agent 88%、Context 84%、Protocol 84% |
| 2026-08-23 | 最终 `yfh eval` | 20/20，100%，0.104s；包含读写/Patch/审批/安全/取消/恢复 |
| 2026-08-23 | `uv build` | 成功生成 0.1.0 sdist 和 wheel |
| 2026-08-23 | 全新 venv wheel 安装 | uv 安装 25 个运行依赖；version、Mock run、隔离 Doctor 全部通过 |
| 2026-08-23 | 最终 CLI matrix | help、JSON、stdin、file、tools、doctor 均通过 |
| 2026-08-23 | 最终 Change Radar | 非 Git 目录启发式 P3/0；人工仍按 P1 安全契约完成验证 |
| 2026-08-23 | TUI Worker 严格回归 | 专项连续 5 次通过；全量用未回收协程警告即失败模式 80 passed |
| 2026-08-23 | 最终发布包内容 | 重建 sdist/wheel；确认 README、License、Changelog、docs、CLI、typed marker、入口点 |
| 2026-08-23 | 发布前优化测试 | 85 passed；精确覆盖率由 79.56% 提升至 81.19%，CI 固定 80% 门槛 |
| 2026-08-23 | 发布元数据优化 | 增加 GitHub URLs/Python 3.13 classifier；sdist 排除内部规划记录 |

## 错误与修复

- Ruff 将中文文案中的全角标点标为易混淆字符：保留面向中文用户的标点，并在配置中显式列出允许字符。
- Ruff 要求 Python 3.12 `type` 别名与异步超时参数命名：已按规则修正。
- 初次将 `allowed-confusables` 写成 TOML 子表导致解析失败：依据错误信息改为 lint 配置中的字符列表。
- 阶段 2 的组合补丁因 Ruff 格式化后的上下文不匹配被原子拒绝：读取精确内容后拆成小补丁应用，没有发生部分覆盖。
- 阶段 2 首轮质量检查：23 项测试、Doctor、配置展示通过；mypy 发现局部联合类型未充分收窄，Ruff 发现中文逗号和两条长测试数据，已针对性修正。
- 一次质量检查编排脚本存在 JavaScript 语法错误，项目命令未执行；拆分为格式化与并行检查两次调用后成功运行。
- 阶段 3 首轮行为测试 28 项全部通过；mypy 发现 Repository 的 `list` 方法遮蔽内置类型名和 CLI 分支可空类型，已改用明确类型。
- Doctor smoke 创建的临时数据目录已安全删除；环境拒绝 `rm -rf` 后改用逐文件删除和 `rmdir`。
- 阶段 4 首次静态检查 Ruff 通过；mypy 的 30 条输出均由子进程 kwargs 使用 `object` 导致重载无法推断，已收窄为适合 kwargs 的动态容器。
- TUI 首次 headless 启动发现 Textual 1.0 不支持 CSS `@media`；改为 `on_resize` 中实际控制侧栏和状态栏显隐。
- TUI 弹窗测试发现 App 高优先级 `Esc` 抢占 ModalScreen；移除该优先级，让帮助/审批/设置弹窗先处理返回键。
- Eval 自动化首次 19/20：符号链接用例在共享临时父目录创建固定名 `outside`，被前次运行污染；改为独立临时外部目录并自动回收。
- 系统 pip 在全新 venv 下载依赖时遇到本机 SSL CA 验证失败；uv 使用自己的受信传输在另一全新 venv 成功解析、安装同一 wheel 并运行，确认产物和依赖元数据有效。
- 最终全量复跑偶发 Textual Worker 退出上下文警告；集成测试改为等待完整 Worker（含 Trace 和会话刷新）结束，专项连续 5 次及全量严格警告模式均无告警。

> 只有实际执行过的命令才会进入本表；后续每阶段完成后同步更新。
