from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


class CiCommand(BaseModel):
    request_id: str = Field(default_factory=lambda: uuid4().hex)
    conversation_id: str | None = None
    user_id: str = Field(..., examples=["u001"])
    action: Literal["jenkins.trigger", "bug.create"] = "jenkins.trigger"
    job: str | None = Field(None, examples=["ci_test"])
    text: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)
    confirmed: bool = False
    wait_result: bool = False


class CiResult(BaseModel):
    request_id: str | None = None
    conversation_id: str | None = None
    success: bool
    code: str
    message: str
    job: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)
    needs_confirmation: bool = False
    build_url: str | None = None
    build_status: str | None = None
    bug_url: str | None = None
    task_id: str | None = None
    missing_fields: list[str] = Field(default_factory=list)
    extracted: dict[str, Any] = Field(default_factory=dict)


class JenkinsTriggerRequest(BaseModel):
    user_id: str = Field(..., examples=["u001"])
    job: str = Field(..., examples=["ci_test"])
    env: str | None = Field(None, examples=["test"])
    branch: str | None = Field(None, examples=["main"])
    parameters: dict[str, Any] = Field(default_factory=dict)
    confirmed: bool = False
    wait_result: bool = False


class JenkinsTriggerResponse(BaseModel):
    success: bool
    message: str
    code: str = "failed"
    build_url: str | None = None
    build_status: str | None = None
    needs_confirmation: bool = False


class BugCreateRequest(BaseModel):
    user_id: str = Field(..., examples=["u001"])
    conversation_id: str | None = None
    text: str | None = None
    fields: dict[str, Any] = Field(default_factory=dict)


class BugCreateResponse(BaseModel):
    success: bool
    message: str
    code: str = "failed"
    bug_url: str | None = None
    task_id: str | None = None
    missing_fields: list[str] = Field(default_factory=list)
    fields: dict[str, Any] = Field(default_factory=dict)
