# 高级 Agent 框架集成

YF-Harness 0.2 提供 LangChain、LlamaIndex 和 AutoGen 的真实、可选适配层。目标不是用框架替换核心
`AgentRunner`，而是让同一个项目能安全地比较和调用三种生态 Agent API，同时继续复用 Provider/Model 配置。

## 安装与发现

```bash
pip install 'yf-harness[frameworks]'
yfh frameworks list
yfh frameworks doctor
```

也可只安装 `yf-harness[langchain]`、`yf-harness[llamaindex]` 或 `yf-harness[autogen]`。默认安装不包含
这些 SDK；发现命令读取包元数据，不会提前导入框架。缺少依赖时，运行命令会明确显示对应 extra，而不会
静默换成另一个实现。

## CLI

```bash
# 完全离线；默认 mock/mock-default
yfh frameworks run langchain "解释 Agent Loop"
yfh frameworks run llamaindex "列出上下文压缩风险" --output json
yfh frameworks run autogen "拟定测试策略" --system "回答要简洁"

# 复用 examples/config.example.toml 形式的远程配置
yfh frameworks run langchain "你好" --provider deepseek --model deepseek_v4_flash
```

`--output json` 返回稳定字段：`framework`、`provider`、`model`、`text`、`duration`、`usage` 和
`metadata`。`usage.estimated=false` 表示框架响应暴露了实际 token 计数；离线或未暴露计数时会明确标记估算。

## Python API

```python
from yfharness.config.loader import load_config
from yfharness.integrations.frameworks import FrameworkName, FrameworkRequest, get_adapter

config = load_config()
request = FrameworkRequest(
    task="分析这份设计",
    provider=config.default_provider,
    model=config.default_model,
)
result = await get_adapter(FrameworkName.LANGCHAIN).run(request, config)
print(result.text)
```

三个适配器的远程映射如下：

| 适配器 | 原生 Agent | OpenAI-compatible 客户端 | 离线模型路径 |
|---|---|---|---|
| LangChain | `create_agent` | `ChatOpenAI` | `FakeListChatModel` |
| LlamaIndex | `ReActAgent` | `OpenAILike` | `CustomLLM` |
| AutoGen | `AssistantAgent` | `OpenAIChatCompletionClient` | `ChatCompletionClient` 实现 |

## 配置与密钥

适配器只接受 `AppConfig` 中已存在的 Provider 和 Model。模型必须属于所选 Provider；远程 `base_url`、
超时、重试和上下文窗口映射到框架客户端。`api_key_env` 只保存环境变量名称，密钥值在运行时读取。
没有 `api_key_env` 的本地兼容服务使用非敏感占位值满足 SDK 参数要求。

## 安全边界

框架 Agent 当前总是接收空工具集。这一点是有意设计：第三方执行循环不能直接操作文件、Shell 或 Git，
也不能绕过 YF-Harness 的模式策略、审批和 WorkspaceGuard。需要工具时使用 `yfh run`；不要把第三方
框架返回的文本当成已执行的操作。

## 测试

```bash
uv sync --extra dev --extra frameworks
uv run pytest -m frameworks
```

离线测试真实实例化三种 Agent。远程契约测试通过本地 HTTP mock 接收每套官方客户端发出的
`/chat/completions` 请求，并验证模型名、Bearer Header、响应文本与 token 用量映射，不需要真实 API Key。
