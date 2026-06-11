import json
import sys
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.audit import find_latest, write_audit
from app.schemas import BugCreateRequest, BugCreateResponse, CiCommand, CiResult, JenkinsTriggerRequest, JenkinsTriggerResponse
from app.tools.jenkins_tool import trigger_job
from app.tools.teambition_tool import create_bug


def load_command(request_file: str | None = None, request_json: str | None = None) -> CiCommand:
    raw = Path(request_file).read_text(encoding="utf-8-sig") if request_file else request_json
    return CiCommand.model_validate_json(raw)


def execute(command: CiCommand) -> CiResult:
    if command.action == "bug.create":
        return _bug_result(command, create_bug(BugCreateRequest(
            user_id=command.user_id,
            conversation_id=command.conversation_id,
            text=command.text,
            fields=command.params,
            source=command.source,
            confirmed=command.confirmed,
            confirm_token=command.confirm_token,
        )))
    if command.action == "jenkins.query":
        return _query_result(command, "jenkins.trigger", "没有找到最近的 Jenkins 执行记录")
    if command.action == "bug.query":
        return _query_result(command, "bug.create", "没有找到最近的 bug 创建记录", {"created"})
    if command.action != "jenkins.trigger":
        return CiResult(request_id=command.request_id, conversation_id=command.conversation_id, success=False, code="invalid_action", message=f"不支持的 action: {command.action}")
    if not command.job:
        return CiResult(success=False, code="invalid_request", message="job is required for jenkins.trigger")
    response = trigger_job(JenkinsTriggerRequest(
        user_id=command.user_id,
        conversation_id=command.conversation_id,
        job=command.job,
        env=_string_param(command.params, "env"),
        branch=_string_param(command.params, "branch"),
        parameters={key: value for key, value in command.params.items() if key not in {"env", "branch"}},
        confirmed=command.confirmed,
        confirm_token=command.confirm_token,
        wait_result=command.wait_result,
    ))
    return _result(command, response)


def print_result(result: CiResult) -> None:
    sys.stdout.buffer.write(json.dumps(result.model_dump(exclude_none=True), ensure_ascii=False).encode("utf-8"))
    sys.stdout.buffer.write(b"\n")


def run_request(request_file: str | None = None, request_json: str | None = None) -> int:
    command = None
    try:
        command = load_command(request_file, request_json)
        result = execute(command)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        result = CiResult(success=False, code="invalid_request", message=str(exc))
    if command:
        write_audit(command, result)
    print_result(result)
    return 0


def _string_param(params: dict[str, Any], name: str) -> str | None:
    value = params.get(name)
    return None if value in (None, "") else str(value)


def _result(command: CiCommand, response: JenkinsTriggerResponse) -> CiResult:
    return CiResult(
        request_id=command.request_id,
        conversation_id=command.conversation_id,
        success=response.success,
        code=response.code,
        message=response.message,
        job=command.job,
        params=command.params,
        needs_confirmation=response.needs_confirmation,
        confirm_token=response.confirm_token,
        expires_in_seconds=response.expires_in_seconds,
        preview=response.preview,
        build_number=response.build_number,
        build_url=response.build_url,
        build_status=response.build_status,
        duration_seconds=response.duration_seconds,
        summary=response.summary,
    )


def _bug_result(command: CiCommand, response: BugCreateResponse) -> CiResult:
    return CiResult(
        request_id=command.request_id,
        conversation_id=command.conversation_id,
        success=response.success,
        code=response.code,
        message=response.message,
        params=response.fields,
        bug_url=response.bug_url,
        task_id=response.task_id,
        missing_fields=response.missing_fields,
        extracted=response.fields,
        needs_confirmation=response.needs_confirmation,
        confirm_token=response.confirm_token,
        expires_in_seconds=response.expires_in_seconds,
        preview=response.preview,
    )


def _query_result(command: CiCommand, target_action: str, not_found_message: str, codes: set[str] | None = None) -> CiResult:
    item = find_latest(target_action, command.conversation_id, command.user_id, codes)
    if not item:
        return CiResult(request_id=command.request_id, conversation_id=command.conversation_id, success=False, code="not_found", message=not_found_message)
    if target_action == "jenkins.trigger":
        return CiResult(request_id=command.request_id, conversation_id=command.conversation_id, success=True, code="query_result", message=_jenkins_query_message(item), job=item.get("job"), params=item.get("params") or {}, build_url=item.get("external_url"), build_status=item.get("build_status"), summary=item.get("summary"))
    return CiResult(request_id=command.request_id, conversation_id=command.conversation_id, success=True, code="query_result", message=_bug_query_message(item), params=item.get("result_params") or {}, bug_url=item.get("external_url"), task_id=item.get("task_id"), extracted=item.get("result_params") or {})


def _jenkins_query_message(item: dict[str, Any]) -> str:
    suffix = "" if item.get("external_url") else "，暂无链接"
    return f"最近一次 Jenkins 记录：{item.get('code')}{suffix}"


def _bug_query_message(item: dict[str, Any]) -> str:
    suffix = "" if item.get("external_url") else "，暂无链接"
    return f"最近一次 bug 创建记录已找到{suffix}"
