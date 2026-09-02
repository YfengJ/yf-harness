# 发现与决策

## 阶段 21：Composer 控制、工具连接、Skills 与 GitHub（2026-09-02）

- 用户要求模型与模式继续位于输入框内，因此 Composer 底栏作为“本次运行控制面”，而 Provider、Workflow 和权限仍留在高级设置，避免重复配置源。
- 联网搜索选择 MCP 而非在核心中硬编码搜索 API：Brave 预设限制可见工具，自定义 stdio 保留扩展性；两者都复用 ToolExecutor 的 Schema、模式、Workflow 与审批边界。
- Brave API Key 不应进入 TOML、托管 JSON、数据库或仓库。桌面写入系统钥匙串，运行时环境变量优先，托管 JSON 只保存非密钥命令和环境变量名。
- MCP 服务端 annotation 属于不可信输入，默认不能降权；逐工具只允许由本地配置覆盖风险。Brave 预设的搜索工具标为只读网络工具，首次或策略要求时仍审批。
- Skills 安装不是插件执行：只复制并校验目录，禁止符号链接、超限和覆盖，scripts/assets 不自动运行；成功后必须经同一个 SkillCatalog 发现和显式 `$source:name` 调用。
- GitHub 以当前 workspace 的 origin 作为能力边界，拒绝非 `github.com` 远端；读操作与写操作分层，写工具 always-approval，且刻意不实现 force push、删除、merge 或 settings。
- 真实验证已经覆盖 Brave MCP initialize/tools-list、私密 GitHub Skill 安装和当前私密仓库状态读取；没有真实 Brave Key 时不能声称已经完成在线搜索查询。
- 安全审查定位到两个边界问题：导入 Skill 根目录符号链接在 resolve 后无法识别；GitHub CLI 环境缺少 HOME 会把状态写到 workspace。两者均已修复并有负向测试。

## 阶段 20：桌面对话减法与统一附件入口（2026-09-01）

- 真实截图中的首屏说明区由一个大标题、长副标题和三条编号行组成，信息重复且纵向占用过高；用户希望改为一句话，因此不应通过缩字号保留原结构，而应直接删除三条行。
- Composer 周围同时暴露模式、Goal、模型、上下文和额度，会把“输入任务”与“观察/配置运行”混在同一区域；更合理的层级是高频输入留在 Composer，低频设置与统计进入左下角入口后的独立面板。
- 图片与普通文件应共享单一 `+` 入口，但安全语义不同：图片可按模型能力与显式上传配置进入多模态请求；普通文本文件应通过受 workspace、大小和编码限制的上下文附件链路进入模型，其他二进制文件只允许选择后给出明确不支持提示，不能静默上传。
- 当前仓库无未提交变更；实现前需要确认既有图片附件 API、上下文文件附加 API、QML 弹层状态和桌面测试对象名，优先复用而不是新增平行状态。
- `ContentPartType.FILE` 已在领域模型中存在，但 `OpenAICompatibleProvider._message_payload()` 只序列化 TEXT 与显式远程 IMAGE；如果把 FILE 直接附到用户消息，文件会被静默丢弃。实现因此在 `_run_once` 中将 FILE 与 IMAGE 分流，FILE 经哈希复核后加入 `ContextBuilder`，IMAGE 保持 Provider 多模态路径。
- 右侧检查器本来已经同时承载用量、Provider、模型、工作流、模式与权限，因此无需新增设置数据层；只需把左下角作为统一入口，并将第一标签从“运行”明确改名为“设置”。
- Composer 原本高度 166/196px 且有两行元信息；移除常驻运行状态和五个控制项后可降到 124/154px，附件存在时仍保留横向可移除清单。
- 1280×800 空状态截图中主画布获得足够留白，唯一引导句与底部输入形成清晰的“提示—行动”关系；不存在旧三条任务说明或额度/上下文标签。
- 设置面板截图确认左下角入口与右侧面板形成直接映射；面板在 800px 高度内通过 ScrollView 承载较长设置，不发生水平溢出，主画布仍保留足够宽度。
- review-changes 发现普通文件原方案存在“哈希校验后由 ContextBuilder 再读文件”的微小 TOCTOU；最终改为 `file_context()` 返回已验证的确切文本，`add_verified_file()` 不再重新打开文件，并用文件校验后被改写的回归测试证明实际上下文仍是已验证内容。
- 最终请求逐项证据：一句空状态由 Bundle 截图与 QML 负向字符串断言证明；设置/额度迁移由左下角入口和设置抽屉截图证明；简化 Composer 由布局报告证明；图片/文件 `+` 菜单由 QML 契约 smoke 证明；普通文件真实上下文由 DesktopController 集成测试证明。
- 0.11.0 发布准备仅在本地完成；App、wheel 与 sdist 可用，但未收到本轮 GitHub 推送授权，因此没有把本轮改动上传远端。

## 阶段 19：DeepSeek 真实 API 纵向验收与凭据安全（2026-09-01）
- 起点 `main` 干净且与私密远端同为 `bb8af96`；Change Radar 在无 diff 时为 P3/0，但真实凭据、外部计费和 Agent 工具链人工按 P1 管理。
- README 与 `examples/config.example.toml` 已提供 DeepSeek 配置：`type = "openai_compatible"`、`api_key_env = "DEEPSEEK_API_KEY"`；源码的 Provider/框架运行时均只按环境变量名取值，密钥不属于持久化配置模型。
- 凭据测试方案：不在仓库创建 `.env` 或含密钥 TOML，不把密钥拼入命令行；使用无回显交互把它注入单个临时 shell 环境，所有配置、数据库和日志放在仓库外临时目录，进程退出即销毁环境。
- 验收顺序采用低成本递进：鉴权/模型与流式 usage → CLI 持久化 → Agent 原生工具调用 → 同会话恢复与摘要 → 本地额度聚合 → 桌面 Controller 后端；只有直接证据显示项目行为错误才修改源码。
- DeepSeek 当前官方 OpenAI-format base URL 仍为 `https://api.deepseek.com`，当前模型是 `deepseek-v4-flash`、`deepseek-v4-pro`（另有实验视觉模型），均支持 Chat Completions 与工具调用；项目通用 HTTP 路径与此兼容。[DeepSeek 首次调用](https://api-docs.deepseek.com/) [模型与价格](https://api-docs.deepseek.com/quick_start/pricing/)
- 项目示例仍配置 `deepseek-chat`，但 DeepSeek 官方已声明该旧名称在 2026-07-24 停用；当前日期已超过停用日，因此 README/example 的默认首次运行路径已失效，必须改为 `deepseek-v4-flash` 或 `deepseek-v4-pro` 并补回归。
- 新模型的 thinking + tools 多轮契约要求把上一轮 `reasoning_content` 连同 assistant tool call 回传；当前领域 `Message` 没有 reasoning 字段，Provider 只可选择把 reasoning 流作为观察事件，Agent 后续消息无法保留它。需用真实 API 判断默认请求是否触发该限制，再决定加入 provider 请求模式控制还是扩展持久化消息契约。[DeepSeek Thinking Mode](https://api-docs.deepseek.com/guides/thinking_mode/)
- 真实鉴权与 `/models` 已通过；单轮 `deepseek-v4-flash` 返回真实 usage 2,103 Token，说明 base URL、Bearer 认证、JSON 响应与 usage 归一化均兼容，且密钥未出现在 stdout。
- 15 个工具的 Plan 请求在完成前超过 12k 累计 Token。可能原因包括 V4 默认 thinking 消耗、重复工具调用或第二轮缺失 reasoning；需要最小化为单工具协议探针后再判断，不能直接归咎上游或简单抬高预算。
- 最小工具协议首轮含 reasoning 仍能在不回传 reasoning 字段的现有 Message 下完成第二轮，因此当前 DeepSeek V4 API 对该非严格路径保持兼容；12k 超限的实际原因是自动选择 5 份文件后每轮输入约 7k、两轮累计 15,704，预算门行为正确。
- CLI `workflow.visible_tools` 原先直接枚举 `ToolExecutor.definitions()`，而 Agent 在 Plan/Review/Chat 内部还会过滤非只读工具；实机 JSON 因此把 15 个工具错报为可见，实际请求只有 8 个。修复改为复用 Agent 的确切暴露集合并增加显式 `--mode plan` 回归。
- 流式非 2xx 使用 `client.send(..., stream=True)`，旧 `_raise_for_status` 立即访问 `response.json()`，导致 `httpx.ResponseNotRead` 逃逸并打印内部 traceback。修复对错误流最多读取 64 KiB、关闭响应并构造统一 `ProviderError`；真实 401 已验证无 traceback。
- DeepSeek V4 默认 thinking 在较小 `max_output_tokens=256` 下可能耗尽输出预算而不产生正文；Provider 正确发出 `FinishEvent(reason="length")`，但 Agent 只收集 text/tool/usage、忽略 finish reason，导致空白成功。应在保留真实 usage 后把 length 作为明确失败，不得把截断结果记为完成。
- 完整实机矩阵已覆盖核心 CLI（流式/JSON/鉴权错误）、只读原生工具两轮、会话恢复、手动摘要复用、usage 聚合、LangChain/LlamaIndex/AutoGen、桌面 Controller 和 Textual TUI；除已修四项外未发现新的真实 Provider 兼容失败。
- 0.10.1 最终离线门为 174 passed、83.49% 覆盖率、Ruff/format、核心/桌面 mypy、20/20 Eval、构建与隔离 wheel smoke。App 初次构建为 236 MiB、Plist 0.10.1、codesign 有效；MCP 版本来源随后改为 `__version__`，因此最终发布前需重建以保证 Bundle 对应最终源码。
- 密钥审计不使用密钥字面量查询，而以完整 `sk-` 长模式检查：工作树、Git 历史、临时配置/日志/脚本、临时 SQLite、解包 wheel/sdist 和 App Bundle 全部无匹配；远端仓库确认 `PRIVATE`。
- 最终 review 无可操作缺陷；Change Radar 的 P1/30 由补丁版本元数据和 `uv.lock` 触发，而非新依赖，隔离 wheel、完整测试和最终 App 覆盖该风险。MCP clientInfo 已改为读取 `__version__`，以后无需手工同步。
- 私密发布完成：提交 `59e0da8` 对应 GitHub Actions run `33500549560`，minimal-install、desktop-smoke 与 Ubuntu/macOS/Windows × Python 3.12/3.13 共 8/8 Job 全绿；缓存 annotation 不影响任何 Job conclusion。

## 阶段 18：0.10 性能、上下文与额度纵深（2026-09-01）
- 起点仓库干净，`main` 与私密远端均在 `7618270`；无差异时 Change Radar 为 P3/0，但上下文/存储/配置/桌面联动按 P1 管理。
- `usage_records` 已保存 provider/model/input/output/total/estimated/cost/duration/created_at，且 runs 关联 session；缺口不是采集，而是 Repository 没有聚合查询，桌面和 CLI 都无法展示会话、今日、本月累计或估算占比。
- “额度统计”应定义为本地账本：精确/估算 Token、已知成本、运行次数、耗时和可选本地预算；除非 Provider 提供专门余额 API，否则不得把本地预算剩余称为供应商账户余额。
- `ContextBuilder.previous_summary` 当前只在 Python 对象内存中；自动与手动压缩虽然能减少下一次请求消息，但跨进程/重建 Builder 是否丢失尚需沿桌面与 CLI 创建路径验证。
- `ContextBuilder._estimate()` 每次都重新把全部工具定义 `model_dump + json.dumps`；自动压缩超预算时的 recent-message 裁剪循环会反复支付同一工具 schema 成本，可把工具估算缓存为当前 build/fit 的局部值并用消息增量估算验证收益。
- 真实缺陷已确认：CLI/桌面每次 `_run_once()` 都新建 `ContextBuilder`，而 `previous_summary` 只存在对象内；同一会话下一次运行不会复用摘要，会对完整历史重复压缩。0.10 将摘要 JSON 前向迁移到 session，保留原始消息，分支复制摘要，运行后只在摘要变化时更新。
- 热路径基线（16 个中等工具 schema、49 条长消息、22k 请求预算）：单次 `fit_messages` 10.06 ms、39 次 estimator 调用，100 次 974.32 ms（平均 9.74 ms），最终从 49 条裁到 21 条。0.10 的最低验收是 estimator 调用不随逐条裁剪线性增加，并以同参数前后复测给出证据。
- 上下文状态契约采用 `none/reused/created/manual`：`compacted` 继续兼容旧 UI，另行暴露摘要是本次创建还是跨运行复用；重复摘要必须把上一版结构化字段当一等输入，不能因旧摘要以 system role 注入而丢失约束。
- 额度统计契约采用本地账本而非供应商账户余额：会话累计、工作区今日、本月各展示运行数、总 Token、其中估算 Token、已知成本、未知成本运行数和耗时；可选本地日/月 Token 与成本预算仅用于进度显示，不改变现有每次运行硬限制。
- 第一轮 review 发现旧 `_add_usage` 在模型未配置价格时把成本归零，额度 UI 会把“未知”误报为“免费”；已改为聚合成本保持 `None`，配置成本硬限制但缺少价格时明确失败，CLI/TUI/桌面分别显示未知成本。
- 第一轮 review 还发现 `_run_once` 会把带自动文件上下文的扩展 user message 写回原始历史，导致会话和后续摘要持续膨胀；现改为只持久化原始 prompt 与显式图片 part，模型扩展上下文不进入 `messages`。真实 smoke 的单轮手动摘要由 10,858 字符降至 131 字符。
- 示例配置原先在 TOML table 之后声明根级 `default_workflow`，实际会落入错误 table；0.10 将根键移到文档顶部并加入 `tomllib` 结构回归。
- 第二轮 review 修复多步 Agent 在工具后重建上下文时把已有摘要状态重置为 `none`，并在最近窗口没有 user 消息时保留上一摘要的真实 goal/next step。
- 发布门最终证据：170 passed、83.21% 覆盖率、Ruff/format、核心 68 文件和桌面 3 文件 mypy、20/20 Eval、0.10.0 sdist/wheel、隔离 wheel 版本/Mock/usage、236 MiB App、Plist 0.10.0、深度 codesign 和真实 Bundle 截图全部通过。
- 最终 Change Radar 为 P1/50、无 blocking gaps；P1 来源是版本/lockfile、配置 schema 和可执行链路的预期变化，相关风险均有直接验证。目标 GitHub 仓库复核为 `PRIVATE`。
- 功能提交 `0a46291` 的 GitHub Actions CI 运行 `33479652726` 已完成：8/8 Job 全绿，覆盖 Ubuntu/macOS/Windows、Python 3.12/3.13、minimal-install 与 desktop-smoke；唯一 cache reserve annotation 属于并发缓存竞争，不影响构建或测试结果。
- 现有结构化摘要由确定性规则提取目标、约束、决定、文件、测试与未解决项，优点是离线和可审计；风险是重复压缩时系统角色的旧摘要可能被首个 system message 过滤，需要增加多轮压缩与关键约束保留测试。

## 阶段 17：0.9 蓝图工作室桌面重构（2026-08-31）
- 当前 2960×1648 Bundle 截图证实 Composer 把图片、原图开关、模式、长 Goal、模型、上下文、技能快捷键和发送压在同一固定行；长目标虽省略，但各控件仍争抢剩余宽度，快捷键文案与发送区已经失去稳定间距。
- 输入框本体占据约 140px 高度，但只有一行低对比占位符；动作区比输入内容更抢眼，形成“空文本框 + 拥挤底栏”的反向层级。
- 主画布采用近黑背景和大量低对比灰字，消息少时中段出现大面积无意义空白；工具结果像日志条，产品更接近调试器而不是任务工作区。
- 左侧 344px 视觉宽度在截图中占比偏高，底部项目块与切换按钮重复表达当前项目；导航、项目和新建任务没有形成清晰的单一动作主线。
- 最新界面审查规则要求长内容明确 truncate/wrap、flex 子项允许收缩、空状态完整、可见焦点、具体按钮文案、错误提供下一步、覆盖层不能遮住焦点元素；这些原则将映射到 QML 的 `elide`、`wrapMode`、`activeFocus` 边框、显式宽度上限与 Popup/Drawer 焦点恢复。[Web Interface Guidelines](https://github.com/vercel-labs/web-interface-guidelines)
- 新视觉方向确定为“蓝图工作室”：暖白主画布、深海军蓝任务轨道、钴蓝行动色和薄荷绿安全状态，完全脱离 0.7/0.8 的石墨黑/铜金方案。
- 新功能重点不是继续增加底栏按钮，而是加入 `⌘K` 命令中心与任务状态带，让高频动作可发现、低频配置进入覆盖式检查器，并保持主画布宽度不随检查器开关变化。
- 视觉验收必须至少覆盖 1040×720、1280×800、1480×824 三种窗口尺寸和超长 Goal/会话名/模型名；只看默认 1480px 截图不能证明“不跑出去”。
- 第一张 1040×720 压力截图显示 Composer 的状态带和动作区已完整留在边界内，长 Goal 正确省略，模型与发送仍可用；但超长会话标题没有获得父列宽度，实际覆盖到右侧状态/命令区，证明仅给 `elide` 而没有确定宽度无效。
- 新暖白/海军蓝/钴蓝视觉在最窄尺寸下已经形成明显不同的产品语言：会话轨道、消息卡片、工具完成条和 Composer 层级清晰，旧版“全黑日志器”观感消失；后续细化重点转为标题边界、命令中心与检查器截图。
- 1480×824 压力截图确认长标题可以完整展示且主消息宽度稳定；1040×720 截图确认同一标题正确省略，Composer 状态带与动作区均未越界。两份几何报告的 sidebar/workspace/composer/input/status/actions 全部 `within_window=true`。
- 1280×800 命令中心截图显示新建、Plan、Goal、变更、上下文、技能入口具备一致图标/说明/快捷键层级；检查器截图确认抽屉覆盖主画布而不触发重排，但标题栏原检查器按钮仍显示为抽屉外的孤立 X，需在抽屉打开时隐藏。
- 命令搜索的初始实现只隐藏不匹配行，`currentIndex` 可能停在不可见项；键盘回车会执行错误动作。修正方案是查询变化时选择首个匹配项，上下移动显式跳过过滤项。
- 命令中心加高后 7 个动作在 1280×800 全部可见，底部仍保留键盘与权限提示；抽屉标题栏重复 X 已消失，但 16px 右边距让底层“命令”按钮末端从缝隙露出，最终改为基于 Overlay 宽度贴右并覆盖整高。
- 发布前 Change Radar 为 P1/40 且无 blocking gaps；风险由 0.9 版本/锁文件、桌面运行路径和 669 行 QML 差异触发，验证必须覆盖静态、专项、全量、Eval、包构建与最终 Bundle，不以单张截图代替。
- 发布审查将几何报告从 6 个容器扩到 13 个关键对象：会话标题、Composer、输入、状态/动作行、Agent/Goal/模型/上下文/命令/发送；三种尺寸必须逐项位于窗口内。
- 最终 1280×800 检查器截图确认抽屉已经与窗口右边界、上下边界贴合，底层“命令”按钮不再从边距露出；抽屉作为覆盖层保留主画布宽度，关闭入口和刷新动作均完整可见。
- 0.9.0 全量门禁结果为 162 passed、82.87% 覆盖率、20/20 离线 Eval；Ruff、格式、核心/桌面 mypy、锁文件检查及 0.9.0 sdist/wheel 同时通过，说明视觉重构没有破坏核心 Agent、存储、安全与 CLI/TUI 契约。
- 0.9.0 最终 App 为 235 MiB，`CFBundleShortVersionString` 与 `CFBundleVersion` 均为 0.9.0，深度 codesign 通过；Bundle 本体的 1480/1040、命令中心和上下文抽屉截图与源码预览一致，最窄压力报告的 13 个对象全部 `within_window=true`。
- 功能提交 `6cc2cbc` 已进入私密 `YfengJ/yf-harness` 的 `main`；GitHub Actions run `33335645069` 最终八个 Job 全绿，包括 minimal-install、Linux desktop-smoke 和 Ubuntu/macOS/Windows 的 Python 3.12/3.13 矩阵。

## 阶段 16：Composer 工作流控制与持久目标（2026-08-30）
- OpenAI 官方将模型选择与 `reasoning.effort` 分开建模；GPT-5.6 当前提供 Sol/Terra/Luna 三个定位和独立推理强度，因此 UI 不应把“模型”与“运行模式/推理深度”混成同一个选择器。[官方模型目录](https://developers.openai.com/api/docs/models)
- OpenAI Responses 官方接口返回 `usage`，并将 `model`、`reasoning`、`previous_response_id` 和 context management 分开；上下文概览应来自真实快照/使用量，不能用固定百分比模拟。[Responses API](https://developers.openai.com/api/reference/cli/resources/responses/methods/create)
- OpenAI 官方用例把 Follow a goal 描述为给 Codex 一个适合长期工作的 durable objective；YF-Harness 的 `/goal` 应是可恢复的会话状态，而不是一次性把字符串塞进 Prompt。[Codex/ChatGPT 用例目录](https://learn.chatgpt.com/use-cases)
- 现有核心已经有 `AgentMode.PLAN`、Plan 工作流、只读工具安全测试、计划保存与“执行此计划”；本次只需把入口移到 Composer 并保持原安全契约。
- 现有桌面控制台已经持有 Provider、Model、Workflow、Mode、Permissions 五个选择器；Composer 发送函数直接读取这些 QML 控件，因此可以通过单一状态源复用，避免两套选择不同步。
- `DesktopController.contextSummary` 当前只保存字符串，ContextSnapshot 完成后可取得 estimated/budget/compacted 和来源列表；要支持输入框概览，需要暴露结构化 token、budget、ratio、sourceCount 属性。
- SQLite 当前 schema v3 的 sessions 只有 provider/model/mode/workspace 等字段，没有 Goal；应用设置是全局键值，不适合会话隔离，正确方向是 schema v4 给 sessions 增加可空 goal、goal_status、goal_updated_at。
- 初始仓库 `main` 工作树干净；自动 Change Radar P3/0 只是无差异基线，实施会跨 migration/repository/controller/QML，人工风险按 P1。
- 阶段 16 第一张 2960×1648 开发截图确认 Composer 在 1480px 窗口中可以同时容纳图片、Agent/Plan、活动 Goal、模型、上下文百分比和发送；铜金只用于活动 Goal/Plan，不破坏 0.7 的精密编辑台层级。
- Goal 文本采用最大宽度与省略号，长目标不会挤走模型或发送；上下文入口显示真实 `ContextSnapshot.usage_ratio`，截图预览为 5%，不是硬编码的装饰进度。
- QML lint 发现 Goal/Context 两个 Popup 作为 `ColumnLayout` 词法子项时设置 x/y/width；运行 smoke 正常，但该结构存在未定义布局行为，需通过显式 Overlay parent 或移到根级消除。
- 运行完成会异步刷新会话列表；旧处理把 `_load_sessions` 中缺失的 `instructions` 当成空列表，覆盖刚写入 UI 的真实 ContextSnapshot 来源。修正后只有 bootstrap/workspace 的显式 instructions 才更新基础来源。
- 发布复查发现现有桌面模型选择器虽然可选择，但旧会话会被 `_run_once` 的 provider/model 一致性检查拒绝；现在只有桌面显式允许会话运行时切换，CLI 保留原严格契约，并同时持久化 provider、model 与 mode。
- schema v4 的旧库升级、Goal 创建/完成/清除/分支恢复、Plan 上下文注入、模型切换和结构化上下文概览已有直接测试；活动 Goal 只进入 system context，不改写用户消息，也不扩大工具或审批权限。
- 0.8.0 本地最终证据为 158 项测试、82.87% 覆盖率、20/20 Eval、sdist/wheel 与 235 MiB macOS App；真实 Bundle 生成的 2960×1648 截图确认 Composer 控件完整且未造成布局回退。
- 最终 Change Radar 为 P1/30 且无 blocking gaps；P1 来自预期的依赖元数据和运行路径变化，不代表发现新的未解决安全缺陷。
- 发布元数据复核发现部署器只生成 `CFBundleShortVersionString`；构建脚本现在从包版本同时写入并验证 `CFBundleVersion`，避免 App 更新/签名工具看到不完整版本元数据。
- GitHub Actions run `33332257769` 最终确认 minimal-install、desktop-smoke 及 Ubuntu/macOS/Windows × Python 3.12/3.13 八个 Job 全绿；目标仓库再次确认为 `PRIVATE`。

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

## 阶段 13：工作流、Hook、插件与性能基线（2026-08-28）
- 当前 `main` 干净，0.4.0 最终 CI `33076762077` 八个 Job 全绿；Change Radar 无未提交差异时为 P3/0，但 0.5 预计触及配置、工具执行、上传边界和部署，人工风险继续按 P1。
- Claude Code 官方 Hook 将 `PreToolUse` 放在工具参数生成后、权限处理前；决策支持 allow/deny/ask/defer，多 Hook 合并时最严格结果优先，且 Hook 的 allow 不能覆盖 deny/ask 权限规则。YF-Harness 应吸收“拒绝优先、来源可见、超时明确”，不直接开放任意 shell Hook。
- Claude Code 官方还区分 PreToolUse、PermissionRequest 与 PostToolUse；Post 事件发生在副作用之后，不能伪装成阻止机制。YF-Harness 的 Hook 事件和结果必须保留这个时间语义。
- Cursor 当前官方文档把 Run Modes、Rules、插件、MCP、skills、subagents、commands、hooks 作为分 scope 激活的能力；值得吸收的是 Profile 选择与能力可见性，不吸收隐藏的默认权限扩张或模式堆叠。
- 0.5 第一实现顺序：版本化 Profile → 声明式 Hook → AgentRunner/Trace/桌面可见性 → 多模态/MCP。外部进程、HTTP 或 MCP Hook 必须等到最小本地决策引擎和审批优先级有直接测试后再开放。
- macOS Bundle 当前约 491 MB；spec 已声明排除多个 QML 模块，但实际产物仍包含 WebEngine/Quick3D 等框架，说明需先测量部署器真实 module discovery/CLI 参数，而不能只继续增加排除字符串。
- OpenAI 官方 Codex MCP 配置提供 server 级 `enabled_tools` / `disabled_tools`、逐工具 approval mode、启动/调用超时和 OAuth；deny list 在 allowlist 之后生效。YF-Harness 的 Profile 也应采用“先允许、再拒绝”的保守交集，而不是后层 allow 覆盖前层 deny。
- OpenAI 官方 Codex 配置把 approval policy 与 sandbox/permission profile 分开，并允许对 MCP elicitation、规则、sandbox escalation 等提示类别做细粒度控制；这支持 YF-Harness 把“工具是否暴露”“工具能否执行”“是否需询问”建模为三个不同阶段。
- OpenAI 官方 Responses API 的用户消息可混合 `input_text`、`input_image` 与 `input_file`；YF-Harness 多模态领域模型必须保留内容部分类型，不能把图片路径塞进纯文本后假装模型看到了图片。
- MCP 当前官方工具规范要求工具列表确定性、名称冲突消歧、annotations 视为不可信，并建议 UI 明示暴露给模型的工具、调用状态和人工确认。远程 HTTP 授权还要求资源绑定，明确禁止 token passthrough；首版适配应优先 stdio、本地环境变量白名单和每工具审批。
- Cursor 官方插件体系把规则、skills、agents、commands、MCP 与 hooks 组合成可分发清单；YF-Harness 可以兼容开放的 `plugin.json` 发现思路，但不能直接信任插件声明的风险级别或默认启用其 Hook/工具。
- 当前工具暴露路径是 `AgentRunner._available_tools → ToolRegistry.definitions`，执行路径是 `ToolExecutor.execute → 参数校验 → Policy → Preview → Approval → Tool`。Profile allow/deny 必须同时作用于“暴露给模型”和“执行时再校验”，防止模型手写未暴露工具名绕过。
- 当前 Policy 已在 mode、approval policy、风险、只读、always-approval 与 session allow 之间做决策。Hook 不能替换这层；正确组合是：任一 deny 即拒绝，任一 ask 即审批，只有基础 Policy 和 Hook 都允许时才自动执行。
- 当前 Agent 事件已覆盖状态、模型、工具开始/结束与预算；增加 `HookEvaluated` 可让 CLI/桌面/Trace 观察决策来源。Post Hook 只能记录/提示成功或失败，不能声称撤销已发生的副作用。
- AppConfig 使用 defaults < user < project < env < CLI 的深合并，适合新增 `workflows` 与 `default_workflow`。Profile schema 必须带 `version = 1` 且拒绝未知字段，避免未来配置被静默误读。
- 0.5 已实现图片内容部分：默认 `local_only`，显式开启后才以 data URL 发送；扩展名、魔数、10 MiB、workspace 和发送前 SHA 复核共同约束上传边界。
- MCP stdio 仅在配置 `enabled = true` 时启动，环境变量需显式白名单；远端工具统一进入高风险审批，服务端 annotation 不参与本地降权。插件首版只做静态 manifest 发现，始终标为 `review_required`。
- 项目索引加入 mtime/size 样本缓存与 TTL 刷新；140 文件基准中 100 次选择由 662.51 ms 降到 513.28 ms，冷索引 9.26 ms。
- Qt 顶层模块排除实际生效后，0.5 macOS App 从约 491 MB 降到 235 MB；320 MiB 门禁、真实 Bundle smoke、ad-hoc 签名与截图均通过。QML 数据目录名称不能等同于顶层动态库，部署审计必须区分二者。
- 可选并行研究只接受只读上下文快照、独立会话和独立 worktree；任何写入结果仍需哈希基线检查、Diff、人工审批与测试后才能合并，不能共享隐式审批或密钥状态。

## 阶段 14：项目技能与命令工作流调研（2026-08-28）
- OpenAI 官方 Skills 采用渐进披露：启动时只提供名称/说明等元数据，用户显式调用或匹配后才加载完整 `SKILL.md`；仓库级技能从当前目录向仓库根的 `.agents/skills` 发现。YF-Harness 首版只做显式调用，避免隐式匹配误触发高影响指令。
- OpenAI 官方允许 Skill 带 scripts、references、assets，但这些属于能力包而非自动授权。YF-Harness 首版只读取 Markdown 指令；存在脚本时只展示警告，绝不自动执行。
- Claude Code 当前将项目技能放在 `.claude/skills/<name>/SKILL.md`，旧式命令放在 `.claude/commands/*.md`；支持 `$ARGUMENTS` 和位置参数。YF-Harness 可兼容纯文本替换，但所有结果仍受自身工具暴露、Policy、审批和 WorkspaceGuard 约束。
- Claude Code 的会话恢复、分支、回退、后台任务、Diff/Review 和上下文检查彼此分离。YF-Harness 已有会话分支、变更审查、队列和上下文检查器，本阶段优先补齐日常复用入口，而不是继续增加模式。
- Codex 的 `AGENTS.md` 是分层常驻规则，Skill 是按需任务流程，两者不能混成同一个优先级：项目规则继续常驻；完整技能正文只在本次明确调用中加入系统上下文并标注来源。
- 同名技能若靠静默优先级覆盖会造成供应链和误调用风险；公开身份采用 `source:name`，裸名称只在全目录唯一时可用，冲突时要求显式命名空间。
- 工作区内容视为不可信输入。Skill frontmatter 中的 `allowed-tools`、`disable-model-invocation` 等只能作为元数据和兼容提示，不能授权工具、跳过审批或覆盖工作流 Profile。
- 当前无差异 Change Radar 为 P3/0；预计修改上下文、CLI/TUI、桌面与打包版本，人工风险按 P1，验证重点为负向安全测试、正文不持久化、三入口一致性和真实 App 启动。
- 0.6.0 发布审查确认桌面选择的工作区必须作为运行时配置传给 `_run_once`，否则界面显示路径与工具/技能实际路径会分离；现已通过 `config_override` 和直接集成测试锁定这一契约。
- 同一来源的重复技能和 `user-invocable: false` 不能只在列表层提示，调用层也必须拒绝；现在裸名与完整 ID 都经过统一解析和权限检查。
- 整次运行恢复采用反序预检、写入前即时哈希复核与安全回滚；若恢复期间发生外部并发编辑，回滚不会覆盖外部内容。
- SQLite schema v3 将会话绑定到工作区；桌面和 TUI 仅显示当前项目会话，CLI 全局列表仍保留旧会话可访问性。
- Trace 只保存技能名称、来源和路径等元数据，不保存消息、附件或完整技能正文；无效技能在创建持久化运行之前被拒绝。
- 本地最终证据为 154 项测试、82.83% 覆盖率、20/20 Eval、0.6.0 sdist/wheel 隔离安装和 235 MiB macOS App；真实 Bundle 截图通过视觉检查。
- 最终 Change Radar 为 P1/30 且无 blocking gaps；高风险来源是预期的依赖元数据变化，SQLite、运行时、桌面和多入口契约均已有专项与全量证据。
- GitHub Actions run `33275432095` 最终确认 minimal-install、desktop-smoke 及 Ubuntu/macOS/Windows × Python 3.12/3.13 八个 Job 全绿；目标仓库在发布前再次确认为 `PRIVATE`。

## 阶段 15：桌面界面二次重构（2026-08-30）
- 0.6.0 的真实 Bundle 截图暴露四个核心视觉问题：左右两栏同时常驻导致主线被挤压；右侧表单像配置后台；中央空白没有任务语境；Composer 高度大但行动层级弱。
- 保留深色桌面工具定位，但从“卡片化后台”转向“精密编辑台”：更清晰的纵向基线、单一铜金强调色、纸白正文、细线分区和更紧凑的信息密度。
- 新布局应让对话与任务状态占主导，模型/权限等低频设置收进可显隐检查器；工作区与会话保留在左侧，但降低品牌头部和大按钮的占地。
- 视觉验收必须使用打包后的 `.app` 直接截图，而不是只看源代码或开发入口；窄窗口、空状态、运行中和技能面板仍需保持可用。
- 当前 `Main.qml` 已有可复用的 `QuietButton`、`ControlSelect`、技能面板、审批弹窗及 Controller 绑定，重构无需改核心协议；主要可集中在窗口骨架和视觉组件。
- 左栏目前把 52px 品牌、38px 大按钮、搜索、标题和工作区按钮纵向叠加，首屏固定开销过大；新的导航应缩成 248px 左右并把品牌、新建和搜索做成紧凑工具区。
- 主标题栏只有会话名与状态，缺少项目语境和检查器显隐入口；需要加入 workspace breadcrumb、运行状态胶囊和工具条，使右栏能够默认按需显示。
- 消息流本身的角色区分可保留，但助手回答目前用左侧 3px 竖线模拟引用块，视觉上像日志；应改成带编号/状态的编辑稿式回答块，工具调用则压缩为可扫读的执行行。
- 空状态的 72px `YF` 方块和三枚建议胶囊过于常见，且与大面积空画布组合后显得模板化；新空状态应以工作区任务清单/快捷启动呈现，直接建立“下一步做什么”的语境。
- Composer 固定 142–172px，却把图片开关、附件和发送并列在底部，输入动作不够聚焦；新 Composer 应是更紧凑的多行编辑器，底部工具条只显示关键上下文，发送按钮形成明确视觉锚点。
- 检查器现有运行/上下文/变更能力完整，适合保留功能并更换呈现：默认宽度不应永久挤占主画布，标签改为图文段控件，运行配置按两列/分组布局而不是纵向后台表单。
- 现有标题栏高度 72px 但右侧只有运行中才出现的取消按钮，空间利用率低；重构后用 64px 标题栏同时承载项目路径、状态、取消和检查器开关，不额外增加 Controller API。
- 第一张开发截图确认主画布占比和层级已明显改善：控制台收起后对话不再被三栏夹住，左侧导航从大按钮堆叠变为紧凑任务记录，标题栏同时表达项目、会话和运行状态。
- 截图也显示少量消息时仍会留下大块负空间，但这是对话画布的正常可增长区；通过靠近底部的 Composer 和顶部连续消息基线保持两端锚点，不再用装饰卡片填满空间。
- 第一轮 QML smoke 仅发现并修复一个会话列表 anchor loop；修正后开发入口 smoke 与截图命令均无 QML TypeError/ReferenceError。
- 控制台展开截图确认 306px 面板在 1480px 窗口中不会压垮主画布；上下文来源、路径和 Token 信息可扫读，关闭按钮与标题栏开关形成明确返回路径。
- `app.py` 的截图模式现在会在 `--preview-tab 1/2` 时同步展开控制台，因此文档可以分别生成运行主画布、上下文和变更三种真实 Bundle 视图。
- 项目 `review-changes` 要求发布前以具体缺陷优先审查当前 diff，`prepare-release` 要求版本在 Python 元数据、包、桌面 UI、部署配置和 Changelog 中一致，并将本地构建、GitHub 推送、远端 CI 作为三类独立证据。
- 发布审查发现 `Esc` 在“运行中 + 控制台打开”时会先关闭面板，破坏原有即时取消契约；已改为 busy 时始终优先取消，只有空闲时才关闭控制台。
- 发布审查还发现状态文案可能无限扩张并挤压标题；状态胶囊现限制为 220px，内部文本 188px 并启用右侧省略。
- 修复发布审查问题后的完整本地门为 155 passed、82.83% 覆盖率、20/20 Eval；Ruff/format、核心与桌面 mypy、0.7.0 sdist/wheel 均通过。
- 最终构建产物为 236 MiB 的 `YF-Harness.app`；Plist 版本 0.7.0、`local.yfharness.desktop` Bundle ID 与 ad-hoc codesign 完整性验证通过。
- 由 Bundle 自身生成的 2960×1648 主画布截图通过视觉复核：主消息流不再被常驻三栏夹住，编辑稿式响应、紧凑导航和底部 Composer 的层级清晰；控制台展开截图也未出现溢出或布局回退。
- 发布前 Change Radar 为 P1/40 且无 blocking gaps；P1 来自预期的版本/锁文件变更，不代表发现新的安全缺陷。
- GitHub Actions run `33309580532` 最终确认 minimal-install、desktop-smoke 及 Ubuntu/macOS/Windows × Python 3.12/3.13 八个 Job 全绿；目标仓库在推送前确认为 `PRIVATE`。
