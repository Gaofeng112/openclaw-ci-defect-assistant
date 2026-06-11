import json
import re
import sys
from argparse import Namespace
from typing import Any

from app.audit import write_audit
from app.config import jobs_config
from app.executor import execute
from app.schemas import CiCommand, CiResult
from app.tools.jenkins_tool import find_pending_confirmation
from app.tools.teambition_tool import find_pending_bug_confirmation


def handle_chat(args: Namespace) -> dict[str, Any]:
    command = _confirmation_command(args)
    action = _action(args.text) if command is None else command.action
    if command is None and action == "unknown_intent":
        result = CiResult(success=False, code="unknown_intent", message="没判断出是执行 Jenkins 还是创建 bug，请补充说明。")
    else:
        command = command or _command(args, action)
        result = execute(command)
        write_audit(command, result)
    return {"reply": _reply(result), "result": result.model_dump(exclude_none=True)}


def print_json(payload: dict[str, Any]) -> None:
    sys.stdout.buffer.write(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
    sys.stdout.buffer.write(b"\n")


def _confirmation_command(args: Namespace) -> CiCommand | None:
    if not _is_confirmation(args.text) or args.confirm_token:
        return None
    bug_data = find_pending_bug_confirmation(args.user_id, args.conversation_id)
    if bug_data:
        return _confirmed_command(args, "bug.create", dict(bug_data.get("fields") or {}), bug_data["token"])
    data = find_pending_confirmation(args.user_id, args.conversation_id)
    if not data:
        return None
    params = dict(data.get("parameters") or {})
    params |= {key: data[key] for key in ["env", "branch"] if data.get(key)}
    return _confirmed_command(args, "jenkins.trigger", params, data["token"], data.get("job"), bool(data.get("wait_result", True)))


def _confirmed_command(
    args: Namespace,
    action: str,
    params: dict[str, Any],
    token: str,
    job: str | None = None,
    wait_result: bool = True,
) -> CiCommand:
    return CiCommand(
        conversation_id=args.conversation_id,
        user_id=args.user_id,
        action=action,
        job=job,
        text=args.text,
        params=params,
        source=_source(args),
        confirmed=True,
        confirm_token=token,
        wait_result=wait_result,
    )


def _is_confirmation(text: str) -> bool:
    return re.sub(r"\s+", "", text.strip().lower()) in {"确认", "确定", "yes", "y", "ok", "确认创建", "继续创建", "确认提交"}


def _command(args: Namespace, action: str) -> CiCommand:
    payload = {
        "conversation_id": args.conversation_id,
        "user_id": args.user_id,
        "action": action,
        "text": args.text,
        "params": _params(args.text, action),
        "source": _source(args),
        "confirmed": args.confirmed,
        "confirm_token": args.confirm_token,
        "wait_result": not args.no_wait_result,
    }
    if action == "jenkins.trigger":
        payload["job"] = _job(args.text)
    if args.request_id:
        payload["request_id"] = args.request_id
    return CiCommand(**payload)


def _source(args: Namespace) -> dict[str, str]:
    return {"platform": "dingtalk", "conversation_id": args.conversation_id, "reporter_user_id": args.user_id}


def _action(text: str) -> str:
    lowered = text.lower()
    bug_words = ["bug", "缺陷", "问题单", "teambition", "创建问题", "提交问题"]
    jenkins_words = ["jenkins", "ci", "流水线", "自动化", "冒烟", "接口测试", "构建", "跑一下", "执行", "触发"]
    query_words = ["查询", "查一下", "结果", "状态", "链接", "刚才", "跑完"]
    bug_create_words = ["创建", "新建", "提交", "提bug", "提个bug", "提缺陷", "创建缺陷", "创建bug"]
    if _has(lowered, bug_words) and _has(lowered, bug_create_words):
        return "bug.create"
    if _has(lowered, bug_words) and _has(lowered, ["刚才", "查询", "查一下", "结果", "状态", "链接发"]):
        return "bug.query"
    if _has(lowered, jenkins_words) and _has(lowered, ["执行", "触发", "跑一下", "构建"]):
        return "jenkins.trigger"
    if _has(lowered, query_words) and _has(lowered, jenkins_words + ["跑完", "构建结果"]):
        return "jenkins.query"
    if _has(lowered, bug_words):
        return "bug.create"
    if _has(lowered, jenkins_words):
        return "jenkins.trigger"
    return "unknown_intent"


def _has(text: str, words: list[str]) -> bool:
    return any(word.lower() in text for word in words)


def _params(text: str, action: str) -> dict[str, str]:
    if action != "jenkins.trigger":
        return {}
    return {key: value for key, value in {
        "env": _match(text, [r"(?:环境|env)\s*[:：=]?\s*([a-zA-Z0-9_-]+)", r"\b(test|pre|stage|uat|prod)\b"]),
        "branch": _match(text, [r"(?:分支|branch)\s*[:：=]?\s*([a-zA-Z0-9._/-]+)"]),
    }.items() if value}


def _job(text: str) -> str:
    configured_jobs = jobs_config().get("jobs", jobs_config())
    for job in configured_jobs:
        if job.lower() in text.lower():
            return job
    if "api-auto-test" in configured_jobs and _has(text.lower(), ["api", "接口"]):
        return "api-auto-test"
    return "ci_test" if "ci_test" in configured_jobs else next(iter(configured_jobs), "")


def _match(text: str, patterns: list[str]) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            return match.group(1)
    return None


def _reply(result: CiResult) -> str:
    if result.code == "query_result" and (result.build_url or result.build_status):
        return _jenkins_preview(result, result.message)
    if result.code == "query_result" and (result.bug_url or result.task_id):
        return _bug_query(result)
    if result.code == "needs_confirmation":
        return _bug_preview(result) if result.preview.get("action") == "bug.create" else _jenkins_preview(result, "触发 Jenkins 前需要确认。请回复“确认”后继续。")
    if result.code in {"triggered", "build_success", "build_finished"}:
        return _jenkins_preview(result, result.message)
    if result.success and result.code == "created":
        return _bug_created(result)
    if result.code == "missing_fields":
        return f"还缺少：{', '.join(_field_label(name) for name in result.missing_fields)}。请补充后我继续创建。"
    return result.message


def _bug_query(result: CiResult) -> str:
    lines = [result.message]
    if result.task_id:
        lines.append(f"任务：{result.task_id}")
    if result.bug_url:
        lines.append(f"链接：{result.bug_url}")
    return "\n".join(lines)


def _bug_created(result: CiResult) -> str:
    display = result.extracted.get("display") or {}
    link = result.bug_url or (f"https://www.teambition.com/task/{result.task_id}" if result.task_id else "")
    lines = ["已创建 Teambition 缺陷", f"标题：{display.get('title') or result.extracted.get('title') or '缺陷'}"]
    for label, value in [("任务号", result.task_id), ("项目", display.get("project")), ("迭代", display.get("sprint")), ("链接", link)]:
        if value:
            lines.append(f"{label}：{value}")
    return "\n".join(lines)


def _bug_preview(result: CiResult) -> str:
    preview = result.preview
    display = preview.get("display") or {}
    items = [
        ("项目", display.get("project")),
        ("类型", display.get("type")),
        ("标题", display.get("title") or preview.get("title")),
        ("负责人", display.get("executor")),
        ("缺陷分类", display.get("defect_category")),
        ("严重程度", display.get("severity")),
        ("优先级", display.get("priority")),
        ("迭代", display.get("sprint")),
        ("截止时间", display.get("due_time")),
    ]
    lines = ["准备创建 Teambition 缺陷，请确认："]
    lines += [f"{label}：{value}" for label, value in items if value is not None]
    lines.append("回复“确认”创建；要修改就直接补充字段。")
    return "\n".join(lines)


def _jenkins_preview(result: CiResult, first_line: str) -> str:
    items = [("任务", result.job), ("环境", result.params.get("env")), ("分支", result.params.get("branch")), ("状态", result.build_status), ("链接", result.build_url)]
    return "\n".join([first_line] + [f"{label}：{value}" for label, value in items if value])


def _field_label(name: str) -> str:
    labels = {
        "title": "标题",
        "description": "备注",
        "executor": "执行者",
        "start_time": "开始时间",
        "due_time": "截止时间",
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
        "project_id": "项目",
        "tasklist_id": "任务分组",
    }
    return labels.get(name, name)
