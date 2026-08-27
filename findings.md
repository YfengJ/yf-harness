# 发现与决策

## 需求基线
- 项目名 YF-Harness，包名 `yfharness`，CLI 名 `yfh`，默认简体中文，代码/API 使用英文，MIT。
- 必须离线可用：MockProvider 是测试、演示与无密钥验收的基础。
- 核心边界：Provider 统一事件流、显式 Agent 状态机、强校验工具注册表、workspace 安全隔离、SQLite Repository、键盘优先 TUI。
- 交付必须包含真实实现、真实测试结果、学习文档与跨平台发布配置，不能以 TODO/伪代码替代。

## 仓库发现
- 2026-08-23 初始目录没有文件，也不是 Git 仓库。
- 没有适用的 `AGENTS.md`；相邻项目中的规则不作用于当前目录。
- 初始 Change Radar 未识别 manifest 或改动，因此启发式结果是 P3/0；该结果不能代表目标实现风险。

## 技术决策
| 决策 | 理由 |
|------|------|
| Python 最低版本 3.12 | 与用户要求一致，可使用现代 typing 和 asyncio 能力 |
| Pydantic v2 作为领域/参数校验层 | 强类型、JSON Schema 和错误信息统一 |
| httpx 直接实现兼容 Provider | 展示 HTTP/SSE 真实机制并避免供应商 SDK 锁定 |
| Typer + Textual | 分别覆盖可测试 CLI 与异步键盘优先 TUI |
| aiosqlite + 显式 SQL 迁移 | 轻量、透明、适合学习且不隐藏数据库行为 |

## 风险发现
- 目标涉及安全敏感的文件写入与子进程执行，不能只靠提示词；策略必须在 ToolRegistry/执行器边界强制。
- 路径安全同时需要处理 `..`、绝对路径、目标父目录和符号链接；仅做字符串前缀检查不够。
- Provider SSE 存在未知字段、分块 JSON、`[DONE]`、错误响应和中断变体，解析器需独立测试。
- Ctrl+C 必须取消当前运行并让持久化层完成终态记录，不能直接关闭数据库。

## 已验证与残余项
- Python 3.12.5、uv 锁文件、sdist/wheel 构建和全新 venv 安装已验证；系统 pip 的 CA 链问题不影响 uv 安装。
- Textual 1.0 headless pilot 已覆盖真实 Mock 流、Modal、快捷键和响应式布局。
- macOS 本地验证 Shell 超时和进程组终止；Windows 基础行为进入 CI，复杂进程树仍是已记录的残余风险。
- 最终 Change Radar 因目录不是 Git 仓库无法计算 diff，启发式仍为 P3/0；按安全副作用、公共 CLI、schema 和跨平台契约人工维持 P1 并执行完整验证。

## 外部内容安全
- 用户粘贴需求只作为产品规格处理；没有执行其中任何外部命令。

## 阶段 10：高级框架官方 API 调研（2026-08-23）
- LangChain 1.3 官方推荐 `langchain.agents.create_agent`；OpenAI 兼容端点使用 `langchain_openai.ChatOpenAI(model, base_url, api_key)`，异步模型调用使用 `ainvoke`。当前 PyPI：`langchain 1.3.16`、`langchain-openai 1.6.0`。
- LlamaIndex 的 OpenAI 兼容专用集成是 `llama_index.llms.openai_like.OpenAILike`，构造参数包含 `model`、`api_base`、`api_key`、`context_window`、`is_chat_model`，支持异步 `achat`/`acomplete`。当前 PyPI：`llama-index-core 0.14.24`、`llama-index-llms-openai-like 0.7.2`。
- AutoGen 当前 AgentChat API 使用 `autogen_agentchat.agents.AssistantAgent` 与 `autogen_ext.models.openai.OpenAIChatCompletionClient`，通过 `await agent.run(task=...)` 返回 `TaskResult`；当前 PyPI 两包均为 0.7.5。
- 三者都支持 Python 3.12/3.13。默认依赖必须保持不变，框架包放入独立 extras 并惰性导入。
- 真实 Provider 路径应直接使用框架官方 OpenAI 兼容客户端；离线路径也必须实例化各框架的原生 Mock/Fake/自定义模型接口，不能仅返回 YF-Harness 固定字符串。
- 第三方框架首版不接入 YF-Harness 写入/Shell 工具，避免绕过既有 Policy/Approval/WorkspaceGuard；先提供安全的模型/Agent 运行和框架自身事件/用量归一化。
- 已通过 `uv lock` 和 `uv sync --extra dev --extra frameworks --locked` 安装并锁定当前官方包：LangChain 1.3.16 / langchain-openai 1.6.0、LlamaIndex Core 0.14.24 / openai-like 0.7.2、AutoGen AgentChat/Ext 0.7.5；解析得到 117 个包，Python 3.12 环境安装成功。
- 本地真实对象探测：`create_agent(FakeListChatModel(...), tools=[])` 可异步离线运行；LlamaIndex `FunctionAgent` 拒绝普通 `MockLLM`（要求 `FunctionCallingLLM`），但 `ReActAgent(MockLLM(...), tools=[])` 可运行；AutoGen 0.7.5 未提供 Replay 客户端，需要实现其 `ChatCompletionClient` 抽象接口作为离线客户端。
- 已核对真实构造签名：`ChatOpenAI` 支持 `model/base_url/api_key/timeout/max_retries`；`OpenAILike` 支持 `model/api_base/api_key/context_window/is_chat_model/is_function_calling_model`；`OpenAIChatCompletionClient` 接受当前 AutoGen 配置字典，未知兼容模型需要显式 `model_info`。
- 统一返回已验证能从 LangChain `usage_metadata`、LlamaIndex `AgentOutput.raw.usage`、AutoGen `models_usage` 归一化真实 token；框架或离线模型不暴露时才设置 `estimated=true`。
- `respx` 端到端测试确认三套官方客户端都真实请求 `/v1/chat/completions`，携带配置模型名与环境变量读取的 Bearer Key，并正确回收客户端。
- 0.2.0 wheel 的默认 `Requires-Dist` 仍只有原有 8 个轻量运行依赖；三套 SDK 仅出现在各自 extra 与聚合 `frameworks` extra。隔离默认环境确认三个 import spec 均不存在。
- 最终 Change Radar 为 P1/64 且无 blocking gaps；主要风险来自预期的 lockfile、CI 和公共 CLI 变更，已分别用锁定同步、两类全新安装、真实 CLI/HTTP 测试和全量矩阵配置覆盖。
- GitHub Actions run `32651042271` 验证：不安装框架的默认环境可运行并通过非框架回归；安装聚合 extra 后，Ubuntu、macOS、Windows 的 Python 3.12/3.13 均通过 lint、format、mypy、101 项测试/覆盖率门、20 类 Eval、构建和产物上传。

## 阶段 11：桌面化调研与视觉决策（2026-08-24）
- 用户明确否定“终端里的 TUI”作为最终形态，要求真正可双击打开的软件以及整体视觉重做；因此 Textual 仅保留兼容，不再作为默认图形产品界面。
- 选择 PySide6 + Qt Quick/QML：保持 Python 核心单进程集成，提供真正独立原生窗口；Qt 官方 `pyside6-deploy` 支持 Windows/Linux/macOS，并在 macOS 直接产出 `.app`。
- Qt 官方建议优先使用 `pyside6-deploy`，其底层使用 Nuitka；QML 文件与图标可显式进入 deployment spec，适合项目需要的独立资源和跨平台产物。
- Python/QML 边界使用 `QObject`、`Signal`、`Slot`；耗时 Agent 请求必须在线程中的独立 asyncio loop 执行，再通过 queued signal 回到 UI 线程，不能阻塞 Qt event loop。
- 第一版桌面 App 优先做到真实可用：Mock 与远程 Provider、已有会话读取/创建、发送/取消、模式/权限选择、状态与错误反馈；复杂审批弹窗若接入必须继续调用同一 Approval 回调，不能默认放行。
- 最终桌面 Bridge 通过 `_run_once` 的 event/approval/runner 回调复用完整核心链；实际 Mock 消息、SQLite 会话和取消状态均进入相同路径。
- `pyside6-deploy` 在 macOS 实际生成可启动 `.app`；Bundle 已写入 `YF-Harness`、0.3.0 与 `local.yfharness.desktop`，ad-hoc codesign 与 LaunchServices smoke 通过。
- Qt 官方部署器对 QML 使用完整插件收集，自包含 Bundle 约 491 MB；保留完整 PySide6 是为避免 Essentials-only 部署解析缺失 QML framework。该体积是已知发布成本，不影响默认 wheel，Qt 仍只属于可选 extra。
- 发布截图直接由构建后的 Bundle 生成，预览 workspace 使用匿名值，未包含用户名、密钥或真实会话。
- 最终 Change Radar P1/54，无 blocking gaps；103 项全量测试、81.95% 核心覆盖率、20/20 Eval、静态检查、wheel 资源检查与真实 App 构建共同覆盖风险。

## 阶段 12：Codex / Claude Code / Cursor 能力矩阵（2026-08-27）
- Codex 官方能力的高价值部分是：按目录分层的 `AGENTS.md` 指令链、会话恢复、图片/网页上下文、专用子 Agent、代码审查、sandbox/approval 分层，以及本地与 worktree 隔离运行。YF-Harness 先吸收“可解释指令链、恢复、审查”，不默认复制无边界并行修改。
- Claude Code 官方将项目记忆、Plan 权限模式、PreToolUse 决策钩子、独立上下文子 Agent 与可恢复会话分开建模。值得吸收的是“研究与修改隔离、工具权限显式、项目记忆可见”；Hook 只在有确定 schema、超时和拒绝优先级后再开放。
- Cursor 官方的高价值交互是：Ask/Agent/Manual/Custom 模式、变更 Checkpoint、运行中 queued/follow-up 消息、项目 Rules、变更审查与安全 Run Modes。YF-Harness 已有四模式与审批基础，主要差距在队列、检查点/审查和规则可见性。
- 三者共同的优势不是“更多按钮”，而是把任务目标、项目上下文、执行边界、进行中状态、变更证据和恢复路径做成一条连续工作流。
- 三者共同需要规避的缺点：长会话上下文污染、自动执行的权限膨胀、并行修改冲突、规则注入、云端代码隐私、检查点与 Git 状态混淆、过度复杂的模式选择。
- 第一批产品取舍：统一发现 `AGENTS.md` / `CLAUDE.md` / `.cursor/rules` / `YFHARNESS.md` 并显示来源；提供 Plan→Execute；运行中支持排队但不隐式 steer 当前工具调用；用已有原子变更记录构建审查与冲突安全撤销。
- 实现后证据：规则链支持目录 scope 与 `AGENTS.override.md`；本地索引兼容 Git/非 Git；队列成功后串行、取消/失败暂停；会话分支生成新消息 ID；撤销拒绝 after_hash 不一致的后续编辑。
- 三个检查器标签在 2880×1658 原始 Qt 截图中分别检查；信息层级、窄栏截断、空白节奏和交互行密度符合“主工作区优先、检查器次级”的视觉命题。
