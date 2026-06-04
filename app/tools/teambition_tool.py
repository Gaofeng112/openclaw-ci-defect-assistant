from uuid import uuid4

from app.schemas import BugCreateRequest, BugCreateResponse


def create_bug(request: BugCreateRequest) -> BugCreateResponse:
    bug_id = uuid4().hex[:8]
    return BugCreateResponse(
        success=True,
        message="已模拟创建 Teambition 缺陷",
        bug_url=f"http://fake-teambition/bug/{bug_id}",
    )
