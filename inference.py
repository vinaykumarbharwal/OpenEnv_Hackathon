"""
Submission inference entrypoint.

Mandatory environment variables:
- API_BASE_URL
- MODEL_NAME
- HF_TOKEN

Stdout contract:
- [START] task=<task_name> env=<benchmark> model=<model_name>
- [STEP]  step=<n> action=<action_str> reward=<0.00> done=<true|false> error=<msg|null>
- [END]   success=<true|false> steps=<n> score=<0.xxxx> rewards=<r1,r2,...,rn>

All deterministic heuristics live in ``server/heuristics.py`` and are
shared with the FastAPI server so that changes remain in one place.
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

from models import ActionModel
from server.environment import BugTriageEnv
from server.graders import BugTriageGrader
from server.policy import recommend_action


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

# COMPONENT_TEAM_MAP, COMPONENT_KEYWORDS, SERVICE_COMPONENT_HINTS and all
# heuristic inference functions are imported from server.heuristics so they
# are shared with the FastAPI server without duplication.


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


def _strict_unit_interval(value: float, eps: float = 1e-6) -> float:
    """Clamp numeric scores to the strict open interval (0, 1)."""
    return max(eps, min(1.0 - eps, float(value)))


def _emit(line: str) -> None:
    """Emit one stdout log line immediately."""
    print(line, flush=True)


def _action_to_log(action: ActionModel) -> str:
    if _as_bool(os.getenv("OPENENV_LOG_ACTION_JSON")):
        payload = action.model_dump(exclude_none=True)
        return json.dumps(payload, separators=(",", ":"))

    def _value(raw: object, max_len: int = 48) -> str:
        text = _sanitize(str(raw)).replace(" ", "_")
        if len(text) > max_len:
            return f"{text[:max_len - 3]}..."
        return text

    if action.action_type == "classify" and action.classify:
        return (
            "classify("
            f"sev={action.classify.severity},"
            f"pri={action.classify.priority},"
            f"comp={_value(action.classify.component)}"
            ")"
        )
    if action.action_type == "assign" and action.assign:
        return f"assign(team={_value(action.assign.team)})"
    if action.action_type == "mark_duplicate" and action.mark_duplicate:
        return f"mark_duplicate(canonical={_value(action.mark_duplicate.canonical_ticket_id)})"
    if action.action_type == "request_info" and action.request_info:
        return f"request_info(type={_value(action.request_info.info_type)})"
    if action.action_type == "defer" and action.defer:
        return f"defer(reason={_value(action.defer.reason)})"
    if action.action_type == "close" and action.close:
        return f"close(reason={_value(action.close.reason)})"
    if action.action_type == "escalate_incident" and action.escalate_incident:
        return f"escalate_incident(why={_value(action.escalate_incident.justification)})"
    if action.action_type == "next_ticket":
        return "next_ticket"

    payload = action.model_dump(exclude_none=True)
    return f"raw:{json.dumps(payload, separators=(',', ':'))}"


def _fallback_action(observation, plans: dict[str, dict]) -> ActionModel:
    """Deterministic fallback policy used when the LLM is unavailable."""
    ticket = observation.current_ticket
    if ticket is None:
        return ActionModel(action_type="next_ticket", next_ticket={})

    history = plans.setdefault(ticket.ticket_id, {}).setdefault("history", [])
    action, _ = recommend_action(observation=observation, action_history=list(history))
    return action


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

    if action.action_type == "classify" and "classify" in history:
        return ActionModel(action_type="next_ticket", next_ticket={})

    if action.action_type == "assign" and "assign" in history:
        return ActionModel(action_type="next_ticket", next_ticket={})

    if action.action_type == "mark_duplicate" and "mark_duplicate" in history:
        return ActionModel(action_type="next_ticket", next_ticket={})

    if action.action_type == "escalate_incident" and "escalate_incident" in history:
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
    _emit(f"[START] task={task_id} env={BENCHMARK} model={MODEL_NAME}")

    step_no = 0
    rewards: list[str] = []
    success = False
    score = 0.5

    api_disabled = False
    plans: dict[str, dict] = {}
    action_history_by_ticket: dict[str, list[str]] = defaultdict(list)
    steps_by_ticket: dict[str, int] = defaultdict(int)

    done = False
    episode_actions: list[dict] = []
    info: dict = {"metrics": {}}

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
                except Exception as exc:  # noqa: BLE001
                    print(
                        f"[WARN] Model API error; switching to offline fallback: {_sanitize(str(exc))}",
                        file=sys.stderr,
                        flush=True,
                    )
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

                _emit(
                    f"[STEP] step={step_no:03d} action={_action_to_log(action)} "
                    f"reward={reward_value} done={_b(bool(done))} error={err_value}"
                )

                episode_actions.append(action.model_dump(exclude_none=True))
                if current_ticket_id:
                    action_history_by_ticket[current_ticket_id].append(action.action_type)
                    steps_by_ticket[current_ticket_id] += 1
                    plans.setdefault(current_ticket_id, {}).setdefault("history", []).append(action.action_type)
            except Exception as exc:
                err_value = _sanitize(str(exc))
                _emit(
                    f"[STEP] step={step_no:03d} action={_action_to_log(action)} "
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
            score = _strict_unit_interval(grader_result.score)
            success = bool(grader_result.passed)
        except Exception as exc:  # noqa: BLE001
            print(
                f"[WARN] Grader failed for task '{task_id}'; falling back to reward average: "
                f"{_sanitize(str(exc))}",
                file=sys.stderr,
                flush=True,
            )
            success = False
            parsed_rewards: list[float] = []
            for reward_text in rewards:
                try:
                    parsed_rewards.append(float(reward_text))
                except ValueError:
                    continue
            avg_reward = (sum(parsed_rewards) / len(parsed_rewards)) if parsed_rewards else 0.5
            score = _strict_unit_interval(avg_reward)
    finally:
        if hasattr(env, "close"):
            try:
                env.close()
            except Exception:
                pass

        rewards_csv = ",".join(rewards)
        _emit(
            f"[END] success={_b(success)} steps={step_no:03d} "
            f"score={score:.6f} rewards={rewards_csv}"
        )


def main() -> int:
    offline_mode = _as_bool(os.getenv("OPENENV_OFFLINE"))
    client: OpenAI | None = None

    if not offline_mode and not API_KEY:
        print(
            "No HF_TOKEN or OPENAI_API_KEY found. Falling back to offline mode.",
            file=sys.stderr,
            flush=True,
        )
        offline_mode = True

    if not offline_mode:
        try:
            client = OpenAI(api_key=API_KEY, base_url=API_BASE_URL, max_retries=0, timeout=30)
        except Exception as exc:
            print(
                f"Failed to initialize OpenAI client ({_sanitize(exc)}). "
                "Falling back to offline mode.",
                file=sys.stderr,
                flush=True,
            )
            client = None

    env = BugTriageEnv()

    for task_id in TASKS:
        _run_task(task_id=task_id, env=env, client=client)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
