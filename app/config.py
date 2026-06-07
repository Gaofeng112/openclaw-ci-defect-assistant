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
def teambition_config() -> dict[str, Any]:
    return _read_yaml("teambition.yaml")


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


def _config_id(config: dict[str, Any], name: str) -> str:
    value = str(config.get(name) or "").strip().rstrip("/")
    return value.rsplit("/", 1)[-1] if "/" in value else value


@lru_cache
def teambition_settings() -> dict[str, Any]:
    config = teambition_config()
    return {
        "base_url": str(config.get("base_url") or getenv("TEAMBITION_BASE_URL", "https://open.teambition.com/api")).rstrip("/"),
        "app_id": getenv("TEAMBITION_APP_ID", ""),
        "app_secret": getenv("TEAMBITION_APP_SECRET", ""),
        "org_id": _env_id("TEAMBITION_ORG_ID"),
        "operator_id": _env_id("TEAMBITION_OPERATOR_ID"),
        "project_id": _config_id(config, "project_id"),
        "tasklist_id": _config_id(config, "default_tasklist_id"),
        "stage_id": _config_id(config, "default_stage_id"),
        "taskflowstatus_id": _config_id(config, "taskflowstatus_id"),
        "sfc_id": _config_id(config, "bug_sfc_id"),
        "default_executor_id": _config_id(config, "default_executor_id"),
        "priority_map": config.get("priority_map") or {},
        "customfields": config.get("customfields") or {},
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
