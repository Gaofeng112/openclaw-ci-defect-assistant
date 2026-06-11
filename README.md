# OpenClaw CI Defect Assistant

Portable CLI for OpenClaw/DingTalk ChatOps:

```text
DingTalk -> OpenClaw -> ci-defect-assistant -> Jenkins / Teambition -> JSON reply
```

OpenClaw handles natural language. This project handles trusted execution: permission checks, confirmation tokens, Jenkins triggering, Teambition bug creation, audit logs, and query lookup.

## Install

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
```

Optional helpers:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[browser,dingtalk]"
```

## Initialize

```powershell
ci-defect-assistant init
ci-defect-assistant doctor
```

`init` creates local `runtime/` folders and copies `.env.example` to `.env` when `.env` does not exist.

To run from another directory, set:

```powershell
$env:CI_DEFECT_ASSISTANT_HOME="C:\path\to\openclaw-ci-defect-assistant"
```

## Chat Entry

Use this command from OpenClaw:

```powershell
ci-defect-assistant chat --user-id "{{ding_user_id}}" --conversation-id "{{ding_conversation_id}}" --text "{{original_user_text}}"
```

It prints JSON:

```json
{
  "reply": "send this text back to DingTalk",
  "result": {}
}
```

For existing OpenClaw configs, the old script path still works:

```powershell
.\.venv\Scripts\python.exe scripts\call_ci_assistant.py --user-id "{{ding_user_id}}" --conversation-id "{{ding_conversation_id}}" --text "{{original_user_text}}"
```

## Examples

Jenkins:

```powershell
$env:JENKINS_MOCK='1'
ci-defect-assistant chat --user-id u001 --conversation-id demo --text "执行 ci_test 环境 test 分支 develop"
ci-defect-assistant chat --user-id u001 --conversation-id demo --text "确认"
```

Teambition:

```powershell
ci-defect-assistant chat --user-id u001 --conversation-id bug-demo --text "创建缺陷 title: 登录失败 description: 点击保存后无响应"
```

The first real Teambition call stops at confirmation. Creation only happens after the same user replies `确认` in the same conversation.

## Config

Required config files:

```text
configs/jobs.yaml
configs/users.yaml
configs/teambition.yaml
configs/teambition_bug_form.v1.yaml
.env
```

Runtime files are local and ignored by git:

```text
runtime/audit/
runtime/confirmations/
runtime/sessions/
runtime/teambition_har/
```

Teambition web headers are read from:

```text
runtime/teambition_har/teambition_headers.json
```

Teambition field evidence is read from:

```text
runtime/teambition_har/teambition_v4.teambition-fields.json
```

Use `scripts/save_teambition_cookie.py` and `scripts/extract_teambition_har.py` only when refreshing local Teambition evidence.
