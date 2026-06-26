from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import subprocess
from pathlib import Path
from typing import Optional

from plugins.platforms.dingtalk.adapter import (
    DingTalkAdapter,
    _apply_yaml_config,
    _is_connected,
    _standalone_send,
    check_dingtalk_requirements,
    interactive_setup,
)

logger = logging.getLogger(__name__)


class CiDefectDingTalkAdapter(DingTalkAdapter):
    async def handle_message(self, event) -> None:
        text = event.text or ""
        if not _matches_ci_defect_assistant(text):
            await super().handle_message(event)
            return

        chat_id = event.source.chat_id
        user_id = event.source.user_id_alt or event.source.user_id
        reply = await _run_ci_defect_assistant(text, chat_id, user_id)
        if reply:
            await self.send(chat_id, _dingtalk_markdown_newlines(reply), reply_to=event.message_id)


def _matches_ci_defect_assistant(text: str) -> bool:
    lowered = text.lower()
    return (
        ("确认" in text and re.search(r"[0-9a-fA-F]{6}", text))
        or "tb缺陷" in lowered
        or "teambition" in lowered
        or "提bug" in lowered
        or "提个bug" in lowered
        or ("缺陷" in text and any(word in text for word in ("创建", "新建", "提交", "提")))
    )


async def _run_ci_defect_assistant(text: str, chat_id: str, user_id: str) -> Optional[str]:
    root = Path(os.environ.get("CI_DEFECT_ASSISTANT_ROOT", "")).expanduser()
    python = root / ".venv" / "Scripts" / "python.exe"
    if not python.exists():
        logger.warning("CI Defect Assistant python not found: %s", python)
        return "未找到 CI Defect Assistant 虚拟环境，请检查 CI_DEFECT_ASSISTANT_ROOT。"

    def _run() -> str:
        env = {**os.environ, "CI_DEFECT_ASSISTANT_HOME": str(root)}
        for key in ("PYTHONHOME", "PYTHONPATH", "VIRTUAL_ENV", "__PYVENV_LAUNCHER__"):
            env.pop(key, None)
        env["PATH"] = str(python.parent) + os.pathsep + env.get("PATH", "")
        cp = subprocess.run(
            [
                str(python),
                "-m",
                "app.cli",
                "chat",
                "--user-id",
                user_id,
                "--conversation-id",
                chat_id,
                "--text",
                text,
            ],
            cwd=str(root),
            env=env,
            text=True,
            encoding="utf-8",
            capture_output=True,
            timeout=60,
        )
        output = cp.stdout if cp.returncode == 0 else (cp.stderr or cp.stdout)
        try:
            data = json.loads(output)
            return str(data.get("reply") or output).strip()
        except json.JSONDecodeError:
            return output.strip()

    return await asyncio.to_thread(_run)


def _dingtalk_markdown_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\n", "  \n")


def _build_adapter(config):
    return CiDefectDingTalkAdapter(config)


def register(ctx) -> None:
    ctx.register_platform(
        name="dingtalk",
        label="DingTalk",
        adapter_factory=_build_adapter,
        check_fn=check_dingtalk_requirements,
        is_connected=_is_connected,
        validate_config=_is_connected,
        required_env=["DINGTALK_CLIENT_ID", "DINGTALK_CLIENT_SECRET"],
        install_hint="pip install 'dingtalk-stream>=0.20' httpx",
        setup_fn=interactive_setup,
        apply_yaml_config_fn=_apply_yaml_config,
        allowed_users_env="DINGTALK_ALLOWED_USERS",
        allow_all_env="DINGTALK_ALLOW_ALL_USERS",
        cron_deliver_env_var="DINGTALK_HOME_CHANNEL",
        standalone_sender_fn=_standalone_send,
        emoji="DT",
        allow_update_command=True,
    )
