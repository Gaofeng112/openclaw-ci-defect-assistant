import argparse
import json
import sys
from urllib.request import Request, urlopen


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--user-id", default="u001")
    parser.add_argument("--conversation-id", required=True)
    parser.add_argument("--text", required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = json.dumps(
        {
            "user_id": args.user_id,
            "conversation_id": args.conversation_id,
            "text": args.text,
        },
        ensure_ascii=False,
    ).encode("utf-8")
    request = Request(
        f"{args.base_url.rstrip('/')}/assistant/chat",
        data=payload,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with urlopen(request, timeout=30) as response:
        data = json.loads(response.read().decode("utf-8"))

    sys.stdout.buffer.write(data.get("reply", "").encode("utf-8"))
    sys.stdout.buffer.write(b"\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
