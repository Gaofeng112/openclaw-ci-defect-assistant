from fastapi import FastAPI

from app.audit import audit_event
from app.schemas import BugCreateRequest, BugCreateResponse, HealthResponse, JenkinsTriggerRequest, JenkinsTriggerResponse
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


@app.post("/tools/bugs/create", response_model=BugCreateResponse)
def create_teambition_bug(request: BugCreateRequest) -> BugCreateResponse:
    response = create_bug(request)
    audit_event("bugs.create", request.user_id, {"request": request.model_dump(), "response": response.model_dump()})
    return response
