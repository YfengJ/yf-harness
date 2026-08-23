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
