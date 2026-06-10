import argparse
import base64
import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse


SENSITIVE_KEY_PARTS = ("auth", "token", "cookie", "secret", "password")

CANONICAL_FIELDS = [
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

FIELD_LABELS = {
    "title": "标题",
    "executor": "执行者",
    "start_time": "开始时间",
    "due_time": "截止时间",
    "description": "备注",
    "defect_category": "缺陷分类",
    "priority": "优先级",
    "severity": "严重程度",
    "sprint": "迭代",
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

LABEL_TO_CANONICAL = {label: name for name, label in FIELD_LABELS.items()}
LABEL_TO_CANONICAL.update({
    "content": "title",
    "executor": "executor",
    "startDate": "start_time",
    "dueDate": "due_time",
    "note": "description",
    "priority": "priority",
    "sprint": "sprint",
    "sprintId": "sprint",
    "缺陷环境": "environment",
    "缺陷来源": "source",
})


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract Teambition defect-form evidence from a browser HAR file.")
    parser.add_argument("har", help="Path to .har file exported from browser DevTools")
    parser.add_argument("--out-dir", default="runtime/teambition_har", help="Output directory for analysis files")
    parser.add_argument("--prefix", help="Output filename prefix. Defaults to HAR stem")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    har_path = Path(args.har)
    out_dir = Path(args.out_dir)
    prefix = args.prefix or har_path.stem
    out_dir.mkdir(parents=True, exist_ok=True)

    analysis = analyze_har(load_har(har_path), str(har_path))

    json_path = out_dir / f"{prefix}.teambition-fields.json"
    md_path = out_dir / f"{prefix}.teambition-fields.md"
    json_path.write_text(json.dumps(analysis, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(analysis), encoding="utf-8")

    print(json.dumps({
        "source": str(har_path),
        "json": str(json_path),
        "markdown": str(md_path),
        "observed_entries": analysis["summary"]["observed_entries"],
        "field_count": len(analysis["fields"]),
        "member_count": len(analysis["members"]),
        "existing_task_count": len(analysis["existing_tasks"]),
        "missing_canonical_fields": analysis["summary"]["missing_canonical_fields"],
    }, ensure_ascii=False))
    return 0


def load_har(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def analyze_har(har: dict[str, Any], source: str) -> dict[str, Any]:
    result: dict[str, Any] = {
        "source": source,
        "summary": {
            "observed_entries": 0,
            "missing_canonical_fields": list(CANONICAL_FIELDS),
        },
        "confirmed_ids": {},
        "endpoints": [],
        "fields": {},
        "tasklists": [],
        "sprints": [],
        "members": [],
        "customfield_choices": [],
        "customfield_popups": [],
        "existing_tasks": [],
        "create_payloads": [],
        "errors": [],
    }

    entries = har.get("log", {}).get("entries", [])
    result["summary"]["observed_entries"] = len(entries)
    for entry in entries:
        request = entry.get("request") or {}
        response = entry.get("response") or {}
        method = request.get("method") or "GET"
        url = request.get("url") or ""
        if "teambition.com" not in url:
            continue
        parsed = urlparse(url)
        query = {key: values[-1] for key, values in parse_qs(parsed.query).items()}
        status = response.get("status")
        body = response_json(entry)
        request_body = request_json(request)

        remember_ids(result, url, query)
        result["endpoints"].append({
            "method": method,
            "path": parsed.path,
            "status": status,
            "query_keys": sorted(query),
        })

        path = parsed.path
        if "scenariofieldconfigs" in path:
            extract_scenario_fields(result, body, status, url)
        elif path.endswith("/tasklists") or "/api/tasklists" in path:
            extend_unique(result["tasklists"], extract_tasklists(body), "id")
        elif path.endswith("/sprints") or "/sprints" in path:
            extend_unique(result["sprints"], extract_sprints(body), "id")
        elif "members/search" in path or re.search(r"/projects/[0-9a-f]{24}/members$", path):
            extend_unique(result["members"], extract_members(body), "id")
        elif "customfieldentities/choices" in path:
            result["customfield_choices"].append({
                "customfield_id": query.get("customfieldId"),
                "customfieldentity_id": query.get("customfieldentityId"),
                "status": status,
                "choices": extract_choices(body),
            })
        elif "/customfields/" in path and path.endswith("/popup"):
            result["customfield_popups"].append({
                "customfield_id": match_id(path),
                "sfc_id": query.get("sfcId"),
                "status": status,
                "options": extract_popup_options(body),
            })
        elif is_task_detail_path(path):
            extend_unique(result["existing_tasks"], extract_tasks(body), "id")

        if method.upper() == "POST" and is_task_create_path(path) and request_body:
            result["create_payloads"].append({
                "path": path,
                "status": status,
                "payload": redact_sensitive(request_body),
            })

        if isinstance(body, dict) and body.get("code") in {"InvalidCookie", "NoPermission", "AccessTokenMissing"}:
            result["errors"].append({
                "path": path,
                "status": status,
                "code": body.get("code"),
                "message": body.get("message") or body.get("error"),
            })

    add_system_fields_from_observations(result)
    seen = set(result["fields"])
    result["summary"]["missing_canonical_fields"] = [name for name in CANONICAL_FIELDS if name not in seen]
    result["endpoints"] = unique_dicts(result["endpoints"], ["method", "path", "status"])
    result["errors"] = unique_dicts(result["errors"], ["path", "status", "code"])
    return result


def response_json(entry: dict[str, Any]) -> Any:
    content = (entry.get("response") or {}).get("content") or {}
    text = content.get("text")
    if not text:
        return None
    if content.get("encoding") == "base64":
        try:
            text = base64.b64decode(text).decode("utf-8", errors="replace")
        except ValueError:
            return None
    return parse_json(text)


def request_json(request: dict[str, Any]) -> Any:
    text = ((request.get("postData") or {}).get("text") or "").strip()
    if not text:
        return None
    return parse_json(text)


def parse_json(text: str) -> Any:
    try:
        return json.loads(text)
    except ValueError:
        return None


def remember_ids(result: dict[str, Any], url: str, query: dict[str, str]) -> None:
    ids = result["confirmed_ids"]
    project_id = query.get("projectId") or query.get("_projectId") or first_match(url, r"/projects/([0-9a-f]{24})")
    organization_id = query.get("organizationId") or query.get("_organizationId") or first_match(url, r"/organizations/([0-9a-f]{24})")
    if project_id:
        ids.setdefault("project_id", project_id)
    if organization_id:
        ids.setdefault("organization_id", organization_id)


def extract_scenario_fields(result: dict[str, Any], body: Any, status: int | None, url: str) -> None:
    scenarios = as_list(body)
    for scenario in scenarios:
        if not isinstance(scenario, dict):
            continue
        if scenario.get("name") != "缺陷" and scenario.get("proTemplateConfigType") != "bug":
            continue
        result["confirmed_ids"].setdefault("scenariofieldconfig_id", scenario.get("_id"))
        result["confirmed_ids"].setdefault("taskflow_id", scenario.get("_taskflowId"))
        statuses = [
            {"id": item.get("_id"), "name": item.get("name"), "kind": item.get("kind")}
            for item in scenario.get("taskflowstatuses", [])
            if isinstance(item, dict)
        ]
        if statuses:
            result["confirmed_ids"]["taskflow_statuses"] = statuses
        for field in scenario.get("basicfields", []):
            add_basic_field(result, field)
        for field in scenario.get("scenariofields", []):
            add_scenario_field(result, field, status, url)


def add_basic_field(result: dict[str, Any], field: dict[str, Any]) -> None:
    field_type = field.get("fieldType")
    canonical = LABEL_TO_CANONICAL.get(str(field_type))
    if not canonical:
        return
    result["fields"][canonical] = {
        "label": FIELD_LABELS[canonical],
        "field_type": field_type,
        "field_config_id": field.get("_id"),
        "required": bool(field.get("required")),
        "source": "scenariofieldconfigs.basicfields",
    }


def add_scenario_field(result: dict[str, Any], field: dict[str, Any], status: int | None, url: str) -> None:
    field_type = field.get("fieldType")
    customfield = field.get("customfield") or {}
    label = customfield.get("name") or field_type
    canonical = LABEL_TO_CANONICAL.get(str(label)) or LABEL_TO_CANONICAL.get(str(field_type))
    if not canonical:
        return
    result["fields"][canonical] = {
        "label": label,
        "field_type": field_type,
        "field_config_id": field.get("_id"),
        "customfield_id": customfield.get("_id"),
        "customfield_type": customfield.get("type"),
        "required": bool(field.get("required")),
        "displayed": bool(field.get("displayed")),
        "default": field.get("default"),
        "choices": extract_choices(customfield),
        "source": "scenariofieldconfigs.scenariofields",
        "source_status": status,
        "source_url": url,
    }


def extract_tasklists(body: Any) -> list[dict[str, Any]]:
    items = as_list(body)
    return [
        {
            "id": item.get("_id") or item.get("id"),
            "name": item.get("title") or item.get("name"),
            "project_id": item.get("_projectId"),
            "is_archived": item.get("isArchived"),
        }
        for item in items
        if isinstance(item, dict)
    ]


def extract_sprints(body: Any) -> list[dict[str, Any]]:
    items = as_list(body)
    return [
        {
            "id": item.get("_id") or item.get("id"),
            "name": item.get("name"),
            "status": item.get("status"),
            "due_date": item.get("dueDate") or item.get("endDate"),
        }
        for item in items
        if isinstance(item, dict)
    ]


def extract_members(body: Any) -> list[dict[str, Any]]:
    members = as_list(body)
    if isinstance(body, dict):
        members = as_list(body.get("result") or body.get("data") or body.get("members"))
    return [
        {
            "id": item.get("_id") or item.get("id"),
            "user_id": item.get("_userId") or item.get("userId"),
            "name": item.get("name") or dig(item, ["user", "name"]),
            "role": item.get("role") or item.get("_roleId"),
            "team_name": item.get("teamName"),
        }
        for item in members
        if isinstance(item, dict)
    ]


def extract_tasks(body: Any) -> list[dict[str, Any]]:
    items = as_list(body)
    if isinstance(body, dict):
        if any(key in body for key in ["_id", "id", "content", "customfields", "priority"]):
            items = [body]
        else:
            items = as_list(body.get("result") or body.get("data") or body.get("task"))
    return [
        {
            "id": item.get("taskId") or item.get("_id") or item.get("id"),
            "title": item.get("content") or item.get("title"),
            "priority": item.get("priority"),
            "executor_id": item.get("_executorId") or item.get("executorId"),
            "sprint_id": item.get("_sprintId") or item.get("sprintId"),
            "start_time": item.get("startDate"),
            "due_time": item.get("dueDate"),
            "note": item.get("note"),
            "taskflowstatus_id": item.get("_taskflowstatusId") or item.get("tfsId"),
            "scenariofieldconfig_id": item.get("_scenariofieldconfigId") or item.get("sfcId"),
            "customfields": item.get("customfields"),
        }
        for item in items
        if isinstance(item, dict) and (item.get("content") or item.get("title") or item.get("customfields"))
    ]


def add_system_fields_from_observations(result: dict[str, Any]) -> None:
    create_payloads = result.get("create_payloads") or []
    for item in create_payloads:
        payload = item.get("payload") if isinstance(item, dict) else None
        if isinstance(payload, dict) and (payload.get("content") or payload.get("title")):
            result["fields"].setdefault("title", {
                "label": "鏍囬",
                "field_type": "content",
                "required": True,
                "source": "create_payload",
            })
            break
    if result["existing_tasks"]:
        task = result["existing_tasks"][0]
        if task.get("title"):
            result["fields"].setdefault("title", {
                "label": "标题",
                "field_type": "content",
                "required": True,
                "source": "existing_task_detail",
            })
        if task.get("priority") is not None:
            result["fields"].setdefault("priority", {
                "label": "优先级",
                "field_type": "priority",
                "required": True,
                "observed_value": task.get("priority"),
                "source": "existing_task_detail",
            })
        if task.get("sprint_id"):
            result["fields"].setdefault("sprint", {
                "label": "迭代",
                "field_type": "sprintId",
                "required": True,
                "observed_value": task.get("sprint_id"),
                "source": "existing_task_detail",
            })
    elif result["sprints"]:
        result["fields"].setdefault("sprint", {
            "label": "迭代",
            "field_type": "sprintId",
            "required": True,
            "source": "sprints_endpoint",
        })


def extract_choices(body: Any) -> list[dict[str, Any]]:
    if not body:
        return []
    choices = body
    if isinstance(body, dict):
        choices = body.get("choices")
        if choices is None and isinstance(body.get("result"), dict):
            choices = body["result"].get("choices")
        if choices is None and isinstance(body.get("data"), dict):
            choices = body["data"].get("choices")
    if not isinstance(choices, list):
        return []
    result = []
    for item in choices:
        if isinstance(item, dict):
            result.append({
                "id": item.get("_id") or item.get("id"),
                "name": item.get("value") or item.get("name") or item.get("title") or item.get("label"),
                "is_root": item.get("isRoot"),
            })
    return result


def extract_popup_options(body: Any) -> list[dict[str, Any]]:
    if not isinstance(body, dict):
        return []
    for key in ["options", "choices", "result", "data"]:
        options = body.get(key)
        if isinstance(options, list):
            return extract_choices({"choices": options})
    return []


def as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        for key in ["result", "data", "items", "list"]:
            if isinstance(value.get(key), list):
                return value[key]
    return []


def is_task_detail_path(path: str) -> bool:
    lowered = path.lower()
    return "/task/query" in lowered or re.search(r"/api/(v\d+/)?tasks?/", lowered) is not None


def is_task_create_path(path: str) -> bool:
    lowered = path.lower().rstrip("/")
    return bool(re.fullmatch(r"/api/(v\d+/)?tasks", lowered))


def redact_sensitive(value: Any) -> Any:
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            lowered = str(key).lower()
            if any(part in lowered for part in SENSITIVE_KEY_PARTS):
                result[key] = "[REDACTED]"
            else:
                result[key] = redact_sensitive(item)
        return result
    if isinstance(value, list):
        return [redact_sensitive(item) for item in value]
    if isinstance(value, str):
        lowered = value.lower()
        if value.startswith("Bearer "):
            return "[REDACTED]"
        if any(part in lowered for part in ["token=", "signature=", "ossaccesskeyid=", "access_token="]):
            return "[REDACTED_URL]"
    return value


def match_id(text: str) -> str | None:
    return first_match(text, r"([0-9a-f]{24})")


def first_match(text: str, pattern: str) -> str | None:
    match = re.search(pattern, text)
    return match.group(1) if match else None


def dig(data: dict[str, Any], path: list[str]) -> Any:
    current: Any = data
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def extend_unique(target: list[dict[str, Any]], items: list[dict[str, Any]], key: str) -> None:
    seen = {item.get(key) for item in target}
    for item in items:
        value = item.get(key)
        if value and value not in seen:
            target.append(item)
            seen.add(value)


def unique_dicts(items: list[dict[str, Any]], keys: list[str]) -> list[dict[str, Any]]:
    result = []
    seen = set()
    for item in items:
        marker = tuple(item.get(key) for key in keys)
        if marker in seen:
            continue
        seen.add(marker)
        result.append(item)
    return result


def render_markdown(analysis: dict[str, Any]) -> str:
    lines = [
        "# Teambition HAR 字段提取结果",
        "",
        f"- 来源：`{analysis['source']}`",
        f"- HAR entries：{analysis['summary']['observed_entries']}",
        f"- 已识别字段数：{len(analysis['fields'])}",
        f"- 已识别成员数：{len(analysis['members'])}",
        f"- 已识别已有任务数：{len(analysis['existing_tasks'])}",
        "",
        "## 已确认 ID",
        "",
    ]
    for key, value in analysis["confirmed_ids"].items():
        if key == "taskflow_statuses":
            continue
        lines.append(f"- `{key}`: `{value}`")

    lines += ["", "## 统一字段覆盖情况", "", "| 统一字段 | 公司字段 | 字段 ID | 必填 | 选项数 |", "|---|---|---|---|---|"]
    for name in CANONICAL_FIELDS:
        field = analysis["fields"].get(name) or {}
        lines.append(
            f"| `{name}` | {field.get('label', FIELD_LABELS[name])} | "
            f"`{field.get('customfield_id') or field.get('field_config_id') or ''}` | "
            f"{field.get('required', '')} | {len(field.get('choices') or [])} |"
        )

    if analysis["summary"]["missing_canonical_fields"]:
        lines += ["", "## 仍缺字段", ""]
        for name in analysis["summary"]["missing_canonical_fields"]:
            lines.append(f"- `{name}` / {FIELD_LABELS[name]}")

    if analysis["members"]:
        lines += ["", "## 成员候选", "", "| 姓名 | member id | user id |", "|---|---|---|"]
        for member in analysis["members"][:80]:
            lines.append(f"| {member.get('name') or ''} | `{member.get('id') or ''}` | `{member.get('user_id') or ''}` |")

    if analysis["sprints"]:
        lines += ["", "## 迭代候选", "", "| 名称 | ID | 状态 | 截止时间 |", "|---|---|---|---|"]
        for sprint in analysis["sprints"][:80]:
            lines.append(f"| {sprint.get('name') or ''} | `{sprint.get('id') or ''}` | {sprint.get('status') or ''} | {sprint.get('due_date') or ''} |")

    if analysis["errors"]:
        lines += ["", "## 抓取中的权限/登录问题", "", "| 接口 | 状态 | 错误 |", "|---|---|---|"]
        for error in analysis["errors"][:40]:
            lines.append(f"| `{error.get('path')}` | {error.get('status')} | {error.get('code')} {error.get('message') or ''} |")

    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
