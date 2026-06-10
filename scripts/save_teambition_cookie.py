import argparse
import json
import sys
import time
from pathlib import Path

from playwright.sync_api import Error, sync_playwright


DEFAULT_URL = "https://www.teambition.com/"
DEFAULT_OUT = "runtime/teambition_har/teambition_headers.json"
DEFAULT_PROFILE = "runtime/teambition_browser_profile"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Open Teambition for manual login and save cookies as a local headers JSON file.")
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--out", default=DEFAULT_OUT)
    parser.add_argument("--profile-dir", default=DEFAULT_PROFILE)
    parser.add_argument("--timeout-seconds", type=int, default=900)
    parser.add_argument("--channel", choices=["chrome", "msedge"], help="Browser channel. Defaults to Chrome, then Edge fallback.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    profile_dir = Path(args.profile_dir)
    profile_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as playwright:
        context = launch_context(playwright, args, profile_dir)
        page = context.pages[0] if context.pages else context.new_page()
        page.goto(args.url, wait_until="domcontentloaded")
        print("Opened Teambition. Please log in in the browser window; cookies will be saved automatically after login.")
        deadline = time.time() + args.timeout_seconds
        while time.time() < deadline:
            if is_logged_in(page):
                time.sleep(3)
                cookies = context.cookies(["https://www.teambition.com"])
                teambition_cookies = [item for item in cookies if "teambition.com" in item.get("domain", "")]
                if teambition_cookies:
                    headers = build_headers(page, teambition_cookies)
                    out.write_text(json.dumps(headers, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                    print(json.dumps({
                        "success": True,
                        "out": str(out),
                        "cookie_count": len(teambition_cookies),
                        "header_names": sorted(headers),
                    }, ensure_ascii=False))
                    context.close()
                    return 0
            time.sleep(2)
        context.close()
    print(json.dumps({"success": False, "code": "login_timeout", "message": "Timed out waiting for Teambition login."}, ensure_ascii=False))
    return 1


def launch_context(playwright, args: argparse.Namespace, profile_dir: Path):
    channels = [args.channel] if args.channel else ["chrome", "msedge"]
    last_error: Exception | None = None
    for channel in channels:
        try:
            return playwright.chromium.launch_persistent_context(
                str(profile_dir),
                channel=channel,
                headless=False,
                viewport=None,
                args=["--start-maximized"],
            )
        except Error as exc:
            last_error = exc
    raise RuntimeError(f"Could not launch Chrome or Edge through Playwright: {last_error}")


def is_logged_in(page) -> bool:
    url = page.url.lower()
    return "teambition.com" in url and "login" not in url and "account.teambition" not in url


def build_headers(page, cookies: list[dict]) -> dict[str, str]:
    cookie_header = "; ".join(f"{item['name']}={item['value']}" for item in cookies if item.get("name"))
    user_agent = page.evaluate("navigator.userAgent")
    referer = page.url if "teambition.com" in page.url else DEFAULT_URL
    return {
        "Cookie": cookie_header,
        "accept": "application/json, text/plain, */*",
        "origin": "https://www.teambition.com",
        "referer": referer,
        "user-agent": user_agent,
        "x-timezone": "Asia/Shanghai",
    }


if __name__ == "__main__":
    sys.exit(main())
