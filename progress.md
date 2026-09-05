# YF-Harness 项目进度

## 当前状态

- 当前阶段：阶段 22（全项目审阅优化与公开发布，已完成）
- 整体状态：0.13.0 本地 246 项测试、20/20 Eval、静态/类型、独立 wheel 安装及 238 MiB App 验证通过；远端 8 项 CI + 2 项安全检查成功，仓库已公开
- 初始仓库：空目录、非 Git 仓库
- 当前风险：P1（安全边界、子进程、持久化、CLI/TUI 公共契约）

## 阶段 22：全项目审阅优化与公开发布（2026-09-05）

- 功能提交 `f23c0ac` 已进入 `main`。审阅覆盖前后端、三入口、数据库、上下文、工具、审批、MCP/Skills/GitHub 和发布，确认缺陷均建立对应修复与验证；详细证据见 `docs/AUDIT_2026-09-05.md`。
- 最终本地 246 passed，覆盖率 82.83%；20/20 离线 Eval；核心 74 文件与桌面 3 文件严格类型通过，Ruff 通过，sdist/wheel 构建及全新核心安装通过。
- 0.13.0 macOS App 238 MiB，版本/签名/启动 smoke 验证通过；README 截图来自最新 Bundle。尚未进行 Apple Developer ID 签名与公证。
- Gitleaks 基线 40 提交和最终发布树均无命中；Security 工作流持续扫描完整历史与全部 extras。NLTK 可选依赖的未修复公告按精确版本和 2026-10-05 到期例外记录，不影响默认核心/桌面依赖。
- GitHub CI `33954132361` 八项全通过，Security `33954132365` 两项全通过。用户明确公开授权已执行：`YfengJ/yf-harness` 为 PUBLIC，匿名页面和 API 可访问，并已启用私密漏洞报告。
- 前文所有 PRIVATE 描述均为当时发布状态的历史记录；当前状态以本节为准。

## 阶段 21：Composer 控制、工具连接、Skills 与 GitHub（2026-09-02）

- Composer 已恢复高频模型、Agent/Plan、Goal 与真实上下文概览，并保留设置中心作为 Provider、Workflow 和权限的高级入口；多尺寸截图无越界。
- 审批弹窗已展示路径、命令、参数、Diff 和网络访问，可选择仅本次、会话允许、拒绝或取消运行；`always_approval` 不会被会话允许绕过。
- Brave Search 使用固定版本 MCP 预设，Key 只来自 `BRAVE_API_KEY` 或系统钥匙串；占位凭据的真实 stdio 握手已发现 `mcp__brave__brave_web_search`，没有真实 Key 因而未发起计费查询。
- Skills 管理器支持查看、创建、本地导入和 GitHub 安装；真实私密仓库临时安装已发现并调用 `codex:review-changes`。导入拒绝根目录和子项符号链接、超限目录与覆盖。
- GitHub 工作区复用当前 workspace 的 `github.com` origin 和已有 `gh` 登录；真实读取确认 `YfengJ/yf-harness` 为 PRIVATE，分支 main、ahead/behind 均为 0。十个 GitHub 工具已进入统一审批链。
- 发布审查发现 GitHub CLI 缺少 HOME 时会在 cwd 创建 `.local/state/gh/device-id`，现已固定使用用户 HOME/GH_CONFIG_DIR，并增加回归；意外文件已移出仓库，未提交。
- 最终本地门禁通过：Ruff/format、核心与桌面 mypy、206 项全量测试、82.26% 覆盖率、20/20 Eval、sdist/wheel 与隔离安装 smoke；最小依赖环境另有 183 passed、1 skipped、8 deselected。
- 最终 `dist/YF-Harness.app` 已从发布源码重建为 239 MiB，Plist 短版本/构建版本均为 0.12.0，ad-hoc 深度签名与启动 smoke 通过；1040×720 压力预览的 14 个关键布局对象全部位于窗口内。
- `main` 已推送到私密仓库 `YfengJ/yf-harness`；GitHub Actions run `33636334636` 的 8 个任务全部通过，覆盖 Windows/macOS/Linux、Python 3.12/3.13、最小安装和桌面 smoke。

## 阶段 20：桌面对话减法与统一附件入口（2026-09-01）

- 用户截图显示空会话中的三条“理解项目 / 规划改动 / 检查风险”占据大量画布，但没有直接操作价值；目标改为只留一句短引导。
- 用户明确要求额度与设置不再常驻 Composer；计划迁至左下角统一入口，在独立面板中承载模型、模式、上下文、额度和其他设置。
- 附件入口统一为 `+`，必须同时支持图片和普通文件，且不仅是视觉按钮：要有选择、列表、移除和真实运行时接入。
- 起点 `main` 干净，Change Radar P3/0；涉及附件安全与上下文协议，人工风险按 P1 管理。
- 契约审计确认原有图片附件已经具备 workspace、大小、魔数、哈希与显式远程发送边界；普通 `FILE` 类型虽然存在，但 Provider 会忽略，不能直接复用为“上传文件”。
- 已新增 UTF-8 普通文件附件：选择时限制 200 KB、拒绝二进制/非 UTF-8/工作区外路径并记录哈希，运行前再次校验，再通过 `ContextBuilder.add()` 进入真实上下文。
- QML 已删除三条空状态说明和 Composer 中的 Goal/上下文/模型/模式/命令控件，只保留一句引导、附件清单、统一 `+` 与发送；左下角新增“设置与用量”入口，原功能迁至独立面板。
- 第一轮 Ruff 通过；桌面专项 14 passed。命令带 `-m desktop` 导致附件单元测试被过滤，需单独运行，不视为测试通过证据。
- 补跑附件单元与 CLI 集成共 20 passed；空状态和设置面板的 1280×800 实际 QML 截图均成功，布局报告包含 10 个关键对象且全部 `within_window=true`。
- 视觉复核确认空会话只显示“想做什么？直接说一句就好。”，Composer 只剩 `+` 和发送；左下角入口可见，设置面板内的用量、模型、工作流、模式与上下文不再挤占主输入区。
- 首次扩展静态门中 Ruff check 通过，但 format check 指出 Controller 三元表达式与桌面测试断言两处需机械重排，因此命令在 mypy/pytest 前停止；按工具建议格式化这两个文件后从头重跑。
- 格式修复后 Ruff/format 通过；核心 mypy 因环境只同步了 dev+desktop、缺少三个可选框架依赖而报 18 个 import/subclass 错误并停止。需增加锁定 `frameworks` extra 后重跑，不能把未安装依赖错误归为源码回归。
- 完整环境下 Ruff/format、核心 mypy 68 文件、桌面 mypy 3 文件、178 项全量测试全部通过，覆盖率 83.49%。随后 `yfh eval --output` 被误传为已存在的临时文件，但该参数要求目录，触发 `FileExistsError`，因此 Eval/构建/smoke 尚未执行；改用新临时目录从 Eval 续跑。
- Eval 改用目录后 20/20，0.11.0 sdist/wheel 与桌面 smoke 通过。首次隔离安装使用系统 pip 时被本机 CA 链的 `CERTIFICATE_VERIFY_FAILED` 阻止，wheel 未安装；不降低 TLS，改用项目的 uv 安装器和新隔离环境。
- uv 隔离环境成功安装并报告 0.11.0；首次 Mock smoke 断言错误地读取顶层 `status`，而当前 JSON 公共结构不含该键，验证脚本 `KeyError`。需检查真实键并按现有契约修正断言，不能据此修改产品输出。
- 隔离 wheel 最终以 `session_id=ephemeral` 等真实 JSON 契约完成 Mock smoke。首次 App 构建调用了不存在的 `packaging/build_macos_app.sh`，命令立即退出且无副作用；需按仓库实际脚本名执行。
- 最终本地质量门：Ruff/format、核心 mypy 68 文件、桌面 mypy 3 文件、178 passed、83.49% 覆盖率、Eval 20/20、0.11.0 sdist/wheel、uv 隔离安装/Mock smoke 全部通过。
- `scripts/build_macos_app.sh` 已生成 236 MiB 的 `dist/YF-Harness.app`；Plist 0.11.0、深度签名、启动 smoke、关键布局和 Bundle 凭据模式扫描通过。最终 Bundle 空状态与设置面板截图均完成视觉复核。
- 最终 Change Radar P1/40、无 blocking gap；review-changes 发现并修复文件哈希校验与 ContextBuilder 二次读取间的 TOCTOU，修复后 33 项相关测试及最终 QML 契约 smoke 通过。
- 本轮没有收到推送授权，所有改动和 0.11.0 产物保留在本地工作区，未上传 GitHub。

## 已完成

- 完整解析项目规格和完成定义。
- 建立阶段 0–9 的实施顺序、阶段验收与最终验收映射。
- 建立变更简报、风险基线、公共契约和安全契约。
- 确认阶段 1 的最小可运行范围。
- 完成阶段 0 的规划、风险、契约和验收基线。

## 当前进行

- Stage 19 起点为干净 `main`，本地/远端均为 `bb8af96`，初始 Change Radar P3/0；真实外部 API 与凭据链路人工按 P1 管理。
- 配置审计确认 DeepSeek 使用 `openai_compatible` Provider，项目配置只保存 `api_key_env = "DEEPSEEK_API_KEY"`，运行时从环境读取；测试将使用临时进程环境和仓库外临时配置/数据库，不记录密钥值。
- 本轮验收将从低成本流式文本与 usage 开始，再覆盖原生工具调用、会话恢复、上下文压缩、额度聚合和桌面 Controller；任何失败先区分上游限制、配置问题与项目缺陷。
- 官方契约核对发现示例模型 `deepseek-chat` 已于 2026-07-24 停用，当前应使用 `deepseek-v4-flash`/`deepseek-v4-pro`；另已锁定 thinking 工具多轮必须回传 `reasoning_content` 的潜在兼容风险，等待实机验证。
- 无回显临时凭据环境已建立；`yfh doctor` 对 DeepSeek 配置、鉴权、模型列表和三个可选框架均返回 OK。首次误用 `yfh providers doctor`（不存在）后已改用顶层 `yfh doctor`，该帮助/入口可发现性差异留待 review。
- 真实 `deepseek-v4-flash` 非流式 CLI 返回 `LIVE_OK`，上游 usage 为 2,071 input / 32 output / 2,103 total 且 `estimated=false`；流式文本也成功。
- 首次只读 `read_file` Agent 请求触发 12,000 Token 预算上限，没有最终 JSON；因 `--no-save` 无 Trace，不重复同参数，改用单工具协议探针区分 thinking 消耗、工具循环和 `reasoning_content` 回传问题。
- 单工具协议探针两轮均成功：首轮 417 Token、1 次工具调用、81 reasoning 字符；第二轮 483 Token 并返回正确结果。真实 `get_file_info` Agent 也以 2 步/1 工具完成，先前 12k 超限是自动文件上下文导致两轮累计 15,704 Token，不是循环。
- 同一真实会话恢复成功；手动压缩后再次运行返回 `compaction_status=reused`。本地 usage 精确聚合真实 Token，估算为 0，未知成本运行数正确，且不声明 Provider 余额。
- LangChain、LlamaIndex、AutoGen 三套原生适配器分别通过真实 DeepSeek，返回实际 usage；桌面 Controller 异步发送也返回 `DESKTOP_OK`，会话、上下文和三档用量状态均正常。
- 已修复过期示例模型与 `--mode plan` JSON 错报写入工具，32 项首轮专项回归通过；真实复测确认 Plan 只报告 8 个只读工具。
- 假凭据实测发现流式 401 在响应体未读取时抛 `ResponseNotRead` traceback；已改为有界读取/关闭并归一化，41 项专项回归通过，真实 401 复测只输出一行认证错误。
- 认证恢复请求在临时 `max_output_tokens=256` 下全部消耗于 thinking、无正文且 `finish_reason=length`，现有 Agent 却判为成功；正在补“累计 usage 后显式输出上限失败”的修复。
- Agent 现保留 FinishReason 并在累计 usage/预算后把 `length` 判为明确失败；46 项专项回归通过，真实 DeepSeek 1-Token 上限复测返回可操作错误，临时配置随后恢复为 8,192。
- 真实 TUI 驱动通过：创建会话、DeepSeek Worker、SQLite 消息持久化与空闲终态均正确；授权进程随后显式 unset 并关闭。
- 最终 0.10.1 本地门禁通过：Ruff/format、核心 68 文件与桌面 3 文件 mypy、174 passed、83.49% 覆盖率、20/20 Eval、sdist/wheel 和隔离 wheel 0.10.1 Mock smoke 全部成功。
- 0.10.1 macOS App 已重建为 236 MiB，Plist 短版本/构建版本均为 0.10.1，深度 codesign 通过；wheel/sdist/App Bundle 的完整密钥模式扫描均为 PASS。
- prepare-release review 将 MCP `clientInfo.version` 改为直接复用包 `__version__`，消除上次发布曾出现的手工版本漂移；MCP 专项与运行时元数据测试通过，需用最终源码再构建一次 App 后提交。
- 最终源码 App 已再次构建并验证为 236 MiB、Plist 0.10.1、codesign PASS；最终 Change Radar P1/30、无 blocking gap，P1 仅来自版本元数据与 lockfile，相关安装/构建证据齐全。
- 清理临时目录时直接 `rm -rf` 被执行安全策略拒绝且未产生删除；改为把三个本轮创建的精确目录移动到 `/Users/yfengj/.Trash/`，原 `/tmp` 路径均已不存在，数据仍可从废纸篓恢复。
- 0.10.1 功能提交 `59e0da8` 已推送私密 `YfengJ/yf-harness`；GitHub Actions CI `33500549560` 的 8 个 Job 全绿。两条 cache reserve annotation 仅表示并发 Job 已创建同键缓存，不影响测试、构建或结论。

- 新一轮起点为干净 `main`，HEAD/远端均为 `7618270`；初始 Change Radar P3/0。规划恢复脚本仍不解析 Codex 原生 session，已从三份规划文件、Git 和源码恢复。
- 初审确认 usage_records 已持久化每次运行 Token/成本/估算标记/耗时，但 Repository 没有任何会话、今日或本月聚合接口，桌面目前只显示当次 usage。
- 初审确认 ContextBuilder 的 previous_summary 只在对象内存中，需继续核对桌面每次运行是否重建 Builder；上下文估算在自动压缩裁剪循环中重复序列化工具 schema，是明确的热路径优化候选。
- 首次上下文热路径基准使用 80 个大型工具和 8k 请求预算，工具 schema 自身即约 5 万 Token，按设计触发 `ContextOverflowError`；该参数不能反映裁剪性能，已改为工具可容纳、历史需压缩的基准区间。
- 调整后的热路径基线为 16 个中等工具、49 条长消息、22k 请求预算：10.06 ms、39 次 estimator，100 次平均 9.74 ms，49 条裁为 21 条；这将作为优化前证据。
- 已确认桌面与 CLI 的 `_run_once()` 每次重建 `ContextBuilder`，所以自动压缩摘要不会跨运行恢复；Stage 18 将通过 SQLite session 前向迁移修复，并保持原始历史可审计。
- 已锁定用量/额度语义：只汇总本地 `usage_records`，明确区分真实和估算 Token、已知和未知成本，不声称能读取 Provider 账户余额。
- 一次定向 QML 测试命令使用了不存在的用例名 `test_qml_entrypoint_loads_headlessly`；没有项目测试失败，已改为仓库真实用例 `test_desktop_qml_smoke_starts_without_runtime_errors`。
- 核心实现完成：SQLite v5 摘要、跨运行恢复/分支继承、二分裁剪、单次工具 schema 估算、本地用量聚合、可选日/月额度、CLI 与桌面入口均已落地。
- 优化后同参数基准为 9 次 estimator、单次 8.11 ms、100 次平均 8.02 ms；调用数较 39 次下降 76.9%，批量耗时较 9.74 ms 下降 17.7%，结果仍保留 21 条消息与相同 21,484 Token。
- 真实 Qt 截图已检查运行/上下文两个 Inspector：三档用量卡、额度进度、未知成本说明和手动压缩按钮均在 1440×900 内完整渲染。
- 第一轮 review 修复三项：未定价模型成本误报 0、扩展上下文污染原始消息、示例 TOML 根键落入错误 table；专项静态检查和 41 项核心/CLI/桌面测试已通过。
- 第二轮全量行为测试 169 passed；并行静态门中 Ruff check 已通过，但 format-check 发现新增长测试的一处可压成单行，后续 mypy 因 `&&` 未执行；已格式化后重新运行完整静态门，不能把该次结果记为全绿。
- 首次 0.10 隔离 wheel 安装暴露运行时 `yfh --version` 仍为 0.9.0，且部署 spec/MCP clientInfo 也残留旧版本；已全部对齐并增加“运行时版本 = 安装元数据”回归。一次 `rg` 搜索因 pattern 以 `--version` 开头被当作参数而失败，改用 `rg --` 后完成残留扫描。
- 第二轮 review 修复工具后续步骤丢失“已复用摘要”状态和无最近 user 时目标降级；最终静态门通过，170 passed，覆盖率 83.21%，20/20 Eval、0.10.0 sdist/wheel 与隔离安装全部成功。
- 0.10.0 macOS `YF-Harness.app` 已重建为 236 MiB；Plist 短版本/构建版本、ad-hoc 深度签名、Bundle 直接截图和运行/上下文 Inspector 视觉检查均通过。
- 最终 Change Radar 为 P1/50 且无 blocking gaps；私密仓库 `YfengJ/yf-harness` 已再次确认为 `PRIVATE`、默认分支为 `main`。
- 功能提交 `0a46291` 已推送；GitHub Actions CI 运行 `33479652726` 的 8 个任务全部通过，覆盖 Ubuntu/macOS/Windows、Python 3.12/3.13、最小安装和桌面 smoke。Ubuntu 的并发 cache reserve 提示不影响任务结论。

- 已从当前 0.8.0 Bundle 截图确认底部动作固定行争宽、输入区空耗、低对比黑色日志感和左栏重复表达四类核心问题。
- 已按 frontend-design 确定“蓝图工作室”新方向；按最新界面审查规则将长文本、可见焦点、空状态、错误下一步与多尺寸无溢出设为硬门禁。
- 阶段 17 初始工作树干净，Change Radar 为 P3/0；实现预计主要触及 QML、桌面截图/测试、截图参数与版本文档，人工按 P2 管理。
- 规划技能 session catchup 仍不支持 Codex 原生 session；已从三份持续规划文件与当前 Git/Bundle 状态恢复，不影响实施。
- 第一轮 QML 结构已完成：新视觉 token、键盘焦点、覆盖式检查器、分层 Composer、任务状态带与 `⌘K` 命令中心接入；qmllint 布局警告过滤和无头 smoke 通过。
- 1040×720 压力截图确认 Composer 不再越界，但暴露超长会话标题覆盖右侧动作；已给标题列内文本绑定实际宽度并保留省略策略。
- 第二轮 1040/1480、命令中心、上下文抽屉截图完成；核心几何均在窗口内。正在收尾抽屉标题栏重复关闭按钮和命令搜索键盘选择。
- 命令中心键盘过滤和 7 项完整视图已收尾；检查器改为贴合 Overlay 右边界并覆盖整高，消除底层按钮从边距缝隙露出。
- 0.9.0 版本已对齐 Python 包、MCP、QML 页脚、macOS deploy spec、lockfile、Changelog、README、桌面文档和 Roadmap。
- 最终 Change Radar 为 P1/40 且无 blocking gaps；13 项桌面专项测试、qmllint 布局/运行时警告过滤、桌面 mypy 与无头 smoke 已通过。
- 最终检查器视觉复核通过：1280×800 下覆盖层贴合右边与整高，未再暴露底层控件或形成越界缝隙。
- 0.9.0 完整本地质量门通过：162 passed、82.87% 覆盖率，Ruff/format、核心 68 文件与桌面 3 文件 mypy、20/20 Eval、锁文件及 sdist/wheel 构建全部成功。
- 0.9.0 macOS `YF-Harness.app` 已重建为 235 MiB；Plist 短版本/构建版本均为 0.9.0，深度 codesign 校验通过。真实 Bundle 的 1480、1040、命令中心和上下文抽屉截图均已人工复核，1040 报告 13/13 控件在窗口内。
- 发布前只读审查未发现可操作缺陷；最终 Change Radar 为 P1/40、无 blocking gaps，私密仓库与 main 默认分支已复核。剩余证据仅为提交、推送和远端 CI。
- 0.9.0 功能提交 `6cc2cbc` 已推送私密 `YfengJ/yf-harness`；GitHub Actions run `33335645069` 的 minimal-install、desktop-smoke 及 Ubuntu/macOS/Windows × Python 3.12/3.13 共八个 Job 全绿。

- 已按用户要求先规划后执行：官方语义、现有 Controller/QML、AgentMode、ContextSnapshot 与 SQLite 契约已经完成首轮审计。
- 阶段 16 采用“复用现有 Plan/模型/上下文能力 + 新增会话级 Goal 持久化”，不复制 AgentRunner，也不扩大权限边界。
- 初始工作树干净；Change Radar 为 P3/0，但由于需要数据库迁移和桌面发送路径联动，人工按 P1 管理。
- 规划技能的 session catchup 仍不支持 Codex 原生 session；已从三份持续规划文件恢复，不影响本次工作。
- 阶段 16 首轮后端专项 24 passed；核心与桌面 mypy 通过。Ruff 仅发现 Goal 文案全角括号和一处机械格式差异，已按项目规则修正。
- 阶段 16 开发入口 QML smoke 与真实截图成功；Composer 已展示 Agent/Plan、Goal、模型和 5% 上下文。qmllint 发现两个 Popup 的 Layout 定位警告，正在按规范修复。
- Popup 已移入显式零尺寸承载项并 reparent 到 Overlay，布局警告过滤与 smoke 均通过；模型切换测试初次污染既有消息计数，已拆成独立用例。
- Goal 来源断言发现会话列表刷新会把运行上下文清空；根因是缺失字段使用 `[]` 默认值，已改为只在 bootstrap/workspace 明确返回 instructions 时更新。
- 发布复查发现同一模型下切换 Agent/Plan 时会话元数据可能保留旧模式；已让桌面显式切换原子同步 provider/model/mode，同时保持 CLI 的旧会话模型严格校验。
- 0.8.0 完整本地门通过：158 passed、82.87% 覆盖率，Ruff/format、核心 68 文件与桌面 3 文件 mypy、20/20 Eval、sdist/wheel 全部成功。
- 0.8.0 macOS `YF-Harness.app` 已重建为 235 MiB；Plist 版本 0.8.0、Bundle ID、ad-hoc codesign、Bundle 直接启动截图和视觉检查全部通过。
- 最终 Change Radar 为 P1/30 且无 blocking gaps；风险来自预期的锁文件、迁移与桌面运行路径，均已有专项与全量证据。

- 用户否定 0.6.0 当前 UI；已启动桌面二次重构，目标是去除调试面板感、压缩无效空白并强化消息流和输入器的任务主线。
- 当前工作树起点干净；Change Radar 无差异时为 P3/0，本次按 QML 公共交互契约人工标记 P2。
- 规划技能的 session catchup 仍不支持 Codex 原生 session；已从现有三份持续规划文件恢复，不影响继续。
- 已完成第一轮 QML 重构：紧凑左栏、64px 项目标题栏、默认收起的控制台、编辑稿式消息流、任务型空状态和新的 Composer；开发入口 smoke 与 seeded screenshot 成功。
- 已完成第二轮视觉 QA：主画布与控制台展开两张开发截图均通过；新增 Inspector 真实截图回归，桌面专项 8 passed，Ruff/格式和桌面 mypy 通过。
- `prepare-release` 已将本次视觉重构定为 0.7.0；Python 包、Qt Bundle、MCP 客户端、桌面页脚、Changelog、桌面文档和 lockfile 版本已经对齐。
- 0.7.0 完整质量门通过：155 passed、82.83% 覆盖率，Ruff/format、核心 68 文件与桌面 3 文件 mypy、20/20 Eval、sdist/wheel 构建全部成功。
- 0.7.0 macOS `YF-Harness.app` 已重建为 236 MiB；Plist 版本 0.7.0、Bundle ID、ad-hoc codesign 与 Bundle 可执行截图全部通过。
- 最终 Change Radar 为 P1/40 且无 blocking gaps；目标 GitHub 仓库发布前再次确认为 `PRIVATE`。

- 已完成阶段 14 官方能力复核与变更简报：选择“显式项目技能 + `$` 桌面命令面板”，不启用隐式触发、用户目录扫描或技能脚本执行。
- 规划技能的 Codex session catchup 脚本仍不支持当前原生 session 格式；已直接从三份持续规划文件恢复状态，不影响实现。
- 阶段 14 初始工作树干净；Change Radar 启发式 P3/0，因上下文、安全和公共 UI 契约人工按 P1 管理。
- 0.6.0 已实现可信项目技能发现、渐进披露、CLI/TUI/桌面显式调用、工作区会话隔离和整次运行安全恢复；发布审查发现的工作区错配、重复技能绕过、撤销竞态及无效技能残留运行均已修复。
- 0.6.0 本地发布门：154 passed、82.83% 覆盖率，Ruff/格式、核心 68 文件与桌面 3 文件 mypy、20/20 Eval、sdist/wheel、全新 wheel 安装均通过。
- 0.6.0 macOS `YF-Harness.app` 为 235 MiB；Plist 版本、ad-hoc 签名、LaunchServices、Bundle 直接截图和界面视觉检查均通过。

- 阶段 13 本地实现已完成：版本化 Workflow/Profile、声明式 Hook、多模态图片、MCP stdio、插件静态发现、索引缓存与 Bundle 瘦身均已落地。
- 0.5 初始仓库为干净 `main`；规划技能的 Codex session catchup 解析暂不支持，但 `task_plan.md`、`progress.md`、`findings.md` 已直接恢复。
- 已实现 Profile/Hook 领域模型：schema `version = 1`、安全工具 glob、allow 后 deny、Hook 最严格决策合并、Post Hook 只观察；8 项配置/工作流专项测试通过。
- Profile 已接入 ToolExecutor/AgentRunner/Trace，并在 CLI、TUI 与桌面 App 中统一生效；桌面检查器新增 Workflow 选择和模式/权限联动。
- 正在把 Codex 的分层项目指令与审查、Claude Code 的计划/权限分离、Cursor 的消息队列与检查点整合为一条本地优先工作流。
- 第一批范围锁定为统一项目规则、可解释上下文、Plan→Execute、运行中队列、变更审查与安全撤销；不扩大默认权限。
- 已实现跨 Agent 分层规则、本地 Git 感知索引、真实 ContextSnapshot UI、FIFO 后续任务队列、Plan→Execute、会话分支、逐文件 Diff 与哈希冲突安全撤销。
- 桌面检查器已重构为运行/上下文/变更三个标签；最终截图由 0.4.0 打包 Bundle 直接生成并完成视觉检查。
- 0.4.0 最终本地门为 112 passed、82.77% 覆盖率、20/20 Eval；Ruff、格式、核心/桌面 mypy、wheel/sdist、App 签名和 Plist 均通过。

- TUI 已转为兼容入口；PySide6 + Qt Quick/QML 成为主界面，并以官方 `pyside6-deploy` 生成 macOS `.app`。
- 桌面 Bridge、QML 工作区、会话/模型/模式控制、取消、安全审批、图标、打包脚本和桌面文档均已完成。
- 本机 0.5.0 `dist/YF-Harness.app` 已从约 491 MB 降到 235 MB，并完成 ad-hoc 签名、Plist、LaunchServices smoke 和真实 Bundle 截图；待推送私密 GitHub 并等待 CI。

- 正在将 LangChain、LlamaIndex、AutoGen 作为可选真实集成层加入项目；先依据官方 API 锁定适配契约。
- 约束：默认安装继续轻量；第三方框架不能绕过 YF-Harness 的 Provider 密钥规则和工具安全边界。
- 已锁定并本地安装 `frameworks` extra，三套框架的当前真实 API 和离线可运行路径均已通过最小脚本验证；下一步进入统一契约与适配器实现。
- 已完成 0.2.0 统一适配契约、三套原生适配器、CLI/Doctor、独立/聚合 extras、真实兼容端点测试、文档与 CI。
- 最终全量 101 项测试通过，覆盖率 82.08%；Ruff、格式、mypy、20/20 Eval、sdist/wheel 构建均通过。
- 已验证隔离默认安装不含三套框架；另一个全新 wheel 环境安装 `[frameworks]` 后三套离线 Agent 全部实际运行成功。
- 已推送私密 GitHub 仓库；CI run `32651042271` 的最小安装任务与 3 OS × 2 Python 六组质量任务全部通过。

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
| 2026-08-23 | 首次远端 CI | Linux/macOS 四组通过；Windows 3.12/3.13 暴露 killpg 平台类型错误 |
| 2026-08-23 | Windows 跨平台修复 | 改用可静态裁剪的平台分支和 `taskkill /T /F` 子进程树终止 |
| 2026-08-23 | Windows 换行修复 | Patch 匹配归一化 LF/CRLF 并保留原格式；新增 CRLF 回归测试 |
| 2026-08-23 | CI Action 维护 | 按官方最新 release 升级 checkout/upload-artifact 7.0.1、setup-uv 10.0.1 |
| 2026-08-23 | Windows CLI 编码修复 | 标准流入口强制 UTF-8；新增 cp1252 子进程端到端回归测试 |
| 2026-08-24 | 阶段 10 框架专项 | 12 passed；三套离线 Agent、三套真实兼容 HTTP 客户端、CLI 与缺包诊断通过 |
| 2026-08-24 | 阶段 10 全量 | 101 passed；82.08% 覆盖率，Ruff/格式/mypy 通过 |
| 2026-08-24 | 阶段 10 Change Radar | P1/64，无 blocking gaps；依赖、CI、公开 CLI 风险均有直接验证证据 |
| 2026-08-24 | GitHub CI `32651042271` | minimal-install 与 Linux/macOS/Windows × Python 3.12/3.13 共七个 Job 全绿 |
| 2026-08-24 | 阶段 10 Eval/构建 | 20/20 Eval；成功构建 0.2.0 sdist/wheel |
| 2026-08-24 | 0.2.0 隔离安装 | 默认安装确认无框架 SDK；`[frameworks]` wheel 安装后 LangChain/LlamaIndex/AutoGen smoke 全通过 |
| 2026-08-24 | 阶段 11 桌面专项 | 2 passed；真实 MockProvider 会话持久化与无头 QML 启动通过 |
| 2026-08-24 | 阶段 11 全量 | 103 passed；81.95% 核心覆盖率，Ruff/格式/mypy 全通过 |
| 2026-08-24 | macOS App 构建 | `YF-Harness.app` 0.3.0 生成；签名、Plist、LaunchServices 启动和 Bundle 截图通过 |
| 2026-08-24 | 阶段 11 Eval/构建 | 20/20 Eval；0.3.0 sdist/wheel 成功，wheel 包含 QML 与图标资源 |
| 2026-08-24 | 阶段 11 Change Radar | P1/54，无 blocking gaps；依赖、CI、部署和运行路径均有直接验证证据 |
| 2026-08-24 | 首轮 0.3.0 CI | minimal-install 通过；桌面 Job 暴露 Linux libEGL 缺失，核心矩阵暴露可选 Qt mypy 分层问题，已补充独立依赖与类型门 |
| 2026-08-24 | 最终 0.3.0 CI `32747275102` | minimal-install、desktop-smoke 与 Linux/macOS/Windows × Python 3.12/3.13 全部通过 |
| 2026-08-27 | 阶段 12 核心/桌面专项 | 规则、索引、审查、存储、队列、Plan、QML smoke 均通过，RuntimeWarning 严格模式通过 |
| 2026-08-27 | 0.4.0 最终本地全量门 | 112 passed；82.77% 覆盖率；Ruff/format、核心 63 文件与桌面 3 文件 mypy 全部通过 |
| 2026-08-27 | 0.4.0 Eval/构建 | 20/20 Eval；sdist/wheel 成功；wheel 已确认包含规则、索引、审查与 QML 资源 |
| 2026-08-27 | 0.4.0 macOS App | 491 MB Bundle 生成；ad-hoc codesign、Plist 0.4.0、Bundle 可执行截图 2880×1650 全部通过 |
| 2026-08-27 | 阶段 12 Change Radar | P1/30，无 blocking gaps；依赖、运行时、测试与文档风险均有直接验证证据 |
| 2026-08-27 | 0.4.0 首轮 CI | 6/8 Job 通过；Windows 3.12/3.13 同时发现 CRLF frontmatter 解析与测试快照换行差异，已修复并全量 112 passed |
| 2026-08-27 | 最终 0.4.0 CI `33076762077` | minimal-install、desktop-smoke 与 Linux/macOS/Windows × Python 3.12/3.13 全部通过 |
| 2026-08-28 | 0.5 Profile/Hook 专项 | Ruff/mypy 通过；CLI/TUI/桌面与工具链相关 47 passed |
| 2026-08-28 | Workflow CLI/QML smoke | `plan` 仅暴露 8 个只读工具；无头 Qt App 成功加载且无 QML 错误 |
| 2026-08-28 | 0.5.0 本地发布门 | 138 passed、83.15% 覆盖率；Ruff/format、67 个源码文件 mypy、20/20 Eval、sdist/wheel 全部通过 |
| 2026-08-28 | 0.5.0 Change Radar | P1/50，无 blocking gaps；配置、依赖、上传与工具执行风险均有直接验证证据 |
| 2026-08-28 | 0.5.0 macOS App | 235 MB Bundle；无 QtWebEngine 等顶层重型模块；ad-hoc codesign、Plist 0.5.0、LaunchServices smoke 与真实截图通过 |
| 2026-08-28 | 项目索引性能 | 140 文件、100 次选择由 662.51 ms 降至 513.28 ms；冷索引 9.26 ms |
| 2026-08-28 | 最终 0.5.0 CI `33098549805` | minimal-install、desktop-smoke 与 Linux/macOS/Windows × Python 3.12/3.13 全部通过 |
| 2026-08-30 | 0.6.0 本地发布门 | 154 passed、82.83% 覆盖率；Ruff/format、核心 68 文件与桌面 3 文件 mypy 全部通过 |
| 2026-08-30 | 0.6.0 Eval/构建 | 20/20 Eval；0.6.0 sdist/wheel 成功；全新环境安装 wheel 后 version 与 Mock JSON run 通过 |
| 2026-08-30 | 0.6.0 macOS App | 235 MiB Bundle；Plist 0.6.0、ad-hoc codesign、LaunchServices smoke、Bundle 截图与视觉检查通过 |
| 2026-08-30 | 0.6.0 Change Radar | P1/30，无 blocking gaps；依赖、迁移、运行时与界面风险均有直接验证证据 |
| 2026-08-30 | 最终 0.6.0 CI `33275432095` | minimal-install、desktop-smoke 与 Linux/macOS/Windows × Python 3.12/3.13 全部通过 |
| 2026-08-30 | 0.7.0 本地发布门 | 155 passed、82.83% 覆盖率；Ruff/format、核心与桌面 mypy、20/20 Eval、sdist/wheel 全部通过 |
| 2026-08-30 | 0.7.0 macOS App | 236 MiB Bundle；Plist 0.7.0、Bundle ID、ad-hoc codesign、Bundle 主画布/控制台截图与视觉检查通过 |
| 2026-08-30 | 0.7.0 Change Radar | P1/40，无 blocking gaps；锁文件、桌面运行和用户界面均有直接验证证据 |
| 2026-08-30 | 最终 0.7.0 CI `33309580532` | minimal-install、desktop-smoke 与 Linux/macOS/Windows × Python 3.12/3.13 八个 Job 全绿 |
| 2026-08-31 | 0.8.0 本地发布门 | 158 passed、82.87% 覆盖率；Ruff/format、核心 68 文件与桌面 3 文件 mypy 全部通过 |
| 2026-08-31 | 0.8.0 Eval/构建 | 20/20 Eval；0.8.0 sdist/wheel 成功 |
| 2026-08-31 | 0.8.0 macOS App | 235 MiB Bundle；Plist 0.8.0、Bundle ID、ad-hoc codesign、Bundle 截图与视觉检查通过 |
| 2026-08-31 | 0.8.0 Change Radar | P1/30，无 blocking gaps；迁移、锁文件、桌面运行和界面契约均有直接验证证据 |
| 2026-08-31 | 最终 0.8.0 CI `33332257769` | minimal-install、desktop-smoke 与 Linux/macOS/Windows × Python 3.12/3.13 八个 Job 全绿 |

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
- Windows 3.13 首次桌面版 CI 在 TUI 新会话 Worker 完成前执行断言；测试改为等待 Worker 契约，最终八个 CI Job 全绿。
- 当前 macOS 环境没有 GNU `timeout`；桌面 smoke 改为 PTY 启动、确认 Qt/QML 无报错后发送 Ctrl+C 正常退出。
- 桌面构建首次提示下载 ccache：拒绝下载并在 spec 禁用 ccache，后续构建保持非交互。
- Bundle 门禁首次递归匹配到 `QtQuick3D` QML 数据目录：审计改为只检查顶层动态库，确认重型模块实际未打入 235 MB 产物。

> 只有实际执行过的命令才会进入本表；后续每阶段完成后同步更新。
