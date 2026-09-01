# 截图维护

`desktop-app.png` 由真实的 `YF-Harness.app` 渲染，不是手绘稿。重新生成时运行：

```bash
open -W dist/YF-Harness.app --args --screenshot "$PWD/docs/images/desktop-app.png" --preview-tab 0
```

截图模式使用虚构会话和匿名 workspace。不要提交用户名、主机名、API Key、绝对私人路径或真实历史。
TUI 截图如需维护，使用 MockProvider 并遵循同一脱敏规则。
