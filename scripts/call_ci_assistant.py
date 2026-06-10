import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.audit import write_audit
from app.config import jobs_config
from app.schemas import CiCommand, CiResult
from app.tools.jenkins_tool import find_pending_confirmation
from app.tools.teambition_tool import find_pending_bug_confirmation
from scripts.ci_executor import execute


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--text", required=True)
    parser.add_argument("--user-id", required=True)
    parser.add_argument("--conversation-id", required=True)
    parser.add_argument("--request-id")
    parser.add_argument("--confirmed", action="store_true")
    parser.add_argument("--confirm-token")
    parser.add_argument("--no-wait-result", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    command = _confirmation_command(args)
    action = _action(args.text) if command is None else command.action
    if command is None and action == "unknown_intent":
        result = CiResult(success=False, code="unknown_intent", message="没判断出是执行 Jenkins 还是创建 bug，请补充说明。")
    else:
        command = command or _command(args, action)
        result = execute(command)
        write_audit(command, result)
    print_json({"reply": _reply(result), "result": result.model_dump(exclude_none=True)})
    return 0


def _confirmation_command(args: argparse.Namespace) -> CiCommand | None:
    if not _is_confirmation(args.text) or args.confirm_token:
        return None
    bug_data = find_pending_bug_confirmation(args.user_id, args.conversation_id)
    if bug_data:
        return CiCommand(
            conversation_id=args.conversation_id,
            user_id=args.user_id,
            action="bug.create",
            text=args.text,
            params=dict(bug_data.get("fields") or {}),
            source={"platform": "dingtalk", "conversation_id": args.conversation_id, "reporter_user_id": args.user_id},
            confirmed=True,
            confirm_token=bug_data["token"],
            wait_result=True,
        )
    data = find_pending_confirmation(args.user_id, args.conversation_id)
    if not data:
        return None
    params = dict(data.get("parameters") or {})
    if data.get("env"):
        params["env"] = data["env"]
    if data.get("branch"):
        params["branch"] = data["branch"]
    return CiCommand(
        conversation_id=args.conversation_id,
        user_id=args.user_id,
        action="jenkins.trigger",
        job=data["job"],
        text=args.text,
        params=params,
        source={"platform": "dingtalk", "conversation_id": args.conversation_id, "reporter_user_id": args.user_id},
        confirmed=True,
        confirm_token=data["token"],
        wait_result=bool(data.get("wait_result", True)),
    )


def _is_confirmation(text: str) -> bool:
    normalized = re.sub(r"\s+", "", text.strip().lower())
    return normalized in {"确认", "确定", "yes", "y", "ok", "确认创建", "继续创建", "确认提交"}


def _command(args: argparse.Namespace, action: str) -> CiCommand:
    payload = dict(
        conversation_id=args.conversation_id,
        user_id=args.user_id,
        action=action,
        text=args.text,
        params=_params(args.text, action),
        source={"platform": "dingtalk", "conversation_id": args.conversation_id, "reporter_user_id": args.user_id},
        confirmed=args.confirmed,
        confirm_token=args.confirm_token,
        wait_result=not args.no_wait_result,
    )
    if action == "jenkins.trigger":
        payload["job"] = _job(args.text)
    if args.request_id:
        payload["request_id"] = args.request_id
    return CiCommand(**payload)


def _action(text: str) -> str:
    lowered = text.lower()
    bug_words = ["bug", "缺陷", "问题单", "teambition", "创建问题", "提交问题"]
    jenkins_words = ["jenkins", "ci", "流水线", "自动化", "冒烟", "接口测试", "构建", "跑一下", "执行", "触发"]
    query_words = ["查询", "查一下", "结果", "状态", "链接", "刚才", "跑完"]
    trigger_words = ["执行", "触发", "跑一下", "构建"]
    bug_create_words = ["创建", "新建", "提交", "提bug", "提个bug", "提缺陷", "创建缺陷", "创建bug"]
    bug_query = any(word in lowered for word in ["刚才", "查询", "查一下", "结果", "状态", "链接发"])
    if any(word.lower() in lowered for word in bug_words) and any(word in lowered for word in bug_create_words):
        return "bug.create"
    if any(word.lower() in lowered for word in bug_words) and bug_query:
        return "bug.query"
    if any(word.lower() in lowered for word in jenkins_words) and any(word in lowered for word in trigger_words):
        return "jenkins.trigger"
    if any(word in lowered for word in query_words) and any(word.lower() in lowered for word in jenkins_words + ["跑完", "构建结果"]):
        return "jenkins.query"
    if any(word.lower() in lowered for word in bug_words):
        return "bug.create"
    if any(word.lower() in lowered for word in jenkins_words):
        return "jenkins.trigger"
    return "unknown_intent"


def _params(text: str, action: str) -> dict[str, str]:
    if action != "jenkins.trigger":
        return {}
    params: dict[str, str] = {}
    env = _match(text, [r"(?:环境|env)\s*[:：=]?\s*([a-zA-Z0-9_-]+)", r"\b(test|pre|stage|uat|prod)\b"])
    branch = _match(text, [r"(?:分支|branch)\s*[:：=]?\s*([a-zA-Z0-9._/-]+)"])
    if env:
        params["env"] = env
    if branch:
        params["branch"] = branch
    return params


def _job(text: str) -> str:
    configured_jobs = _jobs()
    for job in configured_jobs:
        if job.lower() in text.lower():
            return job
    if "api-auto-test" in configured_jobs and any(word in text.lower() for word in ["api", "接口"]):
        return "api-auto-test"
    return "ci_test" if "ci_test" in configured_jobs else next(iter(configured_jobs), "")


def _jobs() -> dict:
    config = jobs_config()
    return config.get("jobs", config)


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
        lines = [result.message]
        if result.task_id:
            lines.append(f"任务：{result.task_id}")
        if result.bug_url:
            lines.append(f"链接：{result.bug_url}")
        return "\n".join(lines)
    if result.code == "needs_confirmation":
        if result.preview.get("action") == "bug.create":
            return _bug_preview(result)
        return _jenkins_preview(result, "触发 Jenkins 前需要确认。请回复“确认”后继续。")
    if result.code in {"triggered", "build_success", "build_finished"}:
        return _jenkins_preview(result, result.message)
    if result.success and result.code == "created":
        title = result.extracted.get("title") or "缺陷"
        link = result.bug_url or (f"https://www.teambition.com/task/{result.task_id}" if result.task_id else "")
        return f"已创建 Teambition 缺陷：{title}\n链接：{link}".strip()
    if result.code == "missing_fields":
        return f"还缺少：{', '.join(_field_label(name) for name in result.missing_fields)}。请补充后我继续创建。"
    return result.message


def _bug_preview(result: CiResult) -> str:
    lines = ["创建 Teambition 缺陷前需要确认。请回复“确认”后继续。"]
    preview = result.preview
    if preview.get("title"):
        lines.append(f"标题：{preview['title']}")
    if preview.get("executor"):
        lines.append(f"执行者：{preview['executor']}")
    if preview.get("severity"):
        lines.append(f"严重程度：{preview['severity']}")
    if preview.get("priority") is not None:
        lines.append(f"优先级：{preview['priority']}")
    if preview.get("sprint"):
        lines.append(f"迭代：{preview['sprint']}")
    if preview.get("due_time"):
        lines.append(f"截止时间：{preview['due_time']}")
    return "\n".join(lines)


def _jenkins_preview(result: CiResult, first_line: str) -> str:
    lines = [first_line]
    if result.job:
        lines.append(f"任务：{result.job}")
    if result.params.get("env"):
        lines.append(f"环境：{result.params['env']}")
    if result.params.get("branch"):
        lines.append(f"分支：{result.params['branch']}")
    if result.build_status:
        lines.append(f"状态：{result.build_status}")
    if result.build_url:
        lines.append(f"链接：{result.build_url}")
    return "\n".join(lines)


def _field_label(name: str) -> str:
    return {
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
        "project_id": "项目",
        "tasklist_id": "任务分组",
    }.get(name, name)


def print_json(payload: dict) -> None:
    sys.stdout.buffer.write(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
    sys.stdout.buffer.write(b"\n")


if __name__ == "__main__":
    raise SystemExit(main())
