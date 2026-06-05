from uuid import uuid4

from app.config import bug_fields_config
from app.schemas import BugCreateRequest, BugCreateResponse


def _request_data(request: BugCreateRequest) -> dict:
    data = request.model_dump()
    data.update(request.model_extra or {})
    return data


def _missing_required_fields(request: BugCreateRequest) -> list[str]:
    data = _request_data(request)
    required_fields = bug_fields_config().get("required_fields", [])
    return [field for field in required_fields if not data.get(field)]


def _missing_message(missing_fields: list[str]) -> str:
    return f"缺少 {', '.join(missing_fields)}，请补充"


def create_bug(request: BugCreateRequest) -> BugCreateResponse:
    missing_fields = _missing_required_fields(request)
    if missing_fields:
        return BugCreateResponse(
            success=False,
            message=_missing_message(missing_fields),
            missing_fields=missing_fields,
        )

    bug_id = uuid4().hex[:8]
    return BugCreateResponse(
        success=True,
        message="已模拟创建 Teambition 缺陷",
        bug_url=f"http://fake-teambition/bug/{bug_id}",
    )
