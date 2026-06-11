# OpenClaw CI Defect Assistant

这是一个给 OpenClaw / 钉钉使用的 CI 与缺陷助手。

流程：

```text
钉钉 -> OpenClaw -> ci-defect-assistant -> Jenkins / Teambition -> JSON 回复
```

OpenClaw 负责理解用户意图。本项目负责真正执行：权限检查、确认、Jenkins、Teambition、审计日志和结果查询。

## 最小安装

在项目根目录执行：

```powershell
.\scripts\install.ps1
```

说明：插件会调用本地 CLI，所以 OpenClaw 会要求使用 `--dangerously-force-unsafe-install` 明确确认。

只检查 CLI 和插件、不安装到 OpenClaw：

```powershell
.\scripts\install.ps1 -SkipOpenClawInstall
```

## OpenClaw 工具

插件暴露的工具名：

```text
ci_defect_assistant_chat
```

参数：

```text
user_id: "{{ding_user_id}}"
conversation_id: "{{ding_conversation_id}}"
text: "{{original_user_text}}"
```

规则：

- `user_id` 使用真实钉钉发送人 ID。
- `conversation_id` 使用真实会话 ID。群聊必须用 `Conversation info.chat_id`。
- `text` 传当前用户原文。
- 工具返回后，只把 JSON 里的 `reply` 字段发回钉钉。
- 不要直接调用 Jenkins 或 Teambition。

## CLI 单独验证

Jenkins mock：

```powershell
$env:JENKINS_MOCK='1'
ci-defect-assistant chat --user-id u001 --conversation-id demo --text "执行 ci_test 环境 test 分支 develop"
ci-defect-assistant chat --user-id u001 --conversation-id demo --text "确认"
```

Teambition 预览：

```powershell
ci-defect-assistant chat --user-id u001 --conversation-id bug-demo --text "创建缺陷 title: 登录失败 description: 点击保存后无响应"
```

真实 Teambition 创建会先停在确认步骤。只有同一个用户在同一个会话里回复 `确认` 后，才会真正创建。

## 必要配置

```text
configs/jobs.yaml
configs/users.yaml
configs/teambition.yaml
configs/teambition_bug_form.v1.yaml
.env
```

本地运行文件不会提交到 git：

```text
runtime/audit/
runtime/confirmations/
runtime/sessions/
runtime/teambition_har/
```

如果从其它目录运行 CLI，可以设置：

```powershell
$env:CI_DEFECT_ASSISTANT_HOME="D:\path\to\openclaw-ci-defect-assistant"
```
