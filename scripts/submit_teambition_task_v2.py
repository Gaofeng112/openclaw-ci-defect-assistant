import argparse
import json
import sys
from uuid import uuid4
from os import getenv
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.tools.teambition_payload import build_v2_task_payload, load_evidence


TASK_CREATE_PATH = "/api/v2/tasks"
SKIP_HEADERS = {"host", "content-length", "accept-encoding", "connection"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Submit a Teambition /api/v2/tasks payload with an explicit confirmation gate.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--payload-json", help="Prepared /api/v2/tasks payload JSON")
    source.add_argument("--fields-json", help="Unified bug fields JSON; requires --evidence")
    parser.add_argument(
        "--evidence",
        default="runtime/teambition_har/teambition_v4.teambition-fields.json",
        help="Sanitized HAR extraction JSON used when --fields-json is provided",
    )
    auth = parser.add_mutually_exclusive_group(required=True)
    auth.add_argument("--auth-har", help="Local HAR file containing a successful POST /api/v2/tasks request")
    auth.add_argument("--headers-json", help="Local JSON file containing request headers, for example Cookie")
    parser.add_argument("--cookie-env", default="TEAMBITION_WEB_COOKIE", help="Optional env var that supplies the Cookie header")
    parser.add_argument("--base-url", default="https://www.teambition.com", help="Teambition web base URL")
    parser.add_argument("--confirm", action="store_true", help="Actually create the task. Without this flag no request is sent.")
    parser.add_argument("--out", help="Optional response JSON output file")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = load_payload(args)
    headers = load_headers(args)
    endpoint = args.base_url.rstrip("/") + TASK_CREATE_PATH

    if not args.confirm:
        return write_result(args.out, {
            "success": False,
            "code": "dry_run",
            "message": "Prepared payload only. Re-run with --confirm to create a real Teambition task.",
            "endpoint": endpoint,
            "auth_ready": has_auth_header(headers),
            "header_names": sorted(headers),
            "payload_summary": payload_summary(payload),
        })

    if not has_auth_header(headers):
        return write_result(args.out, {
            "success": False,
            "code": "missing_auth_header",
            "message": "No Cookie or Authorization header found. Provide --headers-json or set TEAMBITION_WEB_COOKIE before using --confirm.",
            "endpoint": endpoint,
            "header_names": sorted(headers),
        })

    response = httpx.post(endpoint, headers=headers, json=payload, timeout=30, follow_redirects=False, trust_env=False)
    data = response_json(response)
    return write_result(args.out, {
        "success": 200 <= response.status_code < 300,
        "code": "submitted" if 200 <= response.status_code < 300 else "teambition_error",
        "endpoint": endpoint,
        "status_code": response.status_code,
        "response": data,
    })


def load_payload(args: argparse.Namespace) -> dict[str, Any]:
    if args.payload_json:
        return json.loads(Path(args.payload_json).read_text(encoding="utf-8-sig"))
    fields = json.loads(Path(args.fields_json).read_text(encoding="utf-8-sig"))
    return build_v2_task_payload(fields, load_evidence(args.evidence))


def load_headers(args: argparse.Namespace) -> dict[str, str]:
    headers = load_headers_from_json(args.headers_json) if args.headers_json else load_headers_from_har(args.auth_har)
    cookie = getenv(args.cookie_env, "").strip()
    if cookie:
        headers["Cookie"] = cookie
    headers["Content-Type"] = "application/json"
    headers.setdefault("x-request-id", uuid4().hex)
    return headers


def load_headers_from_json(path: str) -> dict[str, str]:
    raw = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(raw, dict):
        raise ValueError("--headers-json must contain a JSON object")
    return {str(key): str(value) for key, value in raw.items() if value not in (None, "")}


def load_headers_from_har(path: str) -> dict[str, str]:
    har = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    for entry in har.get("log", {}).get("entries", []):
        request = entry.get("request") or {}
        if request.get("method", "").upper() != "POST":
            continue
        if urlparse(request.get("url") or "").path != TASK_CREATE_PATH:
            continue
        headers = {}
        for item in request.get("headers") or []:
            name = item.get("name")
            value = item.get("value")
            if not name or value is None:
                continue
            lowered = name.lower()
            if lowered in SKIP_HEADERS or lowered.startswith(":"):
                continue
            headers[name] = value
        cookies = request.get("cookies") or []
        if cookies and "Cookie" not in headers:
            headers["Cookie"] = "; ".join(f"{item.get('name')}={item.get('value')}" for item in cookies if item.get("name"))
        if headers:
            return headers
    raise ValueError(f"no POST {TASK_CREATE_PATH} request found in HAR")


def has_auth_header(headers: dict[str, str]) -> bool:
    lowered = {key.lower() for key in headers}
    return "cookie" in lowered or "authorization" in lowered


def payload_summary(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "content": payload.get("content"),
        "_projectId": payload.get("_projectId"),
        "_tasklistId": payload.get("_tasklistId"),
        "_scenariofieldconfigId": payload.get("_scenariofieldconfigId"),
        "_taskflowstatusId": payload.get("_taskflowstatusId"),
        "_executorId": payload.get("_executorId"),
        "_sprintId": payload.get("_sprintId"),
        "startDate": payload.get("startDate"),
        "dueDate": payload.get("dueDate"),
        "priority": payload.get("priority"),
        "customfields": len(payload.get("customfields") or []),
    }


def response_json(response: httpx.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        return response.text[:1000]


def write_result(path: str | None, result: dict[str, Any]) -> int:
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if path:
        Path(path).write_text(text + "\n", encoding="utf-8")
    sys.stdout.buffer.write(text.encode("utf-8"))
    sys.stdout.buffer.write(b"\n")
    return 0 if result.get("success") or result.get("code") == "dry_run" else 1


if __name__ == "__main__":
    raise SystemExit(main())
