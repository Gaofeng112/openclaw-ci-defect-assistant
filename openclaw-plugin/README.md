# OpenClaw CI Defect Assistant

OpenClaw tool plugin that exposes one tool:

```text
ci_defect_assistant_chat
```

The tool forwards `user_id`, `conversation_id`, and `text` to:

```text
ci-defect-assistant chat
```

The Python CLI remains the trusted executor. This plugin only bridges OpenClaw to that CLI.

## Build And Validate

```bash
npm install
npm run plugin:build
npm run plugin:validate
npm test
```

## Install Locally

This plugin uses `child_process` to call the trusted Python CLI, so OpenClaw blocks it unless installation is explicitly forced.

```powershell
openclaw plugins install --link .\openclaw-plugin --dangerously-force-unsafe-install
openclaw gateway restart
openclaw plugins inspect openclaw-ci-defect-assistant
openclaw plugins doctor
```

## Config

```json
{
  "projectRoot": "C:\\2_PROJECT\\proj\\openclaw-ci-defect-assistant",
  "command": "ci-defect-assistant"
}
```
