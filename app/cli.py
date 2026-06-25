import argparse
import shutil
from typing import Any

from app.assistant import handle_chat, print_json
from app.config import BASE_DIR, CONFIG_DIR


RUNTIME_DIRS = ["runtime/requests", "runtime/audit", "runtime/confirmations", "runtime/sessions", "runtime/teambition_har"]


def main() -> int:
    args = parse_args()
    if args.command == "chat":
        print_json(handle_chat(args))
        return 0
    if args.command == "init":
        print_json(init_project())
        return 0
    if args.command == "doctor":
        result = doctor()
        print_json(result)
        return 0 if result["ok"] else 1
    parse_args(["--help"])
    return 1


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="ci-defect-assistant")
    subparsers = parser.add_subparsers(dest="command")

    chat = subparsers.add_parser("chat", help="Handle one DingTalk/OpenClaw message")
    chat.add_argument("--text", required=True)
    chat.add_argument("--user-id", required=True)
    chat.add_argument("--conversation-id", required=True)
    chat.add_argument("--request-id")
    chat.add_argument("--confirmed", action="store_true")
    chat.add_argument("--confirm-token")
    chat.add_argument("--fields-json")
    chat.add_argument("--fields-file")
    chat.add_argument("--no-wait-result", action="store_true")

    subparsers.add_parser("init", help="Create local runtime folders and .env from template")
    subparsers.add_parser("doctor", help="Check local config files and runtime folders")
    return parser.parse_args(argv)


def init_project() -> dict[str, Any]:
    for item in RUNTIME_DIRS:
        (BASE_DIR / item).mkdir(parents=True, exist_ok=True)
    env_path = BASE_DIR / ".env"
    if not env_path.exists() and (BASE_DIR / ".env.example").exists():
        shutil.copyfile(BASE_DIR / ".env.example", env_path)
    return {"ok": True, "base_dir": str(BASE_DIR), "runtime_dirs": RUNTIME_DIRS, "env_created": env_path.exists()}


def doctor() -> dict[str, Any]:
    required = [
        CONFIG_DIR / "jobs.yaml",
        CONFIG_DIR / "users.yaml",
        CONFIG_DIR / "teambition.yaml",
        CONFIG_DIR / "teambition_bug_form.v1.yaml",
        BASE_DIR / ".env.example",
    ]
    missing = [str(path.relative_to(BASE_DIR)) for path in required if not path.exists()]
    return {
        "ok": not missing,
        "base_dir": str(BASE_DIR),
        "missing": missing,
        "runtime_dirs": [item for item in RUNTIME_DIRS if (BASE_DIR / item).exists()],
    }

if __name__ == "__main__":
    raise SystemExit(main())
