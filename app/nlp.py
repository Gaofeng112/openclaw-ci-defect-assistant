import re
from typing import Any


FIELD_ALIASES = {
    "title": ("title", "标题", "问题", "缺陷", "bug"),
    "module": ("module", "模块", "功能", "页面"),
    "severity": ("severity", "优先级", "严重程度", "级别"),
    "env": ("env", "环境", "测试环境"),
    "steps": ("steps", "步骤", "复现步骤", "操作步骤"),
    "expected": ("expected", "期望", "预期", "预期结果"),
    "actual": ("actual", "实际", "实际结果", "现象"),
    "description": ("description", "描述", "详情", "备注"),
}

SEVERITY_WORDS = {
    "较低": "较低",
    "低": "较低",
    "普通": "普通",
    "一般": "普通",
    "中": "普通",
    "高": "较高",
    "较高": "较高",
    "紧急": "紧急",
    "严重": "紧急",
    "p0": "紧急",
    "p1": "较高",
    "p2": "普通",
    "p3": "较低",
}


def extract_bug_fields(text: str | None, params: dict[str, Any] | None = None) -> dict[str, Any]:
    fields = _clean(params or {})
    if not text:
        return _normalize(fields)
    return _normalize(_extract_freeform(text) | _extract_labeled(text) | fields)


def _clean(fields: dict[str, Any]) -> dict[str, Any]:
    return {key: value.strip() if isinstance(value, str) else value for key, value in fields.items() if value not in (None, "")}


def _normalize(fields: dict[str, Any]) -> dict[str, Any]:
    if "severity" in fields:
        fields["severity"] = SEVERITY_WORDS.get(str(fields["severity"]).lower(), fields["severity"])
    return fields


def _extract_labeled(text: str) -> dict[str, str]:
    alias_map = {alias.lower(): field for field, aliases in FIELD_ALIASES.items() for alias in aliases}
    labels = "|".join(re.escape(alias) for alias in sorted(alias_map, key=len, reverse=True))
    pattern = re.compile(rf"(?P<label>{labels})\s*[:：=]\s*(?P<value>.*?)(?=(?:\s*(?:{labels})\s*[:：=])|$)", re.I | re.S)
    return {alias_map[m.group("label").lower()]: _strip_value(m.group("value")) for m in pattern.finditer(text)}


def _extract_freeform(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    lower = text.lower()
    for word, severity in SEVERITY_WORDS.items():
        if word in lower:
            result.setdefault("severity", severity)
            break
    env = _match_first(text, [r"(?:环境|在)\s*([a-zA-Z0-9_-]+)\s*(?:环境)?", r"\b(env|test|pre|prod|uat)\b"])
    if env:
        result.setdefault("env", env)
    if "title" not in result and not _extract_labeled(text):
        result["title"] = _strip_value(re.sub(r"^(帮我|请|创建|新建|提一个|提个|bug|缺陷|\s)+", "", text, flags=re.I))
    return result


def _match_first(text: str, patterns: list[str]) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            return match.group(1)
    return None


def _strip_value(value: str) -> str:
    return value.strip(" \t\r\n，,；;。")
