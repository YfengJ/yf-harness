# Workflow、附件、MCP 与插件边界

YF-Harness 0.5 把“怎样运行”收敛为版本化 Workflow Profile。Profile 可设置默认
mode、approval policy、工具 allow/deny 和声明式 Hook。先应用 allow，再应用 deny；
ToolExecutor 在暴露工具和执行工具两处都检查 Profile，避免模型手写未暴露工具名绕过。

Pre Hook 的合并顺序是 deny > ask > allow > observe。基础 Policy 的 deny/ask 不能被 Hook allow
放宽。Post Hook 只记录成功或失败，因为副作用已经发生。首版 Hook 不运行任意 Shell、
HTTP 或模型，避免将新执行面伪装成配置。

图片附件只支持 PNG、JPEG、GIF 和 WebP，单文件最大 10 MiB。准备时校验 workspace、
文件魔数、大小与 SHA-256；发送时再次校验。`local_only` 不进入 Provider payload，
`remote_model` 需要用户显式选择，且模型配置必须声明 `supports_image_input = true`。

MCP 支持 stdio initialize、`tools/list` 分页和 `tools/call`。服务默认 `enabled = false`；
启用表示允许启动该本地进程做发现，不代表自动允许工具调用。工具名映射为
`mcp__<server>__<tool>`，allow 后 deny，参数按服务 Schema 验证。未知工具默认高风险、非只读、
必须审批；可信预设可在本地配置逐工具 `read_only`、风险和审批策略，服务端 annotation 不能降低
本地风险。子进程只获得基础安全环境与 `env_keys` 显式列出的变量。

桌面“工具与连接”提供固定版本的 Brave Search MCP 预设，只暴露网页搜索、新闻搜索与 LLM 上下文
搜索。`BRAVE_API_KEY` 优先从进程环境读取，否则从系统钥匙串读取；保存的托管配置只包含命令、允许
工具和环境变量名。首次网络调用仍需要审批，可选择仅本次或本会话允许。未配置真实 Key 时可以保存
配置，但不能完成在线搜索。

自定义 stdio MCP 只接受进程参数和环境变量名，不在配置中保存密钥值。可在 TOML 中逐工具声明：

```toml
[mcp_servers.docs]
command = ["node", "server.js"]
enabled = true
enabled_tools = ["search"]
env_keys = ["DOCS_API_KEY"]

[mcp_servers.docs.tool_overrides.search]
read_only = true
risk_level = "medium"
always_approval = true
network = true
```

项目插件只从 `.yfh/plugins/*/plugin.json` 静态发现 schema version 1 manifest。状态始终是
`review_required`；仅列出 rules/skill/command/MCP/Hook 能力和请求权限，不加载代码、
不启动进程、不自动授权。

## 可选并行研究边界

首版不在同一工作区并发运行多个写入 Agent。未来研究任务必须显式携带只读上下文快照、
独立会话与独立 worktree；不得共享隐式可变状态、审批缓存或未脱敏密钥。合并前按变更哈希
检查基线是否漂移，并统一进入现有 Diff、人工审批和测试门。只读研究结果可以回传文字证据，
写入结果不能直接覆盖主工作区，也不能把“子任务已完成”当作合并成功。
