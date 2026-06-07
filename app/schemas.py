from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


class CiCommand(BaseModel):
    request_id: str = Field(default_factory=lambda: uuid4().hex)
    conversation_id: str | None = None
    user_id: str = Field(..., examples=["u001"])
    action: Literal["jenkins.trigger", "jenkins.query", "bug.create", "bug.query"] = "jenkins.trigger"
    job: str | None = Field(None, examples=["ci_test"])
    text: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)
    source: dict[str, Any] = Field(default_factory=dict)
    confirmed: bool = False
    confirm_token: str | None = None
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
    confirm_token: str | None = None
    expires_in_seconds: int | None = None
    preview: dict[str, Any] = Field(default_factory=dict)
    build_number: int | None = None
    build_url: str | None = None
    build_status: str | None = None
    duration_seconds: int | None = None
    summary: str | None = None
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
    confirm_token: str | None = None
    wait_result: bool = False


class JenkinsTriggerResponse(BaseModel):
    success: bool
    message: str
    code: str = "failed"
    build_url: str | None = None
    build_status: str | None = None
    build_number: int | None = None
    duration_seconds: int | None = None
    summary: str | None = None
    needs_confirmation: bool = False
    confirm_token: str | None = None
    expires_in_seconds: int | None = None
    preview: dict[str, Any] = Field(default_factory=dict)


class BugCreateRequest(BaseModel):
    user_id: str = Field(..., examples=["u001"])
    conversation_id: str | None = None
    text: str | None = None
    fields: dict[str, Any] = Field(default_factory=dict)
    source: dict[str, Any] = Field(default_factory=dict)


class BugCreateResponse(BaseModel):
    success: bool
    message: str
    code: str = "failed"
    bug_url: str | None = None
    task_id: str | None = None
    missing_fields: list[str] = Field(default_factory=list)
    fields: dict[str, Any] = Field(default_factory=dict)
