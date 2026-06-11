import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.assistant import handle_chat, print_json


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
    print_json(handle_chat(parse_args()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
