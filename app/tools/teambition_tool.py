import hashlib
import json
import time
from datetime import datetime, timedelta, timezone
from os import getenv
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx

from app.auth import can_create_bug
from app.config import BASE_DIR, teambition_bug_form_config, teambition_settings
from app.confirmation_store import CONFIRM_TTL_SECONDS, consume_confirmation, create_confirmation, find_pending_confirmation as find_pending
from app.nlp import extract_bug_fields
from app.schemas import BugCreateRequest, BugCreateResponse
from app.session_store import clear_fields, load_fields, save_fields
from app.tools.teambition_payload import build_v2_task_payload, load_evidence


ACTION = "bug.create"
EVIDENCE_PATH = Path(getenv("TEAMBITION_EVIDENCE_PATH", str(BASE_DIR / "runtime" / "teambition_har" / "teambition_v4.teambition-fields.json")))
HEADERS_PATH = Path(getenv("TEAMBITION_HEADERS_PATH", str(BASE_DIR / "runtime" / "teambition_har" / "teambition_headers.json")))
TASK_CREATE_URL = "https://www.teambition.com/api/v2/tasks"
REQUIRED_FIELDS = [
    "title",
    "description",
    "sprint",
]
DEFAULTS = {
    "priority": 0,
    "bug_or_legacy": "BUG",
    "service_org": "集团公司",
    "related_product": "药智数据企业版",
    "related_project": "无",
}
SYSTEM_FIELDS = {"project_id", "tasklist_id", "stage_id", "taskflowstatus_id", "sfc_id"}


def create_bug(request: BugCreateRequest) -> BugCreateResponse:
    if not can_create_bug(request.user_id):
        return BugCreateResponse(success=False, code="unauthorized", message="无权限创建缺陷")

    fields = _merged_fields(request)
    missing = [name for name in REQUIRED_FIELDS if _is_missing(fields.get(name))]
    if missing:
        save_fields(ACTION, request.conversation_id, _public_fields(fields))
        return BugCreateResponse(
            success=False,
            code="missing_fields",
            message=f"缺少 {', '.join(missing)}，请补充后继续。",
            missing_fields=missing,
            fields=_public_fields(fields),
        )

    if _mock_enabled():
        return _mock_response(request, fields)

    payload, payload_error = _payload_for_fields(fields)
    if payload_error:
        save_fields(ACTION, request.conversation_id, _public_fields(fields))
        return payload_error

    if not request.confirmed:
        token = _create_confirmation(request, fields)
        save_fields(ACTION, request.conversation_id, _public_fields(fields))
        return BugCreateResponse(
            success=False,
            code="needs_confirmation",
            message="创建 Teambition 缺陷前需要确认",
            fields=_public_fields(fields),
            needs_confirmation=True,
            confirm_token=token,
            expires_in_seconds=CONFIRM_TTL_SECONDS,
            preview=_preview(fields, payload),
        )

    confirm_error = _consume_confirmation(request, fields)
    if confirm_error:
        return confirm_error

    response = _submit_task(fields, payload)
    if response.success:
        clear_fields(ACTION, request.conversation_id)
    else:
        save_fields(ACTION, request.conversation_id, _public_fields(fields))
    return response


def _merged_fields(request: BugCreateRequest) -> dict[str, Any]:
    settings = teambition_settings()
    fields = DEFAULTS | {
        "project_id": settings["project_id"],
        "tasklist_id": settings["tasklist_id"],
        "stage_id": settings["stage_id"],
        "taskflowstatus_id": settings["taskflowstatus_id"],
        "sfc_id": settings["sfc_id"],
    }
    fields |= _default_business_fields()
    text_fields = extract_bug_fields(request.text, request.fields)
    saved_fields = {} if _is_new_bug_request(text_fields) else load_fields(ACTION, request.conversation_id)
    fields |= saved_fields
    fields |= text_fields
    if text_fields.get("environment") and saved_fields.get("environment") and text_fields["environment"] != saved_fields["environment"]:
        fields.pop("sprint", None)
    fields = _apply_environment_rules(fields)
    fields = _apply_runtime_defaults(fields)
    return {key: value for key, value in fields.items() if value not in (None, "")}


def _is_new_bug_request(fields: dict[str, Any]) -> bool:
    return bool(fields.get("title"))


def _mock_enabled() -> bool:
    return getenv("TEAMBITION_MOCK") == "1"


def _mock_response(request: BugCreateRequest, fields: dict[str, Any]) -> BugCreateResponse:
    task_id = f"mock-{int(time.time())}"
    clear_fields(ACTION, request.conversation_id)
    return BugCreateResponse(
        success=True,
        code="created",
        message=f"已模拟创建 Teambition 缺陷：{fields['title']}",
        bug_url=f"http://fake-teambition/task/{task_id}",
        task_id=task_id,
        fields=_public_fields(fields),
    )


def _payload_for_fields(fields: dict[str, Any]) -> tuple[dict[str, Any] | None, BugCreateResponse | None]:
    if not EVIDENCE_PATH.exists():
        return None, BugCreateResponse(
            success=False,
            code="missing_config",
            message=f"缺少 Teambition evidence 文件: {EVIDENCE_PATH}",
            fields=_public_fields(fields),
        )
    try:
        payload = build_v2_task_payload(fields, load_evidence(EVIDENCE_PATH))
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        return None, BugCreateResponse(
            success=False,
            code="invalid_config",
            message=f"Teambition payload 构建失败: {exc}",
            fields=_public_fields(fields),
        )
    return payload, None


def _submit_task(fields: dict[str, Any], payload: dict[str, Any]) -> BugCreateResponse:
    headers, header_error = _load_headers(fields)
    if header_error:
        return header_error

    try:
        with httpx.Client(timeout=30, follow_redirects=False, trust_env=False) as client:
            response = client.post(TASK_CREATE_URL, headers=headers, json=payload)
            data = _response_json(response)
    except httpx.HTTPError as exc:
        return BugCreateResponse(
            success=False,
            code="teambition_connection_failed",
            message=f"Teambition 连接失败: {exc}",
            fields=_public_fields(fields),
        )

    if not 200 <= response.status_code < 300:
        return BugCreateResponse(
            success=False,
            code="teambition_error",
            message=_error_message(data, response.status_code),
            fields=_public_fields(fields),
        )

    task_id = _task_id(data)
    project_id = _project_id(data, payload, fields)
    return BugCreateResponse(
        success=True,
        code="created",
        message=f"已创建 Teambition 缺陷：{fields['title']}",
        bug_url=_task_url(project_id, task_id),
        task_id=task_id,
        fields=_response_fields(fields, payload),
    )


def _load_headers(fields: dict[str, Any]) -> tuple[dict[str, str] | None, BugCreateResponse | None]:
    if not HEADERS_PATH.exists():
        return None, BugCreateResponse(
            success=False,
            code="missing_config",
            message=f"缺少 Teambition headers 文件: {HEADERS_PATH}",
            fields=_public_fields(fields),
        )
    try:
        raw = json.loads(HEADERS_PATH.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        return None, BugCreateResponse(
            success=False,
            code="invalid_config",
            message=f"Teambition headers 读取失败: {exc}",
            fields=_public_fields(fields),
        )
    if not isinstance(raw, dict):
        return None, BugCreateResponse(
            success=False,
            code="invalid_config",
            message="Teambition headers 文件格式不正确",
            fields=_public_fields(fields),
        )
    headers = {str(key): str(value) for key, value in raw.items() if value not in (None, "")}
    lowered = {key.lower() for key in headers}
    if "cookie" not in lowered and "authorization" not in lowered:
        return None, BugCreateResponse(
            success=False,
            code="missing_auth_header",
            message="缺少 Teambition 登录态，请先更新本地 Cookie",
            fields=_public_fields(fields),
        )
    headers["Content-Type"] = "application/json"
    headers.setdefault("x-request-id", uuid4().hex)
    return headers, None


def _preview(fields: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "action": ACTION,
        "title": fields["title"],
        "executor": fields.get("executor"),
        "severity": fields.get("severity"),
        "priority": payload.get("priority"),
        "sprint": fields.get("sprint"),
        "start_time": fields.get("start_time"),
        "due_time": fields.get("due_time"),
        "project_id": payload.get("_projectId"),
        "tasklist_id": payload.get("_tasklistId"),
        "customfields_count": len(payload.get("customfields") or []),
        "display": _display_fields(fields, payload),
    }


def _request_hash(request: BugCreateRequest, fields: dict[str, Any]) -> str:
    payload = {
        "user_id": request.user_id,
        "conversation_id": request.conversation_id,
        "fields": _public_fields(fields),
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _create_confirmation(request: BugCreateRequest, fields: dict[str, Any]) -> str:
    return create_confirmation(ACTION, {
        "action": ACTION,
        "request_hash": _request_hash(request, fields),
        "user_id": request.user_id,
        "conversation_id": request.conversation_id,
        "fields": _public_fields(fields),
    })


def _consume_confirmation(request: BugCreateRequest, fields: dict[str, Any]) -> BugCreateResponse | None:
    expected = {"user_id": request.user_id, "conversation_id": request.conversation_id, "request_hash": _request_hash(request, fields)}
    message = consume_confirmation(request.confirm_token, ACTION, expected)
    return BugCreateResponse(success=False, code="invalid_confirm_token", message=message, fields=_public_fields(fields)) if message else None


def find_pending_bug_confirmation(user_id: str, conversation_id: str | None) -> dict[str, Any] | None:
    return find_pending(ACTION, user_id, conversation_id)


def _response_json(response: httpx.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        return response.text[:1000]


def _error_message(data: Any, status_code: int) -> str:
    if isinstance(data, dict):
        for key in ["message", "errorMessage", "error", "code"]:
            value = data.get(key)
            if value:
                return f"Teambition 创建失败: {value}"
    return f"Teambition 创建失败: HTTP {status_code}"


def _task_id(data: Any) -> str | None:
    if isinstance(data, dict):
        return data.get("_id") or data.get("taskId") or data.get("id")
    return None


def _project_id(data: Any, payload: dict[str, Any], fields: dict[str, Any]) -> str | None:
    if isinstance(data, dict):
        project = data.get("project") or {}
        if isinstance(project, dict) and project.get("_id"):
            return str(project["_id"])
        if data.get("_projectId"):
            return str(data["_projectId"])
    return str(payload.get("_projectId") or fields.get("project_id") or "")


def _task_url(project_id: str | None, task_id: str | None) -> str | None:
    if project_id and task_id:
        return f"https://www.teambition.com/project/{project_id}/tasks/view/{task_id}"
    return f"https://www.teambition.com/task/{task_id}" if task_id else None


def _public_fields(fields: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in fields.items() if key not in SYSTEM_FIELDS}


def _response_fields(fields: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    result = _public_fields(fields)
    result["display"] = _display_fields(fields, payload)
    return result


def _display_fields(fields: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    form = teambition_bug_form_config()
    project = form.get("project") or {}
    return {
        "project": project.get("project_name") or payload.get("_projectId"),
        "type": "缺陷",
        "title": fields.get("title"),
        "description": fields.get("description"),
        "executor": _display_field_value("executor", fields.get("executor"), form),
        "tester": _display_field_value("tester", fields.get("tester"), form),
        "resolver": _display_field_value("resolver", fields.get("resolver"), form),
        "defect_category": _display_field_value("defect_category", fields.get("defect_category"), form),
        "severity": _display_field_value("severity", fields.get("severity"), form),
        "priority": str(payload.get("priority")) if payload.get("priority") is not None else None,
        "sprint": _display_field_value("sprint", fields.get("sprint"), form),
        "start_time": _display_time(fields.get("start_time")),
        "due_time": _display_time(fields.get("due_time")),
        "bug_or_legacy": _display_field_value("bug_or_legacy", fields.get("bug_or_legacy"), form),
        "environment": _display_field_value("environment", fields.get("environment"), form),
        "source": _display_field_value("source", fields.get("source"), form),
        "is_rd_project": _display_field_value("is_rd_project", fields.get("is_rd_project"), form),
        "related_product": _display_field_value("related_product", fields.get("related_product"), form),
        "related_project": _display_field_value("related_project", fields.get("related_project"), form),
        "related_database": _display_field_value("related_database", fields.get("related_database"), form),
        "service_org": _display_field_value("service_org", fields.get("service_org"), form),
        "customfields_count": len(payload.get("customfields") or []),
    }


def _display_field_value(name: str, value: Any, form: dict[str, Any]) -> str | None:
    if value in (None, ""):
        return None
    if isinstance(value, dict):
        return value.get("title") or value.get("name") or value.get("_id") or value.get("id")
    text = str(value)
    if name in {"executor", "tester", "resolver"}:
        display_names = (form.get("members") or {}).get("display_names") or {}
        return display_names.get(text) or text
    field = (form.get("fields") or {}).get(name) or {}
    for title, option_id in (field.get("options") or {}).items():
        if text in {str(title), str(option_id)}:
            return str(title)
    return text


def _display_time(value: Any) -> str | None:
    if value in (None, ""):
        return None
    text = str(value)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return text
    return parsed.astimezone(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M")


def _is_missing(value: Any) -> bool:
    return value is None or value == ""


def _default_business_fields() -> dict[str, Any]:
    form = teambition_bug_form_config()
    fields = form.get("fields") or {}
    defaults = form.get("defaults") or {}
    members = form.get("members") or {}
    bug_create = form.get("bug_create") or {}
    result = {
        "executor": bug_create.get("default_executor_id") or members.get("default_executor"),
        "tester": members.get("default_tester"),
        "resolver": members.get("default_resolver"),
        "defect_category": _field_object_default(fields, "defect_category"),
        "priority": (defaults.get("priority") or {}).get("value"),
    }
    for name in [
        "sprint",
        "severity",
        "bug_or_legacy",
        "environment",
        "source",
        "service_org",
        "is_rd_project",
        "related_product",
        "related_project",
        "related_database",
    ]:
        result[name] = _field_choice_default(fields, name) or _named_default(defaults, name)
    return {key: value for key, value in result.items() if value not in (None, "")}


def _named_default(defaults: dict[str, Any], name: str) -> Any:
    value = defaults.get(name)
    if isinstance(value, dict):
        return value.get("name") or value.get("value") or value.get("id")
    return value


def _field_choice_default(fields: dict[str, Any], name: str) -> Any:
    field = fields.get(name) or {}
    default = field.get("default")
    options = field.get("options") or {}
    if isinstance(default, str) and default in options:
        return options[default]
    return default


def _field_object_default(fields: dict[str, Any], name: str) -> dict[str, Any] | None:
    default = (fields.get(name) or {}).get("default")
    if not isinstance(default, dict):
        return None
    item_id = default.get("_id") or default.get("id")
    title = default.get("title") or default.get("name")
    if item_id and title:
        return {"title": title, "_id": item_id}
    return None


def _apply_runtime_defaults(fields: dict[str, Any]) -> dict[str, Any]:
    result = dict(fields)
    today = datetime.now(timezone(timedelta(hours=8))).date()
    if _is_missing(result.get("start_time")):
        result["start_time"] = f"{today} 08:30"
    if _is_missing(result.get("due_time")):
        result["due_time"] = f"{today} 22:00"
    return result


def _apply_environment_rules(fields: dict[str, Any]) -> dict[str, Any]:
    result = dict(fields)
    if result.get("environment") == "正服":
        result["defect_category"] = {"title": "企业版线上缺陷 / 线上缺陷", "_id": "655c8ace7c4907e734c6a851"}
        result["source"] = "用户反馈"
        result["is_rd_project"] = "否"
        result["sprint"] = "线上缺陷迭代"
    elif result.get("environment") in {"测服", "预发布"}:
        result["defect_category"] = "企业版迭代缺陷"
        result["source"] = "研发技术-测试"
        if result.get("sprint") == "6577dbefe126aba741240518":
            result.pop("sprint")
    return result
