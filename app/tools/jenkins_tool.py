from uuid import uuid4

from app.auth import has_any_role
from app.config import jobs_config
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


def trigger_job(request: JenkinsTriggerRequest) -> JenkinsTriggerResponse:
    job = _job_config(request.job)
    if not job:
        return JenkinsTriggerResponse(success=False, message="不允许触发该任务")

    missing_params = _missing_params(request, job.get("required_params", []))
    if missing_params:
        return JenkinsTriggerResponse(success=False, message=f"缺少 {', '.join(missing_params)} 参数")

    if request.env not in job.get("allowed_envs", []):
        return JenkinsTriggerResponse(success=False, message="环境不允许")

    if not has_any_role(request.user_id, job.get("allowed_roles", [])):
        return JenkinsTriggerResponse(success=False, message="无权限")

    build_id = uuid4().hex[:8]
    return JenkinsTriggerResponse(
        success=True,
        message="已模拟触发 Jenkins 任务",
        build_url=f"http://fake-jenkins/job/{request.job}/{build_id}",
    )
