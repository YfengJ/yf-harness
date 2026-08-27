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

MCP 首版支持 stdio initialize、`tools/list` 分页和 `tools/call`。服务默认 `enabled = false`；
启用表示允许启动该本地进程做发现，不代表自动允许工具调用。工具名映射为
`mcp__<server>__<tool>`，allow 后 deny，参数按服务 Schema 验证，所有工具都按高风险、
非只读、必须审批处理。服务声明的 annotation 不能降低本地风险；子进程只获得
基础安全环境与 `env_keys` 显式列出的变量。

项目插件只从 `.yfh/plugins/*/plugin.json` 静态发现 schema version 1 manifest。状态始终是
`review_required`；仅列出 rules/skill/command/MCP/Hook 能力和请求权限，不加载代码、
不启动进程、不自动授权。

## 可选并行研究边界

首版不在同一工作区并发运行多个写入 Agent。未来研究任务必须显式携带只读上下文快照、
独立会话与独立 worktree；不得共享隐式可变状态、审批缓存或未脱敏密钥。合并前按变更哈希
检查基线是否漂移，并统一进入现有 Diff、人工审批和测试门。只读研究结果可以回传文字证据，
写入结果不能直接覆盖主工作区，也不能把“子任务已完成”当作合并成功。
