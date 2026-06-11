from functools import lru_cache
from os import getenv
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
import yaml


BASE_DIR = Path(getenv("CI_DEFECT_ASSISTANT_HOME") or Path(__file__).resolve().parent.parent).resolve()
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
def teambition_bug_form_config() -> dict[str, Any]:
    return _read_yaml("teambition_bug_form.v1.yaml")


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


def _setting_id(config: dict[str, Any], env_name: str, config_name: str, default: str = "") -> str:
    return _config_id(config, config_name) or default or _env_id(env_name)


@lru_cache
def teambition_settings() -> dict[str, Any]:
    config = teambition_config()
    bug_form = teambition_bug_form_config()
    project = bug_form.get("project") or {}
    bug_create = bug_form.get("bug_create") or {}
    members = bug_form.get("members") or {}
    return {
        "base_url": str(config.get("base_url") or getenv("TEAMBITION_BASE_URL", "https://open.teambition.com/api")).rstrip("/"),
        "app_id": getenv("TEAMBITION_APP_ID", ""),
        "app_secret": getenv("TEAMBITION_APP_SECRET", ""),
        "org_id": _config_id(project, "organization_id") or _env_id("TEAMBITION_ORG_ID"),
        "operator_id": _env_id("TEAMBITION_OPERATOR_ID"),
        "project_id": _setting_id(config, "TEAMBITION_PROJECT_ID", "project_id", _config_id(project, "project_id")),
        "tasklist_id": _setting_id(config, "TEAMBITION_TASKLIST_ID", "default_tasklist_id", _config_id(bug_create, "tasklist_id")),
        "stage_id": _setting_id(config, "TEAMBITION_STAGE_ID", "default_stage_id", _config_id(bug_create, "stage_id")),
        "taskflowstatus_id": _setting_id(config, "TEAMBITION_TASKFLOWSTATUS_ID", "taskflowstatus_id", _config_id(bug_create, "default_status_id")),
        "sfc_id": _setting_id(config, "TEAMBITION_BUG_SFC_ID", "bug_sfc_id", _config_id(bug_create, "scenariofieldconfig_id")),
        "default_executor_id": _setting_id(
            config,
            "TEAMBITION_DEFAULT_EXECUTOR_ID",
            "default_executor_id",
            _config_id(bug_create, "default_executor_id") or _config_id(members, "default_executor"),
        ),
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
