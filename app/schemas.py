from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class JenkinsTriggerRequest(BaseModel):
    user_id: str = Field(..., examples=["u001"])
    job: str = Field(..., examples=["ci_test"])
    env: str | None = Field(None, examples=["test"])
    branch: str | None = Field(None, examples=["main"])
    parameters: dict[str, Any] = Field(default_factory=dict)
    confirmed: bool = False


class JenkinsTriggerResponse(BaseModel):
    success: bool
    message: str
    build_url: str | None = None
    needs_confirmation: bool = False


class JenkinsNaturalLanguageRequest(BaseModel):
    user_id: str = Field(..., examples=["u001"])
    conversation_id: str | None = Field(None, examples=["ding-group-001"])
    text: str = Field(..., examples=["确认执行 ci_test，环境 test，分支 main"])


class JenkinsNaturalLanguageResponse(BaseModel):
    success: bool
    message: str
    reply: str
    conversation_id: str
    extracted: dict[str, Any] = Field(default_factory=dict)
    missing_fields: list[str] = Field(default_factory=list)
    build_url: str | None = None
    needs_confirmation: bool = False


class AssistantChatRequest(JenkinsNaturalLanguageRequest):
    pass


class AssistantChatResponse(JenkinsNaturalLanguageResponse):
    pass


class DingTalkCallbackRequest(BaseModel):
    senderId: str | None = None
    senderStaffId: str | None = None
    conversationId: str | None = None
    text: dict[str, Any] | None = None
    msgtype: str | None = None


class DingTalkCallbackResponse(BaseModel):
    msgtype: str = "text"
    text: dict[str, str]


class BugCreateRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    user_id: str = Field(..., examples=["u001"])
    title: str | None = Field(None, examples=["登录失败"])
    project_id: str | None = None
    tasklist_id: str | None = None
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
    bug_url: str | None = None
    missing_fields: list[str] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: Literal["ok"]
