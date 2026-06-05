import re
from dataclasses import dataclass

from app.config import jobs_config
from app.schemas import JenkinsTriggerRequest


@dataclass(frozen=True)
class ParsedJenkinsCommand:
    request: JenkinsTriggerRequest | None
    extracted: dict
    missing_fields: list[str]


def _jobs() -> dict:
    config = jobs_config()
    return config.get("jobs", config)


def _compact(value: str) -> str:
    return re.sub(r"[\s_-]+", "", value.lower())


def _is_ci_intent(text: str) -> bool:
    keywords = [
        "jenkins",
        "ci",
        "流水线",
        "构建",
        "测试",
        "自动化",
        "跑一下",
        "执行",
        "触发",
        "娴嬭瘯",
        "鎵ц",
        "瑙﹀彂",
        "鏋勫缓",
    ]
    return any(keyword in text.lower() for keyword in keywords)


def _find_job(text: str) -> str | None:
    compact_text = _compact(text)
    for alias, job in _jobs().items():
        candidates = {alias, job.get("job_path", "").split("/")[-1]}
        if any(_compact(candidate) in compact_text for candidate in candidates if candidate):
            return alias

    jobs = _jobs()
    if _is_ci_intent(text) and len(jobs) == 1:
        return next(iter(jobs))
    return None


def _find_keyed_value(text: str, keys: list[str]) -> str | None:
    key_pattern = "|".join(re.escape(key) for key in keys)
    match = re.search(rf"(?:{key_pattern})\s*(?:是|为|=|:|：)?\s*([A-Za-z0-9._/\-]+)", text, re.IGNORECASE)
    return match.group(1).rstrip("，,。.;；") if match else None


def _find_env(text: str, job_alias: str | None) -> str | None:
    keyed = _find_keyed_value(text, ["env", "环境", "鐜"])
    if keyed:
        return keyed

    env_aliases = {
        "测试环境": "test",
        "测试": "test",
        "预发环境": "pre",
        "预发": "pre",
    }
    for phrase, env in env_aliases.items():
        if phrase in text:
            return env

    allowed_envs = _jobs().get(job_alias or "", {}).get("allowed_envs", [])
    for env in allowed_envs:
        if re.search(rf"(?<![A-Za-z0-9_-]){re.escape(env)}(?![A-Za-z0-9_-])", text, re.IGNORECASE):
            return env
    return None


def _find_branch(text: str, job_alias: str | None, env: str | None) -> str | None:
    keyed = _find_keyed_value(text, ["branch", "分支", "代码分支", "鍒嗘敮", "浠ｇ爜鍒嗘敮"])
    return keyed or _find_unkeyed_branch(text, job_alias, env)


def _find_unkeyed_branch(text: str, job_alias: str | None, env: str | None) -> str | None:
    ignore = {
        "jenkins",
        "ci",
        "env",
        "branch",
        "pipeline",
        "build",
        "run",
        "trigger",
        "confirm",
        "yes",
    }
    if job_alias:
        job = _jobs().get(job_alias, {})
        ignore.update({_compact(job_alias), _compact(job.get("job_path", "").split("/")[-1])})
    if env:
        ignore.add(_compact(env))

    allowed_envs = _jobs().get(job_alias or "", {}).get("allowed_envs", [])
    ignore.update(_compact(item) for item in allowed_envs)

    tokens = re.findall(r"(?<![A-Za-z0-9_-])([A-Za-z][A-Za-z0-9._/\-]*)(?![A-Za-z0-9_-])", text)
    candidates = [token.rstrip("，,。.;；") for token in tokens if _compact(token) not in ignore]
    return candidates[0] if len(candidates) == 1 else None


def _is_confirmed(text: str) -> bool:
    lower_text = text.lower()
    confirm_phrases = [
        "确认",
        "可以执行",
        "同意执行",
        "确认触发",
        "确认执行",
        "执行吧",
        "开始吧",
        "触发吧",
        "纭",
        "鍙互鎵ц",
        "鍚屾剰鎵ц",
        "纭瑙﹀彂",
        "纭鎵ц",
    ]
    english_phrases = ["confirm", "yes", "go ahead", "run it", "trigger it"]
    return any(phrase in text for phrase in confirm_phrases) or any(phrase in lower_text for phrase in english_phrases)


def _missing_fields(job_alias: str | None, env: str | None, branch: str | None) -> list[str]:
    return [field for field, value in {"job": job_alias, "env": env, "branch": branch}.items() if not value]


def parse_jenkins_command(user_id: str, text: str) -> ParsedJenkinsCommand:
    job_alias = _find_job(text)
    env = _find_env(text, job_alias)
    branch = _find_branch(text, job_alias, env)
    extracted = {
        "job": job_alias,
        "env": env,
        "branch": branch,
        "confirmed": _is_confirmed(text),
    }
    missing = _missing_fields(job_alias, env, branch)
    if missing:
        return ParsedJenkinsCommand(request=None, extracted=extracted, missing_fields=missing)

    return ParsedJenkinsCommand(
        request=JenkinsTriggerRequest(
            user_id=user_id,
            job=job_alias,
            env=env,
            branch=branch,
            confirmed=extracted["confirmed"],
        ),
        extracted=extracted,
        missing_fields=[],
    )
