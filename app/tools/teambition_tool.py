import base64
import hashlib
import hmac
import json
import time
from typing import Any

import httpx

from app.config import teambition_settings
from app.nlp import extract_bug_fields
from app.schemas import BugCreateRequest, BugCreateResponse
from app.session_store import clear_fields, load_fields, save_fields


ACTION = "bug.create"
REQUIRED_FIELDS = [
    "title",
    "executor",
    "start_time",
    "due_time",
    "description",
    "defect_category",
    "priority",
    "severity",
    "sprint",
    "tester",
    "bug_or_legacy",
    "resolver",
    "environment",
    "source",
    "service_org",
    "is_rd_project",
    "related_product",
    "related_project",
    "related_database",
]
REQUIRED_CONFIG_FIELDS = ["project_id", "tasklist_id"]
DEFAULTS = {
    "priority": "无关紧要",
    "severity": "一般",
    "bug_or_legacy": "BUG",
    "service_org": "集团公司",
    "related_product": "药智数据企业版",
}
SYSTEM_FIELDS = {"project_id", "tasklist_id"}


def create_bug(request: BugCreateRequest) -> BugCreateResponse:
    fields = _merged_fields(request)
    missing = [name for name in REQUIRED_FIELDS if not fields.get(name)]
    if missing:
        save_fields(ACTION, request.conversation_id, _public_fields(fields))
        return BugCreateResponse(
            success=False,
            code="missing_fields",
            message=f"缺少 {', '.join(missing)}，请补充后继续。",
            missing_fields=missing,
            fields=_public_fields(fields),
        )
    missing_config = [name for name in REQUIRED_CONFIG_FIELDS if not fields.get(name)]
    if missing_config:
        return BugCreateResponse(
            success=False,
            code="missing_config",
            message=f"缺少 Teambition 配置: {', '.join(missing_config)}",
            fields=_public_fields(fields),
        )

    if _mock_enabled():
        return _mock_response(request, fields)

    response = _create_task(fields)
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
        "executor_id": settings["default_executor_id"],
    }
    fields |= load_fields(ACTION, request.conversation_id)
    fields |= extract_bug_fields(request.text, request.fields)
    return {key: value for key, value in fields.items() if value not in (None, "")}


def _mock_enabled() -> bool:
    settings = teambition_settings()
    return not all(settings[key] for key in ["app_id", "app_secret", "org_id"]) or settings["app_id"].lower() == "xxx"


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


def _create_task(fields: dict[str, Any]) -> BugCreateResponse:
    settings = teambition_settings()
    payload = {
        "content": fields["title"],
        "projectId": fields["project_id"],
        "tasklistId": fields["tasklist_id"],
        "executorId": fields.get("executor") or settings["default_executor_id"],
        "startDate": fields.get("start_time"),
        "dueDate": fields.get("due_time"),
        "note": _note(fields),
        "priority": _priority(fields["priority"], settings["priority_map"]),
        "stageId": settings["stage_id"],
        "tfsId": settings["taskflowstatus_id"],
        "sfcId": settings["sfc_id"],
        "customfields": _customfields(fields, settings["customfields"]) or None,
    }
    try:
        with httpx.Client(timeout=20, trust_env=False) as client:
            response = client.post(
                f"{settings['base_url']}/v3/task/create",
                headers=_headers(settings),
                json={key: value for key, value in payload.items() if value is not None},
            )
            data = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        return BugCreateResponse(success=False, code="teambition_connection_failed", message=f"Teambition 连接失败: {exc}", fields=fields)

    if response.status_code != 200 or data.get("code") not in {0, 200}:
        return BugCreateResponse(
            success=False,
            code=data.get("errorCode") or "teambition_error",
            message=data.get("errorMessage") or f"Teambition 创建失败: HTTP {response.status_code}",
            fields=_public_fields(fields),
        )

    task = data.get("result") or {}
    task_id = task.get("taskId") or task.get("id") or task.get("_id") or _find_task_id(fields)
    return BugCreateResponse(
        success=True,
        code="created",
        message=f"已创建 Teambition 缺陷：{fields['title']}",
        bug_url=_task_url(task_id),
        task_id=task_id,
        fields=_public_fields(fields),
    )


def _find_task_id(fields: dict[str, Any]) -> str | None:
    settings = teambition_settings()
    try:
        with httpx.Client(timeout=20, trust_env=False) as client:
            response = client.get(
                f"{settings['base_url']}/v3/project/{fields['project_id']}/task/query",
                headers=_headers(settings),
            )
            data = response.json()
    except (httpx.HTTPError, ValueError):
        return None
    result = data.get("result")
    if not isinstance(result, list):
        return None
    matches = [task for task in result if task.get("content") == fields["title"]]
    return _task_id(matches[-1]) if matches else None


def _headers(settings: dict[str, str]) -> dict[str, str]:
    headers = {
        "Authorization": f"Bearer {_app_token(settings['app_id'], settings['app_secret'])}",
        "Content-Type": "application/json",
        "X-Tenant-Type": "organization",
        "X-Tenant-Id": settings["org_id"],
    }
    if settings["operator_id"]:
        headers["x-operator-id"] = settings["operator_id"]
    return headers


def _app_token(app_id: str, app_secret: str) -> str:
    now = int(time.time())
    header = _b64url(json.dumps({"typ": "JWT", "alg": "HS256"}, separators=(",", ":")).encode())
    payload = _b64url(json.dumps({"_appId": app_id, "iat": now, "exp": now + 3600}, separators=(",", ":")).encode())
    signature = hmac.new(app_secret.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest()
    return f"{header}.{payload}.{_b64url(signature)}"


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _note(fields: dict[str, Any]) -> str:
    return str(fields["description"])


def _public_fields(fields: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in fields.items() if key not in SYSTEM_FIELDS}


def _priority(severity: str, priority_map: dict[str, int]) -> int | None:
    value = priority_map.get(str(severity))
    return int(value) if value not in (None, "") else None


def _task_id(task: dict[str, Any]) -> str | None:
    return task.get("taskId") or task.get("id") or task.get("_id")


def _customfields(fields: dict[str, Any], customfield_config: dict[str, str]) -> list[dict[str, Any]]:
    labels = {
        "defect_category": "缺陷分类",
        "severity": "严重程度",
        "tester": "测试人员",
        "bug_or_legacy": "BUG/遗留",
        "resolver": "缺陷解决人",
        "environment": "缺陷环境",
        "source": "缺陷来源",
        "service_org": "服务组织",
        "is_rd_project": "是否为研发立项",
        "related_product": "相关产品",
        "related_project": "相关项目",
        "related_database": "相关数据库",
    }
    result = []
    for name, cf_id in customfield_config.items():
        if fields.get(name) and cf_id:
            result.append({
                "cfId": cf_id,
                "customfieldName": labels.get(name, name),
                "value": [{"title": str(fields[name])}],
            })
    return result


def _task_url(task_id: str | None) -> str | None:
    return f"https://www.teambition.com/task/{task_id}" if task_id else None
