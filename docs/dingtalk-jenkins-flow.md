# DingTalk Jenkins Natural Language Flow

## 推荐接入方式

如果你已经让 OpenClaw 连接了钉钉，推荐让 OpenClaw 在识别到 CI/Jenkins/测试意图时调用：

```text
POST http://127.0.0.1:8000/assistant/chat
```

请求体：

```json
{
  "user_id": "u001",
  "conversation_id": "ding-group-001",
  "text": "帮我跑一下 Jenkins 测试，环境 test，分支 main"
}
```

返回体里的 `reply` 可以直接发回钉钉群。

## 直接接钉钉回调

如果钉钉机器人直接回调本服务，使用：

```text
POST http://127.0.0.1:8000/callbacks/dingtalk
```

兼容的钉钉消息格式：

```json
{
  "senderId": "ding-user-id",
  "conversationId": "ding-group-001",
  "msgtype": "text",
  "text": {
    "content": "帮我执行 ci_test 环境 test 分支 main"
  }
}
```

服务返回：

```json
{
  "msgtype": "text",
  "text": {
    "content": "已识别任务 ci_test，环境 test，分支 main。请回复“确认”后触发 Jenkins。"
  }
}
```

用户回复：

```text
确认
```

同一个 `conversationId` 下会复用上一轮提取出的 `job/env/branch`，确认后才会触发 Jenkins。

## 当前支持的自然语言

```text
帮我跑一下 Jenkins 测试，环境 test，分支 main
执行 ci_test env test branch main
跑自动化测试，测试环境，分支 main
确认
```

当前 `configs/jobs.yaml` 只有一个 Jenkins job 时，如果用户只说“跑测试”，系统会默认选择这个 job。

## 用户映射

钉钉的 `senderId` 通常不是本系统的 `user_id`。当前实现会：

1. 如果 `senderStaffId` 或 `senderId` 正好存在于 `configs/users.yaml`，直接使用它。
2. 否则使用 `.env` 里的 `DINGTALK_DEFAULT_USER_ID`，默认是 `u001`。

演示阶段可以用默认映射。正式使用时建议把钉钉用户 ID 明确映射到本系统用户和角色。
