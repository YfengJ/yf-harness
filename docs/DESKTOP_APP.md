# 桌面应用

YF-Harness 0.3 将 Qt Quick 桌面窗口作为主要交互入口。它不是网页壳，也不需要先打开终端窗口；
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

## 生成 macOS App

在 macOS 项目根目录运行：

```bash
./scripts/build_macos_app.sh
```

脚本会锁定并安装 `desktop-build` extra，使用 Qt 官方 `pyside6-deploy` / Nuitka 生成
`dist/YF-Harness.app`，写入应用名、`local.yfharness.desktop` Bundle Identifier 和 0.3.0 版本，
再执行 ad-hoc 签名、Plist 校验与 LaunchServices 启动 smoke。

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
- `Esc` 取消当前运行，`⌘/Ctrl+N` 新建任务，`⌘/Ctrl+Enter` 发送。

## 无头验证

```bash
QT_QPA_PLATFORM=offscreen QSG_RHI_BACKEND=software uv run yfh-desktop --smoke-test
uv run pytest -m desktop tests/integration/test_desktop.py
```

发布截图由真实 Bundle 使用 `--screenshot` 生成，预览数据会替换私人路径，不应提交真实用户名、
主机名、API Key 或历史会话。
