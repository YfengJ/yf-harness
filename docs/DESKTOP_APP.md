# 桌面应用

YF-Harness 0.8 将 Qt Quick 桌面窗口作为主要交互入口。它不是网页壳，也不需要先打开终端窗口；
打包后的 `YF-Harness.app` 包含 Python、Qt 与项目运行时，可以从 Finder 双击启动。

## 直接运行源码

```bash
git clone https://github.com/YfengJ/yf-harness.git
cd yf-harness
uv sync --extra desktop
uv run yfh desktop
```

默认 MockProvider 不需要 API Key。应用首次启动会在系统用户数据目录创建 SQLite；Provider、模型、
workspace 和安全策略继续读取同一套 YF-Harness 配置。
从 Finder 双击启动后，可点击左下角“切换项目”。最近选择只保存在本机的
`desktop-state.json`，下次启动自动恢复，不会写进项目仓库。

## 生成 macOS App

在 macOS 项目根目录运行：

```bash
./scripts/build_macos_app.sh
```

脚本会锁定并安装 `desktop-build` extra，使用 Qt 官方 `pyside6-deploy` / Nuitka 生成
`dist/YF-Harness.app`，写入应用名、`local.yfharness.desktop` Bundle Identifier 和 0.8.0 版本，
再执行 ad-hoc 签名、Plist 校验与 LaunchServices 启动 smoke。

0.8 构建继续显式排除未使用的 WebEngine、Quick3D、Charts、Sensors 与 Test 顶层二进制，
并以 320 MiB 为发布门禁。本机验证产物为 235 MB；不同 Qt 补丁版本可能有少量波动。

构建完成后可执行：

```bash
open dist/YF-Harness.app
```

也可把 App 拖到 `/Applications`。ad-hoc 签名只用于本机验证；正式发布给其他 Mac 时，应使用
Developer ID Application 证书重新签名，并提交 Apple notarization。项目不会把本机签名冒充正式分发签名。

## 桌面与核心的边界

- Qt 主线程只负责渲染和输入；Agent 在单独工作线程的 asyncio loop 中运行。
- 流式模型事件、工具状态、Token 用量与错误通过 queued signal 返回界面。
- 工具审批弹窗返回同一 `ApprovalDecision`，不会绕过 `ToolExecutor`、Policy 或 WorkspaceGuard。
- 会话与消息仍写入同一个 SQLite Repository；CLI、TUI 与桌面版可以读取相同历史。
- 新会话记录所属 workspace；桌面和 TUI 只列出当前项目会话，避免跨项目误执行。
- `Esc` 优先取消当前运行，空闲时关闭控制台；`⌘/Ctrl+N` 新建任务，`⌘/Ctrl+Enter` 发送，`Ctrl+.` 打开或收起控制台。

## 0.7 精密编辑台

- **主画布：** 控制台默认收起，对话、运行证据和 Composer 形成连续任务主线。
- **控制台：** 点击标题栏按钮或按 `Ctrl+.` 打开运行、上下文和变更检查器；低频设置不再常驻挤压内容。

- **运行：** Provider、模型、Plan/Agent/Review 模式与权限保持显式；Plan 完成后必须点击“执行此计划”才进入 Agent。
- **上下文：** 展示当前实际注入的项目规则、自动相关文件、历史、工具定义、Token 预算和压缩状态。
- **变更：** 按会话列出 Agent 文件变更与统一 Diff；既可撤销单文件，也可按 run 整组原子回退。
- **队列：** Agent 运行时仍可输入后续任务；成功后顺序执行，取消或失败会暂停，必须手动继续或清空。
- **分支：** “分支当前会话”复制对话历史但不复制或修改文件，适合比较另一条实现路线。
- **Workflow：** 切换 Profile 时联动默认模式/权限，运行时同时约束模型可见和真实执行的工具。
- **图片：** 附件显示“仅本地/发送给模型”；远程发送必须在选取图片前显式打开。
- **技能：** 输入 `$` 打开项目技能面板；完整正文只在选择后进入当次上下文，不自动执行脚本。

## 0.8 Composer 工作流控制

- **Agent / Plan：** 输入框底栏直接切换；Plan 继续只暴露只读工具，生成后仍需显式点击“执行此计划”。
- **持久 Goal：** 点击 `/goal` 编辑，或输入 `/goal <目标>`；`/goal done` 完成，`/goal clear` 清除。目标跟随当前会话与分支保存，不会自动启动任务或改变审批策略。
- **模型：** Composer 直接列出当前 Provider 已配置的模型；完整 Provider、Workflow 和权限仍在控制台中管理。
- **上下文：** 底栏显示最后一次真实快照的使用比例；展开后显示 Token 预算、剩余量、来源数量与压缩状态，点击可进入完整来源列表。新会话在实际运行前明确标为待刷新。

## 无头验证

```bash
QT_QPA_PLATFORM=offscreen QSG_RHI_BACKEND=software uv run yfh-desktop --smoke-test
uv run pytest -m desktop tests/integration/test_desktop.py
```

发布截图由真实 Bundle 使用 `--screenshot` 生成，预览数据会替换私人路径，不应提交真实用户名、
主机名、API Key 或历史会话。
