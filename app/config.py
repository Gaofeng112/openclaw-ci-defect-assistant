from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml


BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = BASE_DIR / "configs"


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
