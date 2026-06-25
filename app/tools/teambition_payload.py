from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any

from app.config import teambition_bug_form_config


CUSTOMFIELD_NAMES = [
    "defect_category",
    "severity",
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

MEMBER_FIELDS = {"tester", "resolver"}
EXECUTOR_FIELD = "executor"
KNOWN_CHOICE_VALUES = {
    "defect_category": {
        "655c8ace7c4907e734c6a851": {
            "title": "企业版线上缺陷 / 线上缺陷",
            "_id": "655c8ace7c4907e734c6a851",
        },
        "企业版线上缺陷 / 线上缺陷": {
            "title": "企业版线上缺陷 / 线上缺陷",
            "_id": "655c8ace7c4907e734c6a851",
        },
        "线上缺陷": {
            "title": "企业版线上缺陷 / 线上缺陷",
            "_id": "655c8ace7c4907e734c6a851",
        },
    },
}


def load_evidence(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def build_v2_task_payload(fields: dict[str, Any], evidence: dict[str, Any]) -> dict[str, Any]:
    payload = _template_payload(evidence)
    remove_reusable_note_tokens(payload)
    template_customfields = _customfield_templates(payload)
    _set_if_present(payload, "_projectId", fields, "project_id")
    _set_if_present(payload, "_tasklistId", fields, "tasklist_id")
    _set_if_present(payload, "_stageId", fields, "stage_id")
    _set_if_present(payload, "_taskflowstatusId", fields, "taskflowstatus_id")
    _set_if_present(payload, "_scenariofieldconfigId", fields, "sfc_id")
    _set_if_present(payload, "content", fields, "title")
    _set_if_present(payload, "note", fields, "description")
    _set_executor_if_present(payload, fields, evidence)
    _set_date_if_present(payload, "startDate", fields, "start_time")
    _set_date_if_present(payload, "dueDate", fields, "due_time")
    _set_sprint_id(payload, fields, evidence)
    if "priority" in fields:
        payload["priority"] = _priority_value(fields["priority"])

    if not isinstance(payload.get("customfields"), list):
        raise ValueError("template payload does not contain customfields")
    customfields: list[dict[str, Any]] = []
    payload["customfields"] = customfields

    for name in CUSTOMFIELD_NAMES:
        if name not in fields:
            continue
        customfield_id = _customfield_id(evidence, name)
        if not customfield_id:
            raise ValueError(f"missing customfield_id for {name}")
        item = _empty_customfield(template_customfields.get(customfield_id), customfield_id)
        customfields.append(item)
        _set_customfield_value(item, fields[name], evidence, name)
    return payload


def remove_reusable_note_tokens(payload: dict[str, Any]) -> None:
    payload.pop("noteRtfValue", None)
    payload.pop("noteRtfData", None)
    payload.pop("noteRenderMode", None)


def _template_payload(evidence: dict[str, Any]) -> dict[str, Any]:
    payloads = evidence.get("create_payloads") or []
    for item in payloads:
        if item.get("path") == "/api/v2/tasks" and isinstance(item.get("payload"), dict):
            return copy.deepcopy(item["payload"])
    raise ValueError("no /api/v2/tasks payload found in evidence")


def _set_if_present(payload: dict[str, Any], target: str, fields: dict[str, Any], source: str) -> None:
    value = fields.get(source)
    if value not in (None, ""):
        payload[target] = value


def _set_date_if_present(payload: dict[str, Any], target: str, fields: dict[str, Any], source: str) -> None:
    value = fields.get(source)
    if value not in (None, ""):
        payload[target] = _date_value(value)


def _set_executor_if_present(payload: dict[str, Any], fields: dict[str, Any], evidence: dict[str, Any]) -> None:
    value = fields.get(EXECUTOR_FIELD)
    if value in (None, ""):
        return
    payload["_executorId"] = _member_id(value, evidence) or str(value)


def _customfield_templates(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    customfields = payload.get("customfields")
    if not isinstance(customfields, list):
        return {}
    result: dict[str, dict[str, Any]] = {}
    for item in customfields:
        if not isinstance(item, dict):
            continue
        customfield_id = item.get("_customfieldId")
        if customfield_id:
            result[str(customfield_id)] = copy.deepcopy(item)
    return result


def _empty_customfield(template: dict[str, Any] | None, customfield_id: str) -> dict[str, Any]:
    item = copy.deepcopy(template) if isinstance(template, dict) else {"_customfieldId": customfield_id}
    item["_customfieldId"] = customfield_id
    item["value"] = []
    if "values" in item:
        item["values"] = []
    return item


def _set_sprint_id(payload: dict[str, Any], fields: dict[str, Any], evidence: dict[str, Any]) -> None:
    value = fields.get("sprint")
    if value in (None, ""):
        return
    sprint_id = _sprint_id(value, evidence)
    payload["_sprintId"] = sprint_id


def _priority_value(value: Any) -> int:
    if isinstance(value, int):
        priority = value
    else:
        text = str(value).strip()
        if not re.fullmatch(r"-?\d+", text):
            raise ValueError("priority must be a numeric Teambition priority value")
        priority = int(text)
    if priority in {0, 1, 2, 3, 4, 5}:
        return priority
    raise ValueError("priority must be one of 0, 1, 2, 3, 4, 5")


def _date_value(value: Any) -> str:
    text = str(value).strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}", text):
        return text.replace(" ", "T") + ":00+08:00"
    return text


def _sprint_id(value: Any, evidence: dict[str, Any]) -> str | None:
    text = str(value).strip()
    if not text:
        return None
    for sprint in evidence.get("sprints") or []:
        sprint_id = str(sprint.get("id") or "").strip()
        sprint_name = str(sprint.get("name") or "").strip()
        if text in {sprint_id, sprint_name}:
            return sprint_id or None
    normalized = _normalize_name(text)
    for sprint in evidence.get("sprints") or []:
        sprint_id = str(sprint.get("id") or "").strip()
        sprint_name = str(sprint.get("name") or "").strip()
        sprint_normalized = _normalize_name(sprint_name)
        if normalized and sprint_normalized and (normalized in sprint_normalized or sprint_normalized in normalized):
            return sprint_id or None
    if re.fullmatch(r"[0-9a-f]{24}", text, re.I):
        return text
    return None


def _normalize_name(text: str) -> str:
    return re.sub(r"\s+", "", text).lower()


def _customfield_id(evidence: dict[str, Any], name: str) -> str | None:
    field = (evidence.get("fields") or {}).get(name) or {}
    return field.get("customfield_id")


def _find_customfield(customfields: list[dict[str, Any]], customfield_id: str) -> dict[str, Any] | None:
    for item in customfields:
        if item.get("_customfieldId") == customfield_id:
            return item
    return None


def _set_customfield_value(item: dict[str, Any], raw_value: Any, evidence: dict[str, Any], name: str) -> None:
    values = raw_value if isinstance(raw_value, list) else [raw_value]
    keep_id = _template_value_has_id(item) or "values" in item
    resolved = [
        _member_value(value, evidence, item) if name in MEMBER_FIELDS else _choice_value(value, evidence, name, item, keep_id)
        for value in values
    ]
    item["value"] = resolved
    ids = [value["_id"] for value in resolved if isinstance(value, dict) and value.get("_id")]
    if "values" in item:
        item["values"] = ids


def _template_value_has_id(item: dict[str, Any]) -> bool:
    for value in item.get("value") or []:
        if isinstance(value, dict) and value.get("_id"):
            return True
    return False


def _member_value(value: Any, evidence: dict[str, Any], template: dict[str, Any]) -> dict[str, Any]:
    if isinstance(value, dict):
        return {"_id": value.get("_id") or value.get("id"), "title": value.get("title") or value.get("name")}
    text = str(value).strip()
    mapped = _configured_member_id(text)
    if mapped:
        return _member_value(mapped, evidence, template)
    template_match = _template_choice(text, template)
    if template_match:
        return template_match
    for member in evidence.get("members") or []:
        if text in {str(member.get("id") or ""), str(member.get("user_id") or ""), str(member.get("name") or "")}:
            return {"_id": member.get("id"), "title": member.get("name")}
    return {"title": text}


def _member_id(value: Any, evidence: dict[str, Any]) -> str | None:
    if isinstance(value, dict):
        item_id = value.get("_id") or value.get("id")
        return str(item_id) if item_id else None
    text = str(value).strip()
    mapped = _configured_member_id(text)
    if mapped:
        return _member_id(mapped, evidence)
    for member in evidence.get("members") or []:
        if text in {str(member.get("id") or ""), str(member.get("user_id") or ""), str(member.get("name") or "")}:
            return str(member.get("id") or "")
    return None


def _configured_member_id(text: str) -> str | None:
    by_name = (teambition_bug_form_config().get("members") or {}).get("by_name") or {}
    value = by_name.get(text)
    return str(value).strip() or None if value else None


def _choice_value(value: Any, evidence: dict[str, Any], name: str, template: dict[str, Any], keep_id: bool) -> dict[str, Any]:
    known_match = _known_choice_value(value, name)
    if known_match:
        return known_match
    if isinstance(value, dict):
        choice_id = value.get("_id") or value.get("id")
        result = {"title": value.get("title") or value.get("name")}
        if keep_id and choice_id:
            result["_id"] = choice_id
        return result
    text = str(value).strip()
    template_match = _template_choice(text, template)
    if template_match:
        return template_match if keep_id else {"title": template_match["title"]}
    for choice in ((evidence.get("fields") or {}).get(name) or {}).get("choices") or []:
        if text in {str(choice.get("id") or ""), str(choice.get("name") or "")}:
            result = {"title": choice.get("name")}
            if keep_id and choice.get("id"):
                result["_id"] = choice.get("id")
            return result
    return {"title": text}


def _known_choice_value(value: Any, name: str) -> dict[str, Any] | None:
    choices = KNOWN_CHOICE_VALUES.get(name)
    if not choices:
        return None
    if isinstance(value, dict):
        choice_id = str(value.get("_id") or value.get("id") or "").strip()
        title = str(value.get("title") or value.get("name") or "").strip()
        matched = choices.get(choice_id) or choices.get(title)
    else:
        matched = choices.get(str(value).strip())
    if not matched:
        return None
    return dict(matched)


def _template_choice(text: str, template: dict[str, Any]) -> dict[str, Any] | None:
    for value in template.get("value") or []:
        if not isinstance(value, dict):
            continue
        choice_id = str(value.get("_id") or "")
        title = str(value.get("title") or "")
        if text in {choice_id, title}:
            return {key: item for key, item in value.items() if key in {"_id", "title", "thumbUrl"}}
    return None
