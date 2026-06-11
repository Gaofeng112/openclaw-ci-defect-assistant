import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.executor import run_request


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--request-file")
    source.add_argument("--request-json")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    return run_request(args.request_file, args.request_json)


if __name__ == "__main__":
    raise SystemExit(main())
