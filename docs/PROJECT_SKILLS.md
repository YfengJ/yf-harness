# 项目技能

YF-Harness 0.6 把 Codex、Claude Code、Cursor 的项目级可复用流程统一成一个显式技能入口。技能与
`AGENTS.md` 等常驻规则不同：列表只暴露名称、说明、来源和警告，完整正文只在用户选择后加入当次请求。

## 发现位置

按固定顺序扫描工作区内 `.yfh/skills/*/SKILL.md`、`.agents/skills/*/SKILL.md`、
`.claude/skills/*/SKILL.md`、`.claude/commands/*.md` 和 `.cursor/commands/*.md`。不读取用户主目录，
不跟随目录或文件符号链接；非 UTF-8、二进制、超过 128 KiB 或名称不合法的条目会被忽略。

公开 ID 是 `source:name`。裸名称只有在所有来源中唯一时可用；同名时必须明确选择命名空间，避免
一个工具的配置静默覆盖另一个工具。

## 调用

桌面输入 `$` 后选择技能并继续输入任务参数，例如：

```text
$codex:review-changes 检查当前修改是否遗漏测试
```

CLI 和兼容 TUI：

```bash
yfh skills list
yfh skills show codex:review-changes
yfh run --skill codex:review-changes "检查当前修改"
# TUI: /skills 或 /skill codex:review-changes 检查当前修改
```

兼容 `$ARGUMENTS`、`${ARGUMENTS}` 和 `$1` 至 `$9` 的纯文本替换。替换不会调用 Shell，也不会解析
命令替换语法。

## 安全边界

- Skill 内容视为工作区不可信指令，不能覆盖系统提示、模式、Workflow、Policy 或审批结果。
- `allowed-tools` 只作为兼容元数据展示，不能让未暴露或被拒绝的工具变得可执行。
- `scripts`、`assets` 等附带资源不会自动读取或执行；界面只显示警告。
- 会话保存原始用户消息；系统消息不写入消息历史。Context Trace 只保存来源与 Token 元数据，不保存
  完整技能正文、附件或模型请求消息。
- 这是显式调用的第一版，不做模型自动选择技能，避免含糊描述触发高影响流程。

仓库自带 `review-changes` 和 `prepare-release` 两个短小示例。新增技能应保持描述可区分、正文聚焦，
需要外部副作用时仍必须走 YF-Harness 原有审批链。
