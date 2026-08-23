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
