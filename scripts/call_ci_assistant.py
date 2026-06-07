import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.schemas import CiCommand, CiResult
from scripts.ci_executor import execute


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--text", required=True)
    parser.add_argument("--user-id", required=True)
    parser.add_argument("--conversation-id", required=True)
    parser.add_argument("--request-id")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = execute(_command(args))
    print_json({"reply": _reply(result), "result": result.model_dump(exclude_none=True)})
    return 0


def _command(args: argparse.Namespace) -> CiCommand:
    payload = dict(
        conversation_id=args.conversation_id,
        user_id=args.user_id,
        action=_action(args.text),
        text=args.text,
        params={},
    )
    if args.request_id:
        payload["request_id"] = args.request_id
    return CiCommand(**payload)


def _action(text: str) -> str:
    bug_words = ["bug", "缺陷", "问题单", "teambition"]
    if any(word.lower() in text.lower() for word in bug_words):
        return "bug.create"
    return "bug.create"


def _reply(result: CiResult) -> str:
    if result.success and result.code == "created":
        title = result.extracted.get("title") or "缺陷"
        link = result.bug_url or (f"https://www.teambition.com/task/{result.task_id}" if result.task_id else "")
        return f"已创建 Teambition 缺陷：{title}\n链接：{link}".strip()
    if result.code == "missing_fields":
        return f"还缺少：{', '.join(_field_label(name) for name in result.missing_fields)}。请补充后我继续创建。"
    return result.message


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
