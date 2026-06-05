from fastapi import FastAPI, Response

from app.auth import get_user
from app.audit import audit_event
from app.config import assistant_settings
from app.nlp import parse_jenkins_command
from app.schemas import (
    AssistantChatRequest,
    AssistantChatResponse,
    BugCreateRequest,
    BugCreateResponse,
    DingTalkCallbackRequest,
    DingTalkCallbackResponse,
    HealthResponse,
    JenkinsNaturalLanguageRequest,
    JenkinsNaturalLanguageResponse,
    JenkinsTriggerRequest,
    JenkinsTriggerResponse,
)
from app.session_store import clear_session, get_session, update_session
from app.tools.jenkins_tool import trigger_job
from app.tools.teambition_tool import create_bug


app = FastAPI(title="OpenClaw CI Defect Assistant", version="0.1.0")


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.post("/tools/jenkins/trigger", response_model=JenkinsTriggerResponse)
def trigger_jenkins(request: JenkinsTriggerRequest) -> JenkinsTriggerResponse:
    response = trigger_job(request)
    audit_event("jenkins.trigger", request.user_id, {"request": request.model_dump(), "response": response.model_dump()})
    return response


@app.post("/assistant/jenkins/trigger", response_model=JenkinsNaturalLanguageResponse)
def trigger_jenkins_by_text(request: JenkinsNaturalLanguageRequest) -> JenkinsNaturalLanguageResponse:
    return _handle_jenkins_text(request)


@app.post("/assistant/chat", response_model=AssistantChatResponse)
def assistant_chat(request: AssistantChatRequest) -> AssistantChatResponse:
    return AssistantChatResponse(**_handle_jenkins_text(request).model_dump())


@app.get("/assistant/quick")
def assistant_quick(text: str, cid: str = "ding-demo", user_id: str = "u001") -> Response:
    request = AssistantChatRequest(user_id=user_id, conversation_id=cid, text=text)
    response = assistant_chat(request)
    return Response(content=response.reply, media_type="text/plain; charset=utf-8")


@app.post("/callbacks/dingtalk", response_model=DingTalkCallbackResponse)
def dingtalk_callback(request: DingTalkCallbackRequest) -> DingTalkCallbackResponse:
    text = (request.text or {}).get("content", "").strip()
    chat_request = AssistantChatRequest(
        user_id=_local_user_id(request),
        conversation_id=request.conversationId or request.senderId or assistant_settings()["dingtalk_default_user_id"],
        text=text,
    )
    response = assistant_chat(chat_request)
    return DingTalkCallbackResponse(text={"content": response.reply})


def _local_user_id(request: DingTalkCallbackRequest) -> str:
    candidates = [request.senderStaffId, request.senderId]
    return next((user_id for user_id in candidates if user_id and get_user(user_id)), assistant_settings()["dingtalk_default_user_id"])


def _handle_jenkins_text(request: JenkinsNaturalLanguageRequest) -> JenkinsNaturalLanguageResponse:
    conversation_id = request.conversation_id or request.user_id
    parsed = parse_jenkins_command(request.user_id, request.text)
    extracted = _merge_jenkins_context(conversation_id, parsed.extracted)
    missing_fields = _missing_jenkins_context(extracted)
    if missing_fields:
        update_session(conversation_id, extracted)
        response = JenkinsNaturalLanguageResponse(
            success=False,
            message=f"缺少 {', '.join(missing_fields)}，请补充",
            reply=f"缺少 {', '.join(missing_fields)}，请补充。",
            conversation_id=conversation_id,
            extracted=extracted,
            missing_fields=missing_fields,
        )
        audit_event("jenkins.nlp.missing", request.user_id, {"request": request.model_dump(), "response": response.model_dump()})
        return response

    tool_request = JenkinsTriggerRequest(
        user_id=request.user_id,
        job=extracted["job"],
        env=extracted["env"],
        branch=extracted["branch"],
        confirmed=bool(extracted.get("confirmed")),
    )
    tool_response = trigger_job(tool_request)
    if tool_response.success:
        clear_session(conversation_id)
    else:
        update_session(conversation_id, {**extracted, "confirmed": False})

    response = JenkinsNaturalLanguageResponse(
        success=tool_response.success,
        message=tool_response.message,
        reply=_jenkins_reply(tool_response, extracted),
        conversation_id=conversation_id,
        extracted=extracted,
        build_url=tool_response.build_url,
        needs_confirmation=tool_response.needs_confirmation,
    )
    audit_event("jenkins.nlp.trigger", request.user_id, {"request": request.model_dump(), "response": response.model_dump()})
    return response


def _merge_jenkins_context(conversation_id: str, extracted: dict) -> dict:
    previous = get_session(conversation_id)
    merged = {**previous, **{key: value for key, value in extracted.items() if value is not None}}
    merged["confirmed"] = bool(extracted.get("confirmed"))
    return merged


def _missing_jenkins_context(extracted: dict) -> list[str]:
    return [field for field in ["job", "env", "branch"] if not extracted.get(field)]


def _jenkins_reply(response: JenkinsTriggerResponse, extracted: dict) -> str:
    if response.needs_confirmation:
        return f"已识别任务 {extracted['job']}，环境 {extracted['env']}，分支 {extracted['branch']}。请回复“确认”后触发 Jenkins。"
    if response.success:
        return f"已触发 Jenkins 任务，地址：{response.build_url}"
    return response.message


@app.post("/tools/bugs/create", response_model=BugCreateResponse)
def create_teambition_bug(request: BugCreateRequest) -> BugCreateResponse:
    response = create_bug(request)
    audit_event("bugs.create", request.user_id, {"request": request.model_dump(), "response": response.model_dump()})
    return response
