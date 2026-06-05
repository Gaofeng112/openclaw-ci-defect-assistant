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
def bug_fields_config() -> dict[str, Any]:
    return _read_yaml("bug_fields.yaml")


@lru_cache
def jenkins_settings() -> dict[str, str]:
    return {
        "base_url": getenv("JENKINS_BASE_URL", "").rstrip("/"),
        "user": getenv("JENKINS_USER", ""),
        "token": getenv("JENKINS_TOKEN", ""),
    }


@lru_cache
def assistant_settings() -> dict[str, str]:
    return {
        "dingtalk_default_user_id": getenv("DINGTALK_DEFAULT_USER_ID", "u001"),
    }
