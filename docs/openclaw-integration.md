# OpenClaw 接入方案

## 推荐接入方式

先不要让 OpenClaw 直接调用 Jenkins。推荐链路：

```text
用户自然语言
  -> OpenClaw Agent
  -> FastAPI 工具服务 /assistant/chat
  -> 白名单/权限/会话补全/二次确认
  -> Jenkins
```

这样 Jenkins 的安全边界仍然在后端工具服务里，OpenClaw 只负责理解用户消息和转发工具调用。

## 工具接口

给 OpenClaw 暴露一个工具即可：

```text
call_ci_assistant
```

用途：

```text
把用户在聊天中的自然语言请求发送给 CI 助手服务，返回可直接回复给用户的文本。
```

参数：

```json
{
  "user_id": "u001",
  "conversation_id": "ding-group-001",
  "text": "帮我执行 ci_test，环境 test，分支 main"
}
```

HTTP 调用：

```text
POST http://127.0.0.1:8000/assistant/chat
```

请求体：

```json
{
  "user_id": "{{user_id}}",
  "conversation_id": "{{conversation_id}}",
  "text": "{{text}}"
}
```

响应示例：

```json
{
  "success": false,
  "reply": "已识别任务 ci_test，环境 test，分支 main。请回复“确认”后触发 Jenkins。",
  "conversation_id": "ding-group-001",
  "extracted": {
    "job": "ci_test",
    "env": "test",
    "branch": "main",
    "confirmed": false
  },
  "missing_fields": [],
  "build_url": null,
  "needs_confirmation": true
}
```

OpenClaw 收到响应后，把 `reply` 原样发给用户。

## OpenClaw Agent 提示词建议

```text
你是 CI 流水线测试助手。

规则：
1. 你不能直接访问 Jenkins。
2. 你不能编造 Jenkins job。
3. 用户要触发测试、执行流水线、跑 CI、跑自动化测试时，必须调用 call_ci_assistant。
4. call_ci_assistant 返回的 reply 是对用户的最终回复，优先原样返回。
5. 如果 reply 要求用户补充字段，你只需要把缺失字段告诉用户。
6. 如果 reply 要求确认，你必须等待用户明确回复“确认”后再继续调用工具。
7. 用户没有确认前，不得触发 Jenkins。
```

## 多轮对话示例

第一轮：

```text
用户：帮我跑一下测试
OpenClaw 调用 call_ci_assistant
助手回复：缺少 job, env, branch，请补充。
```

第二轮：

```text
用户：ci_test，环境 test，分支 main
OpenClaw 调用 call_ci_assistant
助手回复：已识别任务 ci_test，环境 test，分支 main。请回复“确认”后触发 Jenkins。
```

第三轮：

```text
用户：确认
OpenClaw 调用 call_ci_assistant
助手回复：已触发 Jenkins 任务，地址：http://jenkins8090.yaozh.com:8090/queue/item/xxxx/
```

## 后续增强

第一阶段先用 `call_ci_assistant` 统一入口，保证演示闭环。

后续可以再拆成两个结构化工具：

```text
trigger_jenkins_job
create_teambition_bug
```

拆分后，OpenClaw 负责参数抽取，后端继续负责白名单、权限、确认和审计。
