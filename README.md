# OpenClaw CI Tool

Minimal ChatOps + Tool/RPC executor for Jenkins tests.

```text
DingTalk -> OpenClaw semantic analysis -> JSON command file -> scripts/ci_executor.py -> Jenkins -> JSON result -> OpenClaw reply
```

OpenClaw owns natural-language understanding and user-facing replies. This project owns trusted execution: schema validation, whitelist checks, role checks, confirmation checks, Jenkins trigger, and optional result polling.

## Files

```text
scripts/ci_executor.py       JSON command executor used by OpenClaw
app/schemas.py               Command/result and Jenkins models
app/tools/jenkins_tool.py    Jenkins validation, trigger, and result polling
app/tools/teambition_tool.py Teambition bug creation
app/auth.py                  User-role checks
app/config.py                .env and YAML config loading
configs/jobs.yaml            Jenkins job whitelist
configs/users.yaml           User role mapping
```

## Request JSON

```json
{
  "request_id": "demo-001",
  "conversation_id": "36665056041252632",
  "user_id": "u001",
  "action": "jenkins.trigger",
  "job": "ci_test",
  "params": {
    "env": "test",
    "branch": "main"
  },
  "confirmed": false,
  "wait_result": false
}
```

## Run Locally

Write a request file, then run:

```powershell
.\.venv\Scripts\python.exe scripts\ci_executor.py --request-file runtime\requests\demo-001.json
```

The executor prints one JSON result to stdout:

```json
{
  "success": false,
  "code": "needs_confirmation",
  "message": "触发 Jenkins 前需要确认",
  "needs_confirmation": true,
  "confirm_token": "confirm_xxx",
  "expires_in_seconds": 300
}
```

Confirmation request:

```json
{
  "request_id": "demo-001-confirm",
  "conversation_id": "36665056041252632",
  "user_id": "u001",
  "action": "jenkins.trigger",
  "job": "ci_test",
  "params": {
    "env": "test",
    "branch": "main"
  },
  "confirmed": true,
  "confirm_token": "confirm_xxx",
  "wait_result": true
}
```

## Mock Test

Use `JENKINS_MOCK=1` to avoid triggering real Jenkins:

```powershell
$env:JENKINS_MOCK='1'
.\.venv\Scripts\python.exe scripts\ci_executor.py --request-file runtime\requests\demo-001.json
```

## OpenClaw Rule

For a DingTalk CI request, OpenClaw should:

1. Extract `job`, `env`, `branch`, `wait_result`, `conversation_id`, and `user_id`.
2. Write a JSON command file under `runtime/requests/`.
3. Execute `scripts/ci_executor.py --request-file <file>`.
4. Parse stdout JSON.
5. Reply to DingTalk from the structured result.

If DingTalk replies with generic text such as "which defect management system"
or "I do not have Teambition access", OpenClaw has not called this executor.
Configure the Tool Router with `docs/openclaw-tool-router-prompt.md`.

For DingTalk integration, prefer the wrapper command:

```powershell
.\.venv\Scripts\python.exe scripts\call_ci_assistant.py --user-id "{{ding_user_id}}" --conversation-id "{{ding_conversation_id}}" --text "{{original_user_text}}"
```

It returns JSON with a `reply` field that can be sent back to DingTalk directly.

The same wrapper also handles recent-result queries:

```powershell
.\.venv\Scripts\python.exe scripts\call_ci_assistant.py --user-id "{{ding_user_id}}" --conversation-id "{{ding_conversation_id}}" --text "刚才那个跑完了吗"
.\.venv\Scripts\python.exe scripts\call_ci_assistant.py --user-id "{{ding_user_id}}" --conversation-id "{{ding_conversation_id}}" --text "刚才创建的 bug 链接发我一下"
```

## Create Teambition Bug

OpenClaw can send natural-language bug creation requests to the same executor:

```json
{
  "request_id": "bug-001",
  "conversation_id": "36665056041252632",
  "user_id": "u001",
  "action": "bug.create",
  "text": "创建bug 标题：登录失败 模块：auth 环境：test 严重程度：P2 步骤：输入正确账号密码后点击登录 预期：进入首页 实际：提示500"
}
```

The executor validates required fields and saves partial fields by `conversation_id`.
If fields are missing, send a second request with the same `conversation_id`:

```json
{
  "request_id": "bug-001-fill",
  "conversation_id": "36665056041252632",
  "user_id": "u001",
  "action": "bug.create",
  "text": "预期：进入首页 实际：提示500"
}
```

Required bug fields:

```text
title, module, severity, env, steps, expected, actual
```

Teambition system IDs come from `configs/teambition.yaml`. OpenClaw should only pass
business fields in `params`; structured values override natural-language extraction.

OpenClaw is allowed to normalize or rewrite the structured command before calling
the local executor. Prefer sending confident fields in `params`; use the same
`conversation_id` when asking the user to fill missing fields. Do not ask again
for fields already available from the current conversation or from executor
defaults.

Teambition config:

```env
TEAMBITION_BASE_URL=https://open.teambition.com/api
TEAMBITION_APP_ID=your-app-id
TEAMBITION_APP_SECRET=your-app-secret
TEAMBITION_ORG_ID=your-org-id
TEAMBITION_OPERATOR_ID=your-user-id
```

```yaml
# configs/teambition.yaml
project_id: "tb_project_id"
bug_sfc_id: "tb_bug_sfc_id"
default_stage_id: "tb_stage_id"
default_tasklist_id: "tb_tasklist_id"
default_executor_id: "tb_user_default"
```
