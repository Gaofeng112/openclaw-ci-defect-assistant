from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any


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


def load_evidence(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def build_v2_task_payload(fields: dict[str, Any], evidence: dict[str, Any]) -> dict[str, Any]:
    payload = _template_payload(evidence)
    remove_reusable_note_tokens(payload)
    _set_if_present(payload, "content", fields, "title")
    _set_if_present(payload, "note", fields, "description")
    _set_if_present(payload, "_executorId", fields, "executor")
    _set_if_present(payload, "startDate", fields, "start_time")
    _set_if_present(payload, "dueDate", fields, "due_time")
    _set_if_present(payload, "_sprintId", fields, "sprint")
    if "priority" in fields:
        payload["priority"] = _priority_value(fields["priority"])

    customfields = payload.get("customfields")
    if not isinstance(customfields, list):
        raise ValueError("template payload does not contain customfields")

    for name in CUSTOMFIELD_NAMES:
        if name not in fields:
            continue
        customfield_id = _customfield_id(evidence, name)
        if not customfield_id:
            raise ValueError(f"missing customfield_id for {name}")
        item = _find_customfield(customfields, customfield_id)
        if item is None:
            item = {"_customfieldId": customfield_id}
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


def _priority_value(value: Any) -> int:
    if isinstance(value, int):
        return value
    text = str(value).strip()
    if re.fullmatch(r"-?\d+", text):
        return int(text)
    raise ValueError("priority must be a numeric Teambition priority value for dry-run")


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
    template_match = _template_choice(text, template)
    if template_match:
        return template_match
    for member in evidence.get("members") or []:
        if text in {str(member.get("id") or ""), str(member.get("user_id") or ""), str(member.get("name") or "")}:
            return {"_id": member.get("id"), "title": member.get("name")}
    return {"title": text}


def _choice_value(value: Any, evidence: dict[str, Any], name: str, template: dict[str, Any], keep_id: bool) -> dict[str, Any]:
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


def _template_choice(text: str, template: dict[str, Any]) -> dict[str, Any] | None:
    for value in template.get("value") or []:
        if not isinstance(value, dict):
            continue
        choice_id = str(value.get("_id") or "")
        title = str(value.get("title") or "")
        if text in {choice_id, title}:
            return {key: item for key, item in value.items() if key in {"_id", "title", "thumbUrl"}}
    return None
