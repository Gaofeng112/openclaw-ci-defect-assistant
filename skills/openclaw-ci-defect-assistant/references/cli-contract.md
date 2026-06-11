# CLI Contract

Command:

```powershell
.\.venv\Scripts\ci-defect-assistant.exe chat --user-id "<real_ding_user_id>" --conversation-id "<real_ding_conversation_id>" --text "<original_user_text>"
```

Output:

```json
{
  "reply": "send exactly this text",
  "result": {
    "code": "needs_confirmation"
  }
}
```

Rules:

- `reply` is the only user-visible response.
- `user-id` must be the real DingTalk sender id.
- In group chat, `conversation-id` must be `Conversation info.chat_id`.
- Confirmation must use the same `user-id`, same `conversation-id`, and text `确认`.
- Current supported actions are `jenkins.trigger`, `jenkins.query`, `bug.create`, and `bug.query`.
- Runtime state is under `runtime/audit`, `runtime/confirmations`, and `runtime/sessions`.
- Config comes from `configs/*.yaml` and `.env`; set `CI_DEFECT_ASSISTANT_HOME` when running outside the project root.
