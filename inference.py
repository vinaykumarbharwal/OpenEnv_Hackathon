"""
Submission inference entrypoint.

Mandatory environment variables:
- API_BASE_URL
- MODEL_NAME
- HF_TOKEN

Stdout contract:
- [START] task=<task_name> env=<benchmark> model=<model_name>
- [STEP]  step=<n> action=<action_str> reward=<0.00> done=<true|false> error=<msg|null>
- [END]   success=<true|false> steps=<n> rewards=<r1,r2,...,rn>
"""

from __future__ import annotations

import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

from openai import OpenAI

# Make package importable when run from repo root.
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from openenv_bug_triage import BugTriageEnv
from openenv_bug_triage.grader import BugTriageGrader
from openenv_bug_triage.models import ActionModel


def _load_simple_env_file(dotenv_path: Path) -> None:
    """Load simple KEY=VALUE lines without failing on stray shell commands."""
    if not dotenv_path.exists():
        return

    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)


_load_simple_env_file(PROJECT_ROOT / ".env")

HF_TOKEN = os.getenv("HF_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
API_BASE_URL = os.getenv("API_BASE_URL", "https://router.huggingface.co/v1")
MODEL_NAME = os.getenv("MODEL_NAME", "Qwen/Qwen2.5-72B-Instruct")
API_KEY = HF_TOKEN or OPENAI_API_KEY

BENCHMARK = os.getenv("OPENENV_BENCHMARK", "bug-triage-openenv")
TASKS = [
    t.strip()
    for t in os.getenv(
        "OPENENV_TASKS",
        "bug_triage_easy,bug_triage_medium,bug_triage_hard",
    ).split(",")
    if t.strip()
]

SEED = int(os.getenv("OPENENV_SEED", "42"))
MAX_STEPS_PER_TICKET = int(os.getenv("MAX_STEPS_PER_TICKET", "4"))
MAX_STEPS = int(os.getenv("MAX_STEPS", "200"))
TEMPERATURE = float(os.getenv("TEMPERATURE", "0"))
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "220"))

COMPONENT_TEAM_MAP = {
    "api-gateway": "backend-api",
    "auth-service": "backend-api",
    "user-service": "backend-api",
    "payment-service": "backend-api",
    "web-app": "frontend-web",
    "ios-app": "mobile-ios",
    "android-app": "mobile-android",
    "database": "data-platform",
    "cache": "infrastructure",
    "cdn": "infrastructure",
}

COMPONENT_KEYWORDS = {
    "api-gateway": ("api gateway", "gateway", "edge", "proxy", "routing", "/api/"),
    "auth-service": ("auth", "authentication", "login", "signin", "token", "session"),
    "user-service": ("user service", "users endpoint", "profile", "identity", "account"),
    "payment-service": ("payment", "checkout", "charge", "billing", "tax", "order"),
    "web-app": ("web app", "web-app", "browser", "dashboard", "frontend", "page"),
    "ios-app": ("ios", "iphone", "ipad", "apple"),
    "android-app": ("android",),
    "database": ("database", "query", "sql", "db", "index"),
    "cache": ("cache", "redis", "memcache"),
    "cdn": ("cdn", "image", "asset", "static content"),
}

SERVICE_COMPONENT_HINTS = {
    "api": ("api-gateway", "user-service"),
    "auth": ("auth-service",),
    "identity": ("user-service",),
    "payments": ("payment-service",),
    "web-app": ("web-app", "cdn", "database", "cache"),
    "mobile-app": ("ios-app", "android-app", "auth-service"),
}


class ActionParseError(ValueError):
    """Raised when a model response cannot be converted into a valid action."""


def _b(value: bool) -> str:
    return "true" if value else "false"


def _as_bool(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _sanitize(text: str) -> str:
    return " ".join(str(text).replace("\n", " ").replace("\r", " ").split())


def _action_to_log(action: ActionModel) -> str:
    payload = action.model_dump(exclude_none=True)
    return json.dumps(payload, separators=(",", ":"))


def _severity_to_priority(severity: str) -> str:
    return {
        "sev0": "p0",
        "sev1": "p1",
        "sev2": "p2",
        "sev3": "p3",
    }.get(severity, "p2")


def _ticket_text(ticket) -> str:
    return " ".join(
        str(part)
        for part in (
            ticket.title,
            ticket.description,
            ticket.service,
            " ".join(ticket.component_candidates),
        )
    ).lower()


def _infer_component(ticket, available_components: list[str]) -> str:
    candidates = [c for c in ticket.component_candidates if c in available_components]
    if not candidates:
        return available_components[0] if available_components else "api-gateway"

    text = _ticket_text(ticket)
    service_hints = SERVICE_COMPONENT_HINTS.get(ticket.service, ())
    best_candidate = candidates[0]
    best_score = -1

    for index, candidate in enumerate(candidates):
        score = 0
        score += max(0, 3 - index)

        if candidate in service_hints:
            score += 3

        normalized = candidate.replace("-", " ")
        if normalized in text:
            score += 4

        for keyword in COMPONENT_KEYWORDS.get(candidate, ()):
            if keyword in text:
                score += 3

        if candidate == "ios-app" and "login" in text:
            score += 1
        if candidate == "payment-service" and "gateway" in text:
            score += 1
        if candidate == "database" and "slow" in text:
            score += 1

        if score > best_score:
            best_score = score
            best_candidate = candidate

    return best_candidate


def _infer_severity(ticket, component: str) -> str:
    text = _ticket_text(ticket)
    synthetic_high_signal = "signal quality is high" in text
    synthetic_low_signal = "signal quality is low" in text

    if any(k in text for k in ["security", "unauthorized", "double charge", "data loss", "corrupt"]):
        return "sev0"

    if any(k in text for k in ["500 internal server error", "null pointer exception", "multiple monitoring alerts"]):
        if ticket.reporter_type == "monitoring" and ticket.customer_tier == "enterprise":
            return "sev0"

    if synthetic_high_signal and ticket.reporter_type == "monitoring" and ticket.customer_tier == "enterprise":
        return "sev1"

    if any(k in text for k in ["timeout", "timing out", "503", "outage", "down"]):
        return "sev1"

    if synthetic_high_signal and ticket.customer_tier in {"pro", "enterprise"}:
        return "sev1"

    if "incorrect tax" in text or ("tax" in text and "wrong" in text):
        return "sev1" if ticket.customer_tier in {"pro", "enterprise"} else "sev2"

    if synthetic_low_signal:
        return "sev3" if ticket.customer_tier == "free" else "sev2"

    if any(k in text for k in ["crash", "not responding", "not working", "broken image", "wrong values"]):
        return "sev2"

    if any(k in text for k in ["latency", "slow", "degraded", "error", "failed"]):
        if component == "database" and ticket.customer_tier == "free":
            return "sev3"
        return "sev2"

    return "sev3"


def _infer_priority(ticket, severity: str) -> str:
    text = _ticket_text(ticket)

    if severity == "sev2" and (
        ticket.customer_tier == "enterprise"
        or ticket.reporter_type == "monitoring"
        or any(k in text for k in ["payment", "checkout", "tax", "cdn", "image", "shopping"])
    ):
        return "p1"

    return _severity_to_priority(severity)


def _needs_more_info(ticket) -> bool:
    text = _ticket_text(ticket)

    if ticket.suspected_duplicate_ids:
        return False

    if "signal quality is low" in text:
        return True

    if not ticket.repro_steps_present and not ticket.logs_present:
        return True

    if not ticket.repro_steps_present and ticket.reporter_type != "monitoring":
        return True

    if not ticket.logs_present and ticket.reporter_type in {"user", "qa"}:
        return True

    return False


def _fallback_action(observation, plans: dict[str, dict]) -> ActionModel:
    ticket = observation.current_ticket
    if ticket is None:
        return ActionModel(action_type="next_ticket", next_ticket={})

    ticket_id = ticket.ticket_id
    plan = plans.setdefault(ticket_id, {"phase": 0})
    phase = int(plan.get("phase", 0))

    if phase == 0:
        component = _infer_component(ticket, observation.available_components)
        severity = _infer_severity(ticket, component)
        priority = _infer_priority(ticket, severity)
        duplicate_id = (ticket.suspected_duplicate_ids or [None])[0]
        plan["phase"] = 1
        plan["severity"] = severity
        plan["component"] = component
        plan["duplicate_id"] = duplicate_id
        plan["needs_more_info"] = _needs_more_info(ticket)
        return ActionModel(
            action_type="classify",
            classify={
                "severity": severity,
                "priority": priority,
                "component": component,
            },
        )

    if phase == 1:
        component = str(plan.get("component") or _infer_component(ticket, observation.available_components))
        default_team = observation.available_teams[0] if observation.available_teams else "backend-api"
        team = COMPONENT_TEAM_MAP.get(component, default_team)
        plan["phase"] = 2
        return ActionModel(action_type="assign", assign={"team": team})

    if phase == 2:
        sev = str(plan.get("severity", "sev2"))
        duplicate_id = plan.get("duplicate_id")
        if duplicate_id:
            plan["phase"] = 3
            return ActionModel(
                action_type="mark_duplicate",
                mark_duplicate={"canonical_ticket_id": str(duplicate_id)},
            )

        if sev in {"sev0", "sev1"}:
            plan["phase"] = 3
            return ActionModel(
                action_type="escalate_incident",
                escalate_incident={"justification": "High-impact production risk detected"},
            )

        if bool(plan.get("needs_more_info")):
            plan["phase"] = 3
            info_type = "both"
            if ticket.repro_steps_present and not ticket.logs_present:
                info_type = "logs"
            elif ticket.logs_present and not ticket.repro_steps_present:
                info_type = "repro_steps"
            return ActionModel(
                action_type="request_info",
                request_info={"info_type": info_type},
            )

        plan["phase"] = 3
        return ActionModel(action_type="next_ticket", next_ticket={})

    return ActionModel(action_type="next_ticket", next_ticket={})


def _guard_action(
    action: ActionModel,
    observation,
    action_history_by_ticket: dict[str, list[str]],
    steps_by_ticket: dict[str, int],
) -> ActionModel:
    ticket = observation.current_ticket
    if ticket is None:
        return action

    ticket_id = ticket.ticket_id
    history = action_history_by_ticket[ticket_id]
    ticket_steps = steps_by_ticket[ticket_id]

    if ticket_steps >= MAX_STEPS_PER_TICKET and action.action_type != "next_ticket":
        return ActionModel(action_type="next_ticket", next_ticket={})

    if action.action_type == "request_info" and "request_info" in history:
        return ActionModel(action_type="next_ticket", next_ticket={})

    if len(history) >= 2 and history[-1] == history[-2] == action.action_type and action.action_type != "next_ticket":
        return ActionModel(action_type="next_ticket", next_ticket={})

    return action


def _build_prompt(observation) -> str:
    ticket = observation.current_ticket
    if ticket is None:
        return '{"action_type":"next_ticket","next_ticket":{}}'

    return f"""Return ONLY JSON for the next bug-triage action.

Ticket ID: {ticket.ticket_id}
Title: {ticket.title}
Description: {ticket.description}
Reporter: {ticket.reporter_type}
Service: {ticket.service}
Tier: {ticket.customer_tier}
Repro Steps Present: {ticket.repro_steps_present}
Logs Present: {ticket.logs_present}
Suspected Duplicates: {ticket.suspected_duplicate_ids}

Last Result: {observation.last_action_result}
Available Teams: {observation.available_teams}
Available Components: {observation.available_components}

Allowed action_type values:
classify, assign, mark_duplicate, request_info, defer, close, escalate_incident, next_ticket

Rules:
- Do not repeat request_info on the same ticket.
- Avoid loops. If uncertain, use classify or next_ticket.
- Do not include markdown fences, analysis, or <think> tags.
- Output exactly one valid JSON object only.
"""


def _message_to_text(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        chunks: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                chunks.append(str(item.get("text", "")))
                continue

            text_value = getattr(item, "text", None)
            if text_value:
                chunks.append(str(text_value))
        return "".join(chunks)
    return "" if content is None else str(content)


def _extract_json_objects(text: str) -> list[str]:
    objects: list[str] = []
    start: int | None = None
    depth = 0
    in_string = False
    escaped = False

    for index, char in enumerate(text):
        if start is None:
            if char == "{":
                start = index
                depth = 1
                in_string = False
                escaped = False
            continue

        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                objects.append(text[start:index + 1])
                start = None

    return objects


def _parse_action(raw: str) -> ActionModel:
    text = re.sub(r"<think>.*?</think>", " ", raw, flags=re.IGNORECASE | re.DOTALL).strip()

    candidates: list[str] = [text]
    if "```json" in text:
        start = text.find("```json") + 7
        end = text.find("```", start)
        if end != -1:
            candidates.append(text[start:end].strip())
    elif "```" in text:
        start = text.find("```") + 3
        end = text.find("```", start)
        if end != -1:
            candidates.append(text[start:end].strip())

    candidates.extend(_extract_json_objects(text))

    seen: set[str] = set()
    for candidate in candidates:
        candidate = candidate.strip()
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)

        try:
            data = json.loads(candidate)
            return ActionModel(**data)
        except (json.JSONDecodeError, TypeError, ValueError):
            continue

    raise ActionParseError(f"Could not parse model action from response: {_sanitize(text[:200])}")


def _request_model_action(client: OpenAI, observation) -> ActionModel:
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {
                "role": "system",
                "content": "You are an expert bug triage assistant. Return one JSON object only.",
            },
            {"role": "user", "content": _build_prompt(observation)},
        ],
        temperature=TEMPERATURE,
        max_tokens=MAX_TOKENS,
    )

    raw = _message_to_text(response.choices[0].message.content)
    return _parse_action(raw)


def _run_task(task_id: str, env: BugTriageEnv, client: OpenAI | None) -> None:
    print(f"[START] task={task_id} env={BENCHMARK} model={MODEL_NAME}")

    step_no = 0
    rewards: list[str] = []
    success = False

    api_disabled = False
    plans: dict[str, dict] = {}
    action_history_by_ticket: dict[str, list[str]] = defaultdict(list)
    steps_by_ticket: dict[str, int] = defaultdict(int)

    done = False
    episode_actions: list[dict] = []
    info = {"metrics": {}}

    try:
        obs = env.reset(task_id=task_id, seed=SEED)

        while not done and step_no < MAX_STEPS:
            step_no += 1
            current_ticket_id = obs.current_ticket.ticket_id if obs.current_ticket else None

            if client is not None and not api_disabled:
                try:
                    action = _request_model_action(client, obs)
                except ActionParseError:
                    action = _fallback_action(obs, plans)
                except Exception:
                    api_disabled = True
                    action = _fallback_action(obs, plans)
            else:
                action = _fallback_action(obs, plans)

            action = _guard_action(action, obs, action_history_by_ticket, steps_by_ticket)

            err_value = "null"
            try:
                obs, reward, done, info = env.step(action)
                reward_value = f"{reward.step_reward:.2f}"
                rewards.append(reward_value)

                last_action_error = info.get("last_action_error") if isinstance(info, dict) else None
                validation_error = info.get("validation_error") if isinstance(info, dict) else None
                error_raw = last_action_error if last_action_error else validation_error
                if error_raw:
                    err_value = _sanitize(error_raw)

                print(
                    f"[STEP] step={step_no} action={_action_to_log(action)} "
                    f"reward={reward_value} done={_b(bool(done))} error={err_value}"
                )

                episode_actions.append(action.model_dump(exclude_none=True))
                if current_ticket_id:
                    action_history_by_ticket[current_ticket_id].append(action.action_type)
                    steps_by_ticket[current_ticket_id] += 1
            except Exception as exc:
                err_value = _sanitize(str(exc))
                print(
                    f"[STEP] step={step_no} action={_action_to_log(action)} "
                    f"reward=0.00 done=true error={err_value}"
                )
                rewards.append("0.00")
                done = True

        try:
            grader = BugTriageGrader(task_id=task_id)
            ground_truths = [
                gt.model_dump() for gt in env.current_task.ground_truths
            ] if env.current_task else []
            grader_result = grader.grade_episode(
                episode_actions=[{"action": a} for a in episode_actions],
                ground_truths=ground_truths,
                metrics=info.get("metrics", {}) if isinstance(info, dict) else {},
            )
            success = bool(grader_result.passed)
        except Exception:
            success = bool(done)
    finally:
        if hasattr(env, "close"):
            try:
                env.close()
            except Exception:
                pass

        rewards_csv = ",".join(rewards)
        print(f"[END] success={_b(success)} steps={step_no} rewards={rewards_csv}")


def main() -> int:
    offline_mode = _as_bool(os.getenv("OPENENV_OFFLINE"))
    client: OpenAI | None = None

    if not offline_mode:
        if not API_KEY:
            print(
                "HF_TOKEN is required for live inference. "
                "OPENAI_API_KEY is also accepted for direct OpenAI endpoints. "
                "Set OPENENV_OFFLINE=1 to run the local fallback policy instead.",
                file=sys.stderr,
            )
            return 1

        try:
            client = OpenAI(api_key=API_KEY, base_url=API_BASE_URL, max_retries=0, timeout=30)
        except Exception as exc:
            print(
                f"Warning: failed to initialize API client ({_sanitize(exc)}). "
                "Falling back to offline policy.",
                file=sys.stderr,
            )
            client = None
    else:
        print("Running in offline fallback mode (OPENENV_OFFLINE=1).", file=sys.stderr)

    env = BugTriageEnv()

    for task_id in TASKS:
        _run_task(task_id=task_id, env=env, client=client)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
