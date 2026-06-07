import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.config import jobs_config
from app.schemas import CiCommand, CiResult
from scripts.ci_executor import execute


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--text", required=True)
    parser.add_argument("--user-id", required=True)
    parser.add_argument("--conversation-id", required=True)
    parser.add_argument("--request-id")
    parser.add_argument("--confirmed", action="store_true")
    parser.add_argument("--no-wait-result", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    action = _action(args.text)
    if action == "unknown_intent":
        result = CiResult(success=False, code="unknown_intent", message="没判断出是执行 Jenkins 还是创建 bug，请补充说明。")
    else:
        result = execute(_command(args, action))
    print_json({"reply": _reply(result), "result": result.model_dump(exclude_none=True)})
    return 0


def _command(args: argparse.Namespace, action: str) -> CiCommand:
    payload = dict(
        conversation_id=args.conversation_id,
        user_id=args.user_id,
        action=action,
        text=args.text,
        params=_params(args.text, action),
        confirmed=args.confirmed,
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
    if result.code == "needs_confirmation":
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
        "module": "模块",
        "env": "环境",
        "severity": "严重程度",
        "steps": "复现步骤",
        "expected": "预期结果",
        "actual": "实际结果",
        "project_id": "项目",
        "tasklist_id": "任务分组",
    }.get(name, name)


def print_json(payload: dict) -> None:
    sys.stdout.buffer.write(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
    sys.stdout.buffer.write(b"\n")


if __name__ == "__main__":
    raise SystemExit(main())
