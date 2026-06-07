from app.config import users_config


def _users() -> dict:
    config = users_config()
    return config.get("users", config)


def get_user(user_id: str) -> dict:
    return _users().get(user_id, {})


def user_roles(user_id: str) -> set[str]:
    return set(get_user(user_id).get("roles", []))


def has_any_role(user_id: str, allowed_roles: list[str]) -> bool:
    return bool(user_roles(user_id) & set(allowed_roles))


def can_trigger_job(user_id: str, job: dict) -> bool:
    return has_any_role(user_id, job.get("allowed_roles", []))
