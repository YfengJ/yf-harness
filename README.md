# YF-Harness

YF-Harness 是一个本地优先、桌面优先、模型无关的个人 LLM Agent Harness。它提供可双击启动的
原生桌面工作区，同时保留 CLI/TUI 作为自动化和兼容入口。它统一 Provider 流式事件，运行有边界的
Agent 状态机，安全调用文件、搜索、Patch、Shell 和 Git 工具，并保存会话、Trace、Token、成本、
审批与评测记录。

项目名：YF-Harness · Python 包：`yfharness` · CLI：`yfh` · Python：3.12+ · License：MIT。

## Harness 是什么

模型只生成不可信建议；Harness 负责组装上下文、请求模型、解析事件、验证工具 Schema、执行策略、
请求审批、限制 workspace、持久化运行和恢复异常。核心实现不依赖高级框架或供应商 SDK；LangChain、
LlamaIndex 和 AutoGen 通过可选、惰性加载的适配层接入，既保留可学习的核心，也能直接运行生态框架。

## 功能

- MockProvider：无网络、无 API Key，支持流式文本、脚本化工具调用和故障模拟。
- OpenAICompatibleProvider：可配置 `base_url`、模型、超时、有限重试和 SSE/JSON 响应。
- Chat / Plan / Agent / Review 四模式共享同一状态机。
- Balanced / Plan / Guarded 版本化 Workflow，可组合模式、审批、工具可见性与声明式 Hook。
- 25 个真实工具；覆盖本地文件、Shell、Git 及受限 GitHub 工作区，并统一使用 Schema、审批和 Diff 预览。
- 路径穿越与符号链接逃逸防护；Shell 超时、进程组终止、输出限制和环境脱敏。
- SQLite 会话、运行、消息、模型事件、工具、审批、用量、上下文和文件变更记录。
- PySide6 + Qt Quick 原生桌面 App：安静的对话画布、轻量 Composer、设置抽屉与 `⌘K` 命令中心。
- Composer 的统一 `+` 支持图片和 UTF-8 文本/代码文件；普通文件进入本地上下文，图片只有显式授权后才进入远程模型请求。
- 运行中后续任务队列、Plan→Execute 显式确认、会话分支和可恢复的长期工作流。
- 会话级 `/goal` 支持设置、查看、完成和清除；活动目标持续注入后续运行但不扩大权限。
- 统一发现 `AGENTS.md`、`CLAUDE.md`、Cursor Rules 与 `.yfh` 指令，并显示实际上下文来源。
- Git 感知的本地项目索引，按路径、内容和工作区状态自动选择相关文件，全程不上传代码。
- 逐文件 Diff 审查与持久化检查点；撤销前校验修改后哈希，拒绝覆盖后续人工编辑。
- Codex / Claude Code / Cursor 项目技能统一发现；桌面输入 `$` 即可搜索和显式调用。
- 整次 Agent 运行可原子式回退；任一文件存在后续编辑时，整组撤销不会部分生效。
- Textual 三栏 TUI：流式 Markdown、会话、工具折叠、审批、设置、诊断和响应式布局。
- 项目指令、手动/自动文件上下文、Token 预算与八字段结构化压缩。
- 会话压缩摘要跨运行恢复；桌面或 `yfh sessions compact` 可显式更新，原始消息始终保留。
- 当前会话、今日、本月的本地 Token/成本账本与可选额度；估算值和未知成本明确标记。
- 轮转文本/JSONL 日志、Trace、只读 Replay 和 20 类离线 Eval。
- LangChain、LlamaIndex、AutoGen 真实 Agent API 集成；支持离线 Mock 和现有 OpenAI-compatible 配置。
- Brave Search 与自定义 MCP stdio 工具使用名称隔离、环境白名单和现有审批链；项目插件只静态发现。

## 截图

![YF-Harness 桌面应用](docs/images/desktop-app.png)

这是由打包后的真实 macOS App 渲染的界面。更新方法见
[`docs/images/README.md`](docs/images/README.md)。

## 架构概览

```text
Qt Quick Desktop / CLI / Textual TUI
        │
        ▼
AgentRunner ── ContextBuilder / ProjectIndex
   │   │
   │   ├── Provider → ModelEvent stream
   │   └── ToolExecutor → Policy → Approval → WorkspaceGuard → Tool
   ▼
Repositories → SQLite        Observability → JSONL / Trace / Eval / Replay
```

完整图和依赖方向见 [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)。
规则融合、自动上下文和恢复语义见 [`docs/PROJECT_INTELLIGENCE.md`](docs/PROJECT_INTELLIGENCE.md)。

## 安装

### uv

```bash
git clone https://github.com/YfengJ/yf-harness.git YF-Harness
cd YF-Harness
uv sync --extra dev
uv run yfh --help
```

启动桌面版：

```bash
uv sync --extra desktop
uv run yfh desktop
```

需要全部高级框架时：

```bash
uv sync --extra dev --extra frameworks
# 或 pip install -e '.[dev,frameworks]'
```

### 普通 pip 与 venv

```bash
python3.12 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
python -m pip install -U pip
python -m pip install -e '.[dev]'
yfh --help
```

## 无 API Key 快速体验

```bash
uv run yfh desktop
```

Mock 是默认 Provider；首次运行会在 platformdirs 对应的用户数据目录创建 SQLite，而不是把历史写入仓库。
使用 `--no-save` 可运行一次性任务。

## macOS App：双击即用

仓库已经提供一键构建脚本。它会生成自包含 App Bundle、创建图标、进行本机临时签名，并实际启动验证：

```bash
./scripts/build_macos_app.sh
open dist/YF-Harness.app
```

也可以在 Finder 中直接双击 `dist/YF-Harness.app`，或把它拖入“应用程序”。本地构建采用 ad-hoc
签名，适合本机使用；发给其他人之前仍需 Apple Developer ID 签名和 notarization。完整说明见
[`docs/DESKTOP_APP.md`](docs/DESKTOP_APP.md)。

如果本机已经有此仓库构建好的 App，最短启动方式就是在 Finder 打开项目的 `dist` 目录，双击
`YF-Harness.app`。不需要先启动终端，也不需要 API Key；默认 MockProvider 可以直接体验完整界面。
首次打开后点击左下角当前项目右侧的箭头切换工作区；App 会在本机配置目录记住这个选择，下次双击自动恢复。

Composer 保留统一附件 `+`、多行输入，并把高频模型、Agent/Plan 模式、Goal、上下文概览和发送
集中在输入框底栏。点击左下角“设置与用量”可管理 Provider、Workflow、权限和本地用量；上下文与变更各有独立标签。
输入框仍支持 `/goal <目标>`、`/goal done` 和 `/goal clear`。活动 Goal 会跟随会话保存并注入后续运行，
但不会自动执行任务、扩大工具权限或跳过审批。

按 `⌘K`（Windows/Linux 为 `Ctrl+K`）可打开命令中心，统一进入新任务、Plan、Goal、文件变更、
上下文、工具与连接、Skills、GitHub 和工作区切换。1040px 起的窗口会自动收缩长标题，检查器以覆盖式抽屉打开，
不会再挤压消息和输入区域。

“设置与用量”面板和命令中心“用量与额度”展示本机保存的会话、今日和本月 Token/成本统计；它不是
Provider 账户余额。上下文页可点击“立即压缩当前会话”，生成的结构化摘要会随会话保存并在后续运行复用。
CLI 可执行：

```bash
yfh usage --output json
yfh sessions compact <session-id>
```

## 项目技能与 `$` 命令面板

桌面输入框键入 `$` 会打开技能面板，支持键盘上下选择、Enter/Tab 插入，也可鼠标点击。“Skills 管理”
还能新建项目 Skill、导入本地文件夹，或复用 `gh` 登录从 GitHub（含有权访问的私密仓库）安装。当前兼容：

- `.yfh/skills/*/SKILL.md`
- `.agents/skills/*/SKILL.md`
- `.claude/skills/*/SKILL.md` 与 `.claude/commands/*.md`
- `.cursor/commands/*.md`

同名技能必须使用完整的 `source:name`。完整正文只在用户显式选择后进入当次上下文；脚本与资源不会
自动执行，`allowed-tools` 也不会授予权限。CLI 可用 `yfh skills list`、`yfh skills show <name>` 和
`yfh run --skill <name> "任务"`。详细边界见 [`docs/PROJECT_SKILLS.md`](docs/PROJECT_SKILLS.md)。

## 配置 DeepSeek 或其他兼容服务

复制 [`examples/config.example.toml`](examples/config.example.toml) 到 `yfh config path` 输出的位置，
并填写服务当前实际支持的模型名称：

```toml
default_provider = "deepseek"
default_model = "deepseek_v4_flash"

[providers.deepseek]
type = "openai_compatible"
base_url = "${DEEPSEEK_BASE_URL}"
api_key_env = "DEEPSEEK_API_KEY"
timeout_seconds = 120
include_reasoning = true

[models.deepseek_v4_flash]
id = "deepseek_v4_flash"
provider = "deepseek"
model = "deepseek-v4-flash"
supports_streaming = true
supports_native_tools = true
supports_reasoning = true
context_window = 1000000

[usage]
daily_token_budget = 100000
monthly_token_budget = 2000000
daily_cost_budget = 2.5
monthly_cost_budget = 50.0
```

```bash
export DEEPSEEK_BASE_URL='https://api.deepseek.com'
export DEEPSEEK_API_KEY='...'
yfh doctor
yfh run --provider deepseek --model deepseek_v4_flash "你好"
```

本地兼容服务可把 `base_url` 设置为如 `http://127.0.0.1:11434/v1` 并留空 `api_key_env`。
上下文长度、能力和价格只来自用户配置；YF-Harness 不把示例模型名或价格当作永久事实。

配置优先级：CLI > `YFH_*` 环境变量 > `.yfh/config.toml` > 用户配置 > 默认值。
API Key 只通过 `api_key_env` 指定的环境变量读取，不写入配置展开结果、数据库、日志或导出。

## 兼容 TUI

```bash
yfh tui
```

快捷键：`Ctrl+N` 新会话、`Ctrl+K` 命令提示、`Ctrl+C` 取消运行、`Ctrl+L` 输入、
`Ctrl+P` 模式、`Ctrl+O` 会话、`Ctrl+Enter` 发送、`Alt+↑/↓` 输入历史、`F1` 帮助。

常用 Slash Commands：`/new`、`/sessions`、`/mode`、`/permissions`、`/add`、`/context`、
`/compact`、`/undo`、`/doctor`、`/export`、`/stop`、`/quit`。命令由客户端解析，不发送给模型。

## 无界面 CLI

```bash
yfh chat
yfh run "任务内容"
yfh run --file task.md
yfh sessions list
yfh sessions export <session_id> --format json
yfh providers list
yfh models list
yfh tools list
yfh workflows list
yfh mcp list
yfh plugins list
yfh skills list
yfh run --skill codex:review-changes "检查当前改动"
yfh doctor --no-network
yfh eval
yfh replay <run_id>              # 默认只读，不执行工具
yfh config show
yfh config path
```

桌面端点击 Composer 左下角 `+` 可选择图片或普通文件。普通文件限制为项目内不超过 200 KB 的 UTF-8
文本/代码，并在发送任务前再次校验大小和 SHA-256；二进制、非 UTF-8、工作区外或被修改的文件会被拒绝。
图片在 CLI 中同样默认不上传：`yfh run --image screen.png "检查这张图"`。
只有加上 `--send-images` 才会把验证后的图片内容发送给声明
`supports_image_input = true` 的兼容模型。Workflow、MCP 和插件契约见
[`docs/WORKFLOWS_MCP.md`](docs/WORKFLOWS_MCP.md)。

## 联网搜索、Skills 与 GitHub

桌面端从 Composer 的 `+`、命令中心或左下角“工具与连接”进入集成管理：

- Brave Search 通过固定版本的官方 MCP server 接入；API Key 保存到系统钥匙串，也可使用 `BRAVE_API_KEY` 环境变量。点击“测试连接”先验证工具发现，真正联网时仍显示网络审批。
- 自定义 MCP 只保存 stdio 命令、参数和环境变量名，不保存密钥值；未知工具默认高风险并要求审批。
- Skills 安装到当前 workspace 的 `.agents/skills`，拒绝符号链接、超限目录和覆盖，附带脚本不会自动执行。
- GitHub 复用系统已有的 `gh auth`，只连接当前 workspace 的 `github.com` origin。可查看 PR、Issue、Actions 和私密性，也可执行普通 push、仅快进 pull、创建分支/PR/Issue、评论及重跑失败任务。

模型可以正常调用这些工具，但仍受当前 Mode、Workflow、权限策略、人工审批和 workspace 边界共同
限制。GitHub 写工具始终审批；系统不提供强推、删除分支、合并 PR 或修改仓库设置的工具。

## 高级 Agent 框架

框架是可选边界，不会替换 `AgentRunner`。安装后可发现、诊断并用相同 Provider/Model 配置运行：

```bash
yfh frameworks list
yfh frameworks doctor
yfh frameworks run langchain "总结这段需求"
yfh frameworks run llamaindex "分析这个问题" --output json
yfh frameworks run autogen "给出实施方案" --provider deepseek --model deepseek_v4_flash
```

也可只安装一个：`pip install 'yf-harness[langchain]'`、`[llamaindex]` 或 `[autogen]`。
MockProvider 会实例化每个框架自己的 Agent/模型接口，完全离线运行；远程 Provider 会实例化该框架的
官方 OpenAI-compatible 客户端。当前适配层故意传入空工具集，避免第三方执行循环绕过 YF-Harness 的
审批和 workspace 防线；需要文件、Shell、Git 等能力时继续使用 `yfh run`。完整契约与 Python API
示例见 [`docs/FRAMEWORK_INTEGRATIONS.md`](docs/FRAMEWORK_INTEGRATIONS.md)。

`yfh run` 支持 stdin、文本/JSON 输出、超时和非零错误码，适合 CI。Replay 只有在显式
`--execute` 并确认后才重新执行。

## 安全说明

- 模型、用户输入和工具参数均不可信；工具名和参数必须通过注册表与 Schema。
- 所有文件路径经真实路径解析，限制在 workspace；搜索不跟随符号链接。
- Plan、Review、Chat 不允许写入。`full_auto` 默认禁用；删除与 Shell 始终审批。
- Shell 默认参数数组、有限环境、超时与输出上限；Shell 字符串必须显式 `shell=true`。
- 网络命令提升为 critical 风险并审批。当前不是 OS/容器级网络沙箱，见已知限制。
- 日志和导出递归脱敏；不要把密钥写进任务文本或文件。

完整威胁模型见 [`docs/SECURITY_MODEL.md`](docs/SECURITY_MODEL.md)。

## 配置与数据位置

```bash
yfh config path
yfh doctor --no-network
```

跨平台路径由 platformdirs 决定。测试或便携环境可设置 `YFH_CONFIG_DIR`、`YFH_DATA_DIR`、
`YFH_LOG_DIR`。数据库文件是数据目录中的 `yfharness.sqlite3`；日志目录包含 `yfharness.log`
和 `debug.jsonl`。

## 质量与测试

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest
uv run pytest -m desktop
uv run pytest -m frameworks
uv run pytest --cov=yfharness --cov-report=term-missing
uv run yfh eval
uv build
```

普通测试和 Eval 不依赖真实 API。真实 Provider 测试应只在显式环境变量存在时单独运行，并不得录制密钥。

## 学习路线

从 [`docs/LEARNING_PATH.md`](docs/LEARNING_PATH.md) 开始，推荐顺序：领域模型与事件 → Provider →
Agent Loop → Tool/Security → Storage → Context → TUI → Observability/Eval。每份核心文档结尾都有理解目标、
可改实验、常见 Bug、面试问题和动手练习。

## 已知限制

- 第一版是单进程本地应用；多个实例同时运行时，崩溃恢复可能把遗留 running 记录标为 interrupted。
- Shell 网络控制是风险识别与审批，不是操作系统级网络隔离；高对抗场景应放入容器/沙箱。
- Windows 子进程树终止是尽力而为；CI 会验证基础行为，复杂进程树仍需平台专项测试。
- 无专用 tokenizer 时使用明确标记的近似估算；兼容服务的非标准 SSE 可能需要适配。
- 自包含 macOS App 会携带 Qt 运行时，因此体积明显大于 Python wheel；公开分发还需要正式签名与公证。
- TUI 是兼容入口，在很小终端会隐藏侧栏并显示警告；完整交互建议宽度 95 列以上。
- 当前不提供训练、云端账户、浏览器自动化、向量数据库或分布式多 Agent；框架适配器目前也不注入本地工具。

## Roadmap 与贡献

见 [`docs/ROADMAP.md`](docs/ROADMAP.md) 和 [`CONTRIBUTING.md`](CONTRIBUTING.md)。新增 Provider 必须输出统一
`ModelEvent`；新增工具必须声明 Schema、风险和只读属性，并补充拒绝、越界与错误路径测试。

## License

[MIT](LICENSE)
