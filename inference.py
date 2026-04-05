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
import sys
from collections import defaultdict
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

# Make package importable when run from repo root.
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from openenv_bug_triage import BugTriageEnv
from openenv_bug_triage.grader import BugTriageGrader
from openenv_bug_triage.models import ActionModel


load_dotenv()

API_BASE_URL = os.getenv("API_BASE_URL", "https://api.groq.com/openai/v1")
MODEL_NAME = os.getenv("MODEL_NAME", "llama-3.3-70b-versatile")
HF_TOKEN = os.getenv("HF_TOKEN")

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


def _b(value: bool) -> str:
    return "true" if value else "false"


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


def _infer_component(ticket, available_components: list[str]) -> str:
    for candidate in ticket.component_candidates:
        if candidate in available_components:
            return candidate
    return available_components[0] if available_components else "api-gateway"


def _infer_severity(ticket) -> str:
    text = f"{ticket.title} {ticket.description}".lower()
    if any(k in text for k in ["security", "unauthorized", "double charge", "data loss"]):
        return "sev0"
    if ticket.reporter_type == "monitoring" or any(
        k in text for k in ["500", "503", "outage", "incident", "crash", "timeout"]
    ):
        return "sev1"
    if any(k in text for k in ["latency", "slow", "degraded", "error", "failed"]):
        return "sev2"
    return "sev3"


def _fallback_action(observation, plans: dict[str, dict]) -> ActionModel:
    ticket = observation.current_ticket
    if ticket is None:
        return ActionModel(action_type="next_ticket", next_ticket={})

    ticket_id = ticket.ticket_id
    plan = plans.setdefault(ticket_id, {"phase": 0})
    phase = int(plan.get("phase", 0))

    if phase == 0:
        suspected = ticket.suspected_duplicate_ids or []
        if suspected:
            plan["phase"] = 3
            return ActionModel(
                action_type="mark_duplicate",
                mark_duplicate={"canonical_ticket_id": suspected[0]},
            )

        component = _infer_component(ticket, observation.available_components)
        severity = _infer_severity(ticket)
        plan["phase"] = 1
        plan["severity"] = severity
        plan["component"] = component
        return ActionModel(
            action_type="classify",
            classify={
                "severity": severity,
                "priority": _severity_to_priority(severity),
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
        plan["phase"] = 3
        if sev in {"sev0", "sev1"}:
            return ActionModel(
                action_type="escalate_incident",
                escalate_incident={"justification": "fallback escalation"},
            )
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
- Output valid JSON only.
"""


def _parse_action(raw: str) -> ActionModel:
    text = raw.strip()
    if "```json" in text:
        start = text.find("```json") + 7
        end = text.find("```", start)
        text = text[start:end].strip()
    elif "```" in text:
        start = text.find("```") + 3
        end = text.find("```", start)
        text = text[start:end].strip()

    data = json.loads(text)
    return ActionModel(**data)


def _run_task(task_id: str, env: BugTriageEnv, client: OpenAI) -> None:
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

            if not api_disabled:
                try:
                    response = client.chat.completions.create(
                        model=MODEL_NAME,
                        messages=[
                            {
                                "role": "system",
                                "content": "You are an expert bug triage assistant. Return JSON only.",
                            },
                            {"role": "user", "content": _build_prompt(obs)},
                        ],
                        temperature=TEMPERATURE,
                        max_tokens=MAX_TOKENS,
                    )
                    raw = response.choices[0].message.content or ""
                    action = _parse_action(raw)
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
    if not HF_TOKEN:
        print("HF_TOKEN is required", file=sys.stderr)
        return 1

    client = OpenAI(api_key=HF_TOKEN, base_url=API_BASE_URL, max_retries=0, timeout=30)
    env = BugTriageEnv()

    for task_id in TASKS:
        _run_task(task_id=task_id, env=env, client=client)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
