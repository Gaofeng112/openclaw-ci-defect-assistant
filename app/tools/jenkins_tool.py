import hashlib
import json
import re
import time
from os import getenv
from pathlib import Path
from urllib.parse import quote
from uuid import uuid4

import httpx

from app.auth import can_trigger_job
from app.config import jenkins_settings, jobs_config
from app.schemas import JenkinsTriggerRequest, JenkinsTriggerResponse

CONFIRM_TTL_SECONDS = 300
CONFIRM_DIR = Path(__file__).resolve().parent.parent.parent / "runtime" / "confirmations"


def _jobs() -> dict:
    config = jobs_config()
    return config.get("jobs", config)


def _job_config(job: str) -> dict | None:
    return _jobs().get(job)


def _param_value(request: JenkinsTriggerRequest, name: str):
    if name in {"job", "env", "branch"}:
        return getattr(request, name)
    return request.parameters.get(name)


def _configured_params(job: dict) -> dict:
    return dict(job.get("params") or {})


def _with_defaults(request: JenkinsTriggerRequest, job: dict) -> JenkinsTriggerRequest:
    params = dict(request.parameters)
    env = request.env
    branch = request.branch
    for name, config in _configured_params(job).items():
        default = config.get("default")
        if name == "env" and not env and default is not None:
            env = str(default)
        elif name == "branch" and not branch and default is not None:
            branch = str(default)
        elif not params.get(name) and default is not None:
            params[name] = default
    return request.model_copy(update={"env": env, "branch": branch, "parameters": params})


def _validate_params(request: JenkinsTriggerRequest, job: dict) -> JenkinsTriggerResponse | None:
    configured_names = set(_configured_params(job))
    for name in _build_parameters(request):
        if name not in configured_names:
            return JenkinsTriggerResponse(success=False, code="invalid_param", message=f"{name} 参数不允许")
    for name, config in _configured_params(job).items():
        value = _param_value(request, name)
        if config.get("required") and not value:
            return JenkinsTriggerResponse(success=False, code="missing_params", message=f"缺少 {name} 参数")
        if value is None or value == "":
            continue
        allowed = config.get("allowed")
        if allowed and str(value) not in [str(item) for item in allowed]:
            code = "invalid_env" if name == "env" else "invalid_param"
            return JenkinsTriggerResponse(success=False, code=code, message=f"{name} 参数不允许")
        pattern = config.get("pattern")
        if pattern and not re.fullmatch(str(pattern), str(value)):
            return JenkinsTriggerResponse(success=False, code="invalid_param", message=f"{name} 参数格式不正确")
    return None


def _build_parameters(request: JenkinsTriggerRequest) -> dict:
    params = dict(request.parameters)
    params.update({"env": request.env, "branch": request.branch})
    return {key: value for key, value in params.items() if value is not None}


def _jenkins_job_url(base_url: str, job_path: str) -> str:
    parts = [quote(part, safe="") for part in job_path.strip("/").split("/") if part]
    return f"{base_url}/" + "/".join(f"job/{part}" for part in parts)


def _jenkins_auth(settings: dict[str, str]):
    if settings["user"] and settings["token"]:
        return (settings["user"], settings["token"])
    return None


def _crumb_headers(client: httpx.Client, base_url: str, auth) -> dict[str, str]:
    try:
        response = client.get(f"{base_url}/crumbIssuer/api/json", auth=auth)
        if response.status_code != 200:
            return {}
        data = response.json()
        return {data["crumbRequestField"]: data["crumb"]}
    except (httpx.HTTPError, KeyError, ValueError):
        return {}


def _mock_trigger(request: JenkinsTriggerRequest) -> JenkinsTriggerResponse:
    build_id = uuid4().hex[:8]
    build_url = f"http://fake-jenkins/job/{request.job}/{build_id}"
    if request.wait_result:
        return JenkinsTriggerResponse(
            success=True,
            message="模拟 Jenkins 任务执行完成: SUCCESS",
            code="build_success",
            build_url=build_url,
            build_status="SUCCESS",
            summary="mock build success",
        )
    return JenkinsTriggerResponse(
        success=True,
        message="已模拟触发 Jenkins 任务",
        code="triggered",
        build_url=build_url,
    )


def _request_hash(request: JenkinsTriggerRequest) -> str:
    payload = {
        "user_id": request.user_id,
        "job": request.job,
        "env": request.env,
        "branch": request.branch,
        "parameters": request.parameters,
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _token_path(token: str) -> Path:
    return CONFIRM_DIR / f"{token}.json"


def _create_confirmation(request: JenkinsTriggerRequest) -> str:
    token = f"confirm_{uuid4().hex}"
    CONFIRM_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "token": token,
        "request_hash": _request_hash(request),
        "user_id": request.user_id,
        "expires_at": int(time.time()) + CONFIRM_TTL_SECONDS,
        "used": False,
    }
    _token_path(token).write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return token


def _consume_confirmation(request: JenkinsTriggerRequest) -> JenkinsTriggerResponse | None:
    if not request.confirm_token:
        return JenkinsTriggerResponse(success=False, code="missing_confirm_token", message="缺少确认 token")
    path = _token_path(request.confirm_token)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return JenkinsTriggerResponse(success=False, code="invalid_confirm_token", message="确认 token 无效")

    if data.get("used"):
        return JenkinsTriggerResponse(success=False, code="invalid_confirm_token", message="确认 token 已使用")
    if int(data.get("expires_at", 0)) < int(time.time()):
        path.unlink(missing_ok=True)
        return JenkinsTriggerResponse(success=False, code="expired_confirm_token", message="确认 token 已过期")
    if data.get("user_id") != request.user_id or data.get("request_hash") != _request_hash(request):
        return JenkinsTriggerResponse(success=False, code="invalid_confirm_token", message="确认 token 与请求不匹配")

    data["used"] = True
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    path.unlink(missing_ok=True)
    return None


def _real_trigger(request: JenkinsTriggerRequest, job: dict) -> JenkinsTriggerResponse:
    settings = jenkins_settings()
    job_url = _jenkins_job_url(settings["base_url"], job["job_path"])
    auth = _jenkins_auth(settings)

    try:
        with httpx.Client(timeout=20, trust_env=False) as client:
            headers = _crumb_headers(client, settings["base_url"], auth)
            response = client.post(
                f"{job_url}/buildWithParameters",
                auth=auth,
                headers=headers,
                params=_build_parameters(request),
            )

            if response.status_code in {200, 201, 202, 302}:
                build_url = response.headers.get("Location") or job_url
                if request.wait_result:
                    return _wait_for_build_result(client, build_url, auth)
                return JenkinsTriggerResponse(
                    success=True,
                    message="已触发真实 Jenkins 任务",
                    build_url=build_url,
                )
    except httpx.HTTPError as exc:
        return JenkinsTriggerResponse(success=False, code="jenkins_connection_failed", message=f"Jenkins 连接失败: {exc}")

    return JenkinsTriggerResponse(success=False, code="jenkins_http_error", message=f"Jenkins 触发失败: HTTP {response.status_code}")


def _api_url(url: str) -> str:
    return f"{url.rstrip('/')}/api/json"


def _get_json(client: httpx.Client, url: str, auth) -> dict:
    response = client.get(url, auth=auth)
    response.raise_for_status()
    return response.json()


def _wait_for_queue_executable(client: httpx.Client, queue_url: str, auth, deadline: float) -> str | None:
    while time.monotonic() < deadline:
        data = _get_json(client, _api_url(queue_url), auth)
        executable = data.get("executable") or {}
        if executable.get("url"):
            return executable["url"]
        if data.get("cancelled"):
            return None
        time.sleep(3)
    return None


def _wait_for_build_result(client: httpx.Client, build_url: str, auth, timeout_seconds: int = 180) -> JenkinsTriggerResponse:
    deadline = time.monotonic() + timeout_seconds
    try:
        if "/queue/item/" in build_url:
            executable_url = _wait_for_queue_executable(client, build_url, auth, deadline)
            if not executable_url:
                return JenkinsTriggerResponse(
                    success=False,
                    code="queue_timeout",
                    message="Jenkins 任务已触发，但等待队列分配构建号超时或被取消",
                    build_url=build_url,
                )
            build_url = executable_url

        while time.monotonic() < deadline:
            data = _get_json(client, _api_url(build_url), auth)
            if not data.get("building", False):
                status = data.get("result") or "UNKNOWN"
                return JenkinsTriggerResponse(
                    success=status == "SUCCESS",
                    code="build_success" if status == "SUCCESS" else "build_finished",
                    message=f"Jenkins 任务执行完成: {status}",
                    build_url=data.get("url") or build_url,
                    build_status=status,
                )
            time.sleep(3)
    except (httpx.HTTPError, ValueError) as exc:
        return JenkinsTriggerResponse(success=False, code="result_query_failed", message=f"Jenkins 结果查询失败: {exc}", build_url=build_url)

    return JenkinsTriggerResponse(success=False, code="build_timeout", message="Jenkins 任务已触发，但等待执行结果超时", build_url=build_url)


def _has_real_jenkins() -> bool:
    if getenv("JENKINS_MOCK") == "1":
        return False
    settings = jenkins_settings()
    return bool(settings["base_url"] and settings["user"] and settings["token"])


def trigger_job(request: JenkinsTriggerRequest) -> JenkinsTriggerResponse:
    job = _job_config(request.job)
    if not job:
        return JenkinsTriggerResponse(success=False, code="invalid_job", message="不允许触发该任务")

    request = _with_defaults(request, job)
    param_error = _validate_params(request, job)
    if param_error:
        return param_error

    if not can_trigger_job(request.user_id, job):
        return JenkinsTriggerResponse(success=False, code="unauthorized", message="无权限")

    if job.get("confirm_required", True) and not request.confirmed:
        token = _create_confirmation(request)
        return JenkinsTriggerResponse(
            success=False,
            code="needs_confirmation",
            message="触发 Jenkins 前需要确认",
            needs_confirmation=True,
            confirm_token=token,
            expires_in_seconds=CONFIRM_TTL_SECONDS,
            preview={
                "action": "jenkins.trigger",
                "job": request.job,
                "params": _build_parameters(request),
            },
        )

    if job.get("confirm_required", True):
        confirmation_error = _consume_confirmation(request)
        if confirmation_error:
            return confirmation_error

    if _has_real_jenkins():
        return _real_trigger(request, job)

    return _mock_trigger(request)
