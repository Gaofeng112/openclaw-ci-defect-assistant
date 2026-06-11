---
name: openclaw-ci-defect-assistant
description: Use this skill when handling OpenClaw, DingTalk, Jenkins, CI, pipeline, Teambition, bug, defect, issue, confirmation, or recent-result requests for the openclaw-ci-defect-assistant project. It tells Codex to use the portable `ci-defect-assistant` CLI as the trusted executor instead of calling Jenkins or Teambition directly, simulating work, or rewriting wrapper output.
---

# OpenClaw CI Defect Assistant

Use the project CLI as the only execution path for Jenkins and Teambition ChatOps.

## Required Flow

1. Ensure the project is installed locally:

Windows:

```powershell
.\.venv\Scripts\python.exe -m pip install -e .
```

Mac / Linux:

```bash
./.venv/bin/python -m pip install -e .
```

2. Check local setup when starting a new machine or after config changes:

Windows:

```powershell
.\.venv\Scripts\ci-defect-assistant.exe doctor
```

Mac / Linux:

```bash
./.venv/bin/ci-defect-assistant doctor
```

3. For every DingTalk/OpenClaw Jenkins or Teambition message, call:

Windows:

```powershell
.\.venv\Scripts\ci-defect-assistant.exe chat --user-id "<real_ding_user_id>" --conversation-id "<real_ding_conversation_id>" --text "<original_user_text>"
```

Mac / Linux:

```bash
./.venv/bin/ci-defect-assistant chat --user-id "<real_ding_user_id>" --conversation-id "<real_ding_conversation_id>" --text "<original_user_text>"
```

4. Parse stdout as JSON and send exactly the `reply` value back to DingTalk. Do not prepend, append, translate, summarize, or reformat it.

## Confirmation

If the CLI result contains `result.code = "needs_confirmation"`, send `reply` and wait.

When the same user replies only `确认`, call the CLI again with the same real `user_id` and `conversation_id`:

Windows:

```powershell
.\.venv\Scripts\ci-defect-assistant.exe chat --user-id "<same_user_id>" --conversation-id "<same_conversation_id>" --text "确认"
```

Mac / Linux:

```bash
./.venv/bin/ci-defect-assistant chat --user-id "<same_user_id>" --conversation-id "<same_conversation_id>" --text "确认"
```

Do not construct confirmation JSON manually. The CLI owns token lookup, user binding, conversation binding, and request matching.

## Query

For follow-up text such as `刚才跑完了吗`, `结果呢`, `链接发我`, `状态怎么样`, or `刚才创建的 bug 链接`, call the CLI again with the original current text.

Do not answer from memory or previous tool output. Query lookup is part of the CLI.

## Boundaries

- Do not call Jenkins directly.
- Do not call Teambition directly.
- Do not use curl, `Invoke-RestMethod`, ad-hoc JSON posts, or fake echo output for Jenkins/TB work.
- Do not run `scripts/ci_executor.py` for normal chat handling; use `ci-defect-assistant chat`.
- Keep scripts as compatibility entrypoints only.
- For group chat, use `Conversation info.chat_id` as `conversation_id`, not sender id or group label.

## Local Paths

The project path is the directory where this repository is cloned.

Example Windows path:

```text
C:\2_PROJECT\proj\openclaw-ci-defect-assistant
```

Example Mac / Linux path:

```text
/opt/openclaw-ci-defect-assistant
```

When running from another directory, set:

Windows:

```powershell
$env:CI_DEFECT_ASSISTANT_HOME="C:\2_PROJECT\proj\openclaw-ci-defect-assistant"
```

Mac / Linux:

```bash
export CI_DEFECT_ASSISTANT_HOME="/opt/openclaw-ci-defect-assistant"
```

Read [references/cli-contract.md](references/cli-contract.md) only when you need exact CLI contract details for packaging, plugin work, or OpenClaw prompt updates.
