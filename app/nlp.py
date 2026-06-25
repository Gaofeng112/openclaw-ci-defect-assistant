import re
from typing import Any


FIELD_ALIASES = {
    "title": ("title", "标题", "问题", "缺陷", "bug"),
    "executor": ("executor", "执行者", "执行人", "处理人", "负责人"),
    "start_time": ("start_time", "开始时间", "开始日期"),
    "due_time": ("due_time", "截止时间", "截止日期", "到期时间"),
    "description": ("description", "描述", "详情", "备注"),
    "defect_category": ("defect_category", "缺陷分类", "分类"),
    "priority": ("priority", "优先级"),
    "severity": ("severity", "严重程度", "级别"),
    "sprint": ("sprint", "迭代"),
    "tester": ("tester", "测试人员", "测试人"),
    "bug_or_legacy": ("bug_or_legacy", "BUG/遗留", "bug_or_legacy"),
    "resolver": ("resolver", "缺陷解决人", "解决人"),
    "environment": ("environment", "缺陷环境", "环境", "测试环境"),
    "source": ("source", "缺陷来源", "来源"),
    "service_org": ("service_org", "服务组织"),
    "is_rd_project": ("is_rd_project", "是否为研发立项", "研发立项"),
    "related_product": ("related_product", "相关产品", "产品"),
    "related_project": ("related_project", "相关项目"),
    "related_database": ("related_database", "相关数据库", "数据库"),
    "steps": ("steps", "步骤", "复现步骤", "操作步骤"),
    "expected": ("expected", "期望", "预期", "预期结果"),
    "actual": ("actual", "实际", "实际结果", "现象"),
}

SEVERITY_WORDS = {
    "致命": "致命",
    "严重": "严重",
    "一般": "一般",
    "轻微": "轻微",
    "p0": "致命",
    "p1": "严重",
    "p2": "一般",
    "p3": "轻微",
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
    if "environment" not in fields and fields.get("env"):
        fields["environment"] = fields.pop("env")
    if "description" not in fields and any(fields.get(name) for name in ["steps", "actual", "expected"]):
        fields["description"] = _description_from_parts(fields)
    if "description" not in fields and fields.get("title"):
        fields["description"] = fields["title"]
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
    environment = _match_first(text, [r"(正服|线上|生产|测服|测试服|预发布)", r"(?:环境|env)\s*[:：=]?\s*([a-zA-Z0-9_-]+)", r"\b(env|test|pre|prod|uat)\b"])
    if environment:
        result.setdefault("environment", environment)
    if "中国上市" in text:
        issue_text = _strip_value(re.split(r"[，,]\s*给", text, 1)[0])
        result.setdefault("related_database", "中国上市药品")
        result.setdefault("title", "【中国上市】" + _strip_value(re.sub(r".*?中国上市", "", text).split("，给", 1)[0]))
        result.setdefault("description", issue_text)
    owner = re.search(r"给\s*([A-Za-z0-9_\-\u4e00-\u9fff]+)\s*创建", text)
    if owner:
        result.setdefault("executor", owner.group(1))
        result.setdefault("resolver", owner.group(1))
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


def _description_from_parts(fields: dict[str, Any]) -> str:
    return "\n\n".join([
        f"【步骤】\n{fields.get('steps', '')}",
        f"【结果】\n{fields.get('actual', '')}",
        f"【期望】\n{fields.get('expected', '')}",
    ])
