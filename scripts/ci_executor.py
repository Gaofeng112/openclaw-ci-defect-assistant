import argparse
import json
import sys
from pathlib import Path
from typing import Any

from pydantic import ValidationError

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.schemas import BugCreateRequest, BugCreateResponse, CiCommand, CiResult, JenkinsTriggerRequest, JenkinsTriggerResponse
from app.tools.jenkins_tool import trigger_job
from app.tools.teambition_tool import create_bug


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--request-file")
    source.add_argument("--request-json")
    return parser.parse_args()


def load_command(args: argparse.Namespace) -> CiCommand:
    raw = Path(args.request_file).read_text(encoding="utf-8-sig") if args.request_file else args.request_json
    return CiCommand.model_validate_json(raw)


def execute(command: CiCommand) -> CiResult:
    if command.action == "bug.create":
        return _bug_result(command, create_bug(BugCreateRequest(
            user_id=command.user_id,
            conversation_id=command.conversation_id,
            text=command.text,
            fields=command.params,
        )))
    if not command.job:
        return CiResult(success=False, code="invalid_request", message="job is required for jenkins.trigger")
    response = trigger_job(
        JenkinsTriggerRequest(
            user_id=command.user_id,
            job=command.job,
            env=_string_param(command.params, "env"),
            branch=_string_param(command.params, "branch"),
            parameters={key: value for key, value in command.params.items() if key not in {"env", "branch"}},
            confirmed=command.confirmed,
            wait_result=command.wait_result,
        )
    )
    return _result(command, response)


def _string_param(params: dict[str, Any], name: str) -> str | None:
    value = params.get(name)
    if value is None or value == "":
        return None
    return str(value)


def _result(command: CiCommand, response: JenkinsTriggerResponse) -> CiResult:
    return CiResult(
        request_id=command.request_id,
        conversation_id=command.conversation_id,
        success=response.success,
        code=_code(response),
        message=response.message,
        job=command.job,
        params=command.params,
        needs_confirmation=response.needs_confirmation,
        build_url=response.build_url,
        build_status=response.build_status,
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
    )


def _code(response: JenkinsTriggerResponse) -> str:
    if response.code:
        return response.code
    if response.needs_confirmation:
        return "needs_confirmation"
    if response.build_status:
        return "build_success" if response.build_status == "SUCCESS" else "build_finished"
    if response.success:
        return "triggered"
    return "failed"


def _error_result(exc: Exception) -> CiResult:
    return CiResult(success=False, code="invalid_request", message=str(exc))


def print_result(result: CiResult) -> None:
    payload = result.model_dump(exclude_none=True)
    sys.stdout.buffer.write(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
    sys.stdout.buffer.write(b"\n")


def main() -> int:
    try:
        result = execute(load_command(parse_args()))
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        result = _error_result(exc)
    print_result(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
