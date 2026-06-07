import time
from os import getenv
from urllib.parse import quote
from uuid import uuid4

import httpx

from app.auth import can_trigger_job
from app.config import jenkins_settings, jobs_config
from app.schemas import JenkinsTriggerRequest, JenkinsTriggerResponse


def _jobs() -> dict:
    config = jobs_config()
    return config.get("jobs", config)


def _job_config(job: str) -> dict | None:
    return _jobs().get(job)


def _param_value(request: JenkinsTriggerRequest, name: str):
    if name in {"job", "env", "branch"}:
        return getattr(request, name)
    return request.parameters.get(name)


def _missing_params(request: JenkinsTriggerRequest, required_params: list[str]) -> list[str]:
    return [name for name in required_params if not _param_value(request, name)]


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
        )
    return JenkinsTriggerResponse(
        success=True,
        message="已模拟触发 Jenkins 任务",
        code="triggered",
        build_url=build_url,
    )


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

    missing_params = _missing_params(request, job.get("required_params", []))
    if missing_params:
        return JenkinsTriggerResponse(success=False, code="missing_params", message=f"缺少 {', '.join(missing_params)} 参数")

    if request.env not in job.get("allowed_envs", []):
        return JenkinsTriggerResponse(success=False, code="invalid_env", message="环境不允许")

    if not can_trigger_job(request.user_id, job):
        return JenkinsTriggerResponse(success=False, code="unauthorized", message="无权限")

    if job.get("confirm_required", True) and not request.confirmed:
        return JenkinsTriggerResponse(success=False, code="needs_confirmation", message="触发 Jenkins 前需要确认", needs_confirmation=True)

    if _has_real_jenkins():
        return _real_trigger(request, job)

    return _mock_trigger(request)
