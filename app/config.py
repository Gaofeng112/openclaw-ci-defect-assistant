from functools import lru_cache
from os import getenv
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
import yaml


BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = BASE_DIR / "configs"

load_dotenv(BASE_DIR / ".env")


def _read_yaml(name: str) -> dict[str, Any]:
    path = CONFIG_DIR / name
    with path.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file) or {}


@lru_cache
def jobs_config() -> dict[str, Any]:
    return _read_yaml("jobs.yaml")


@lru_cache
def users_config() -> dict[str, Any]:
    return _read_yaml("users.yaml")


@lru_cache
def jenkins_settings() -> dict[str, str]:
    return {
        "base_url": getenv("JENKINS_BASE_URL", "").rstrip("/"),
        "user": getenv("JENKINS_USER", ""),
        "token": getenv("JENKINS_TOKEN", ""),
    }


def _env_id(name: str) -> str:
    value = getenv(name, "").strip().rstrip("/")
    return value.rsplit("/", 1)[-1] if "/" in value else value


@lru_cache
def teambition_settings() -> dict[str, str]:
    return {
        "base_url": getenv("TEAMBITION_BASE_URL", "https://open.teambition.com/api").rstrip("/"),
        "app_id": getenv("TEAMBITION_APP_ID", ""),
        "app_secret": getenv("TEAMBITION_APP_SECRET", ""),
        "org_id": _env_id("TEAMBITION_ORG_ID"),
        "operator_id": _env_id("TEAMBITION_OPERATOR_ID"),
        "project_id": _env_id("TEAMBITION_PROJECT_ID"),
        "tasklist_id": _env_id("TEAMBITION_TASKLIST_ID"),
        "stage_id": _env_id("TEAMBITION_STAGE_ID"),
        "taskflowstatus_id": _env_id("TEAMBITION_TASKFLOWSTATUS_ID"),
        "sfc_id": _env_id("TEAMBITION_SFC_ID"),
    }


@lru_cache
def dingtalk_settings() -> dict[str, str]:
    return {
        "app_id": getenv("DINGTALK_APP_ID", ""),
        "agent_id": getenv("DINGTALK_AGENT_ID", ""),
        "client_id": getenv("DINGTALK_CLIENT_ID", ""),
        "client_secret": getenv("DINGTALK_CLIENT_SECRET", ""),
        "robot_code": getenv("DINGTALK_ROBOT_CODE", ""),
    }
