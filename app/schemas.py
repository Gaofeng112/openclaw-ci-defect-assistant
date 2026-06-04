from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class JenkinsTriggerRequest(BaseModel):
    user_id: str = Field(..., examples=["u001"])
    job: str = Field(..., examples=["smoke"])
    env: str | None = Field(None, examples=["test"])
    branch: str | None = Field(None, examples=["release/1.0.0"])
    parameters: dict[str, Any] = Field(default_factory=dict)


class JenkinsTriggerResponse(BaseModel):
    success: bool
    message: str
    build_url: str | None = None


class BugCreateRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    user_id: str = Field(..., examples=["u001"])
    title: str = Field(..., examples=["登录失败"])
    description: str | None = None
    module: str | None = Field(None, examples=["auth"])
    severity: str | None = Field(None, examples=["P2"])
    env: str | None = Field(None, examples=["test"])
    steps: str | None = None
    expected: str | None = None
    actual: str | None = None
    reproduce_steps: str | None = None
    extra_fields: dict[str, Any] = Field(default_factory=dict)


class BugCreateResponse(BaseModel):
    success: bool
    message: str
    bug_url: str


class HealthResponse(BaseModel):
    status: Literal["ok"]
