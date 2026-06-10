import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.tools.teambition_payload import build_v2_task_payload, load_evidence


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a Teambition /api/v2/tasks payload without sending it.")
    parser.add_argument("--fields-json", required=True, help="JSON file containing unified bug fields")
    parser.add_argument(
        "--evidence",
        default="runtime/teambition_har/teambition_v4.teambition-fields.json",
        help="Sanitized HAR extraction JSON containing a captured /api/v2/tasks payload",
    )
    parser.add_argument("--out", help="Optional output JSON file")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    fields = json.loads(Path(args.fields_json).read_text(encoding="utf-8-sig"))
    evidence = load_evidence(args.evidence)
    payload = build_v2_task_payload(fields, evidence)
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    else:
        sys.stdout.buffer.write(text.encode("utf-8"))
        sys.stdout.buffer.write(b"\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
