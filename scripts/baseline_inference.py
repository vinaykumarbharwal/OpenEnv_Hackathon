"""
Baseline inference script for Bug Triage OpenEnv.

Runs all tasks using an OpenAI-compatible chat API (Groq or OpenAI)
and generates reproducible scores.
"""

import os
import sys
import json
import argparse
from collections import defaultdict
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables from .env file
load_dotenv()

# Ensure project root is importable when running as: python scripts/baseline_inference.py
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from openenv_bug_triage import BugTriageEnv
from openenv_bug_triage.models import ActionModel
from openenv_bug_triage.grader import BugTriageGrader


DEFAULT_SEED = 42
DEFAULT_PROVIDER = os.getenv("LLM_PROVIDER", "groq").strip().lower()
DEFAULT_MODELS = {
    "groq": "llama-3.3-70b-versatile",
    "openai": "gpt-5-mini",
}

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


def get_default_model(provider: str) -> str:
    """Resolve default model based on provider and environment."""
    if provider == "groq":
        return os.getenv("GROQ_MODEL", DEFAULT_MODELS["groq"])
    return os.getenv("OPENAI_MODEL", DEFAULT_MODELS["openai"])


def build_client(provider: str) -> OpenAI:
    """Build OpenAI-compatible client for selected provider."""
    max_retries = int(os.getenv("LLM_MAX_RETRIES", "0"))
    timeout_seconds = float(os.getenv("LLM_TIMEOUT_SECONDS", "30"))

    if provider == "groq":
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError(
                "GROQ_API_KEY is not set. Add it to your .env file or shell environment."
            )
        if api_key.startswith("your_") or "replace" in api_key.lower():
            raise ValueError(
                "GROQ_API_KEY appears to be a placeholder value. Set your real key in .env."
            )

        base_url = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
        return OpenAI(
            api_key=api_key,
            base_url=base_url,
            max_retries=max_retries,
            timeout=timeout_seconds,
        )

    if provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "OPENAI_API_KEY is not set. Add it to your .env file or shell environment."
            )
        if api_key.startswith("your_") or "replace" in api_key.lower():
            raise ValueError(
                "OPENAI_API_KEY appears to be a placeholder value. Set your real key in .env."
            )

        return OpenAI(api_key=api_key, max_retries=max_retries, timeout=timeout_seconds)

    raise ValueError(f"Unsupported provider: {provider}")


def infer_severity(ticket) -> str:
    """Heuristic severity for fallback policy."""
    text = f"{ticket.title} {ticket.description}".lower()

    sev0_markers = ["double charge", "unauthorized", "security", "data loss", "corrupt"]
    sev1_markers = ["500", "503", "timeout", "crash", "incident", "outage", "down"]
    sev2_markers = ["slow", "latency", "degraded", "failed", "error"]

    if any(marker in text for marker in sev0_markers):
        return "sev0"
    if ticket.reporter_type == "monitoring" or any(marker in text for marker in sev1_markers):
        return "sev1"
    if any(marker in text for marker in sev2_markers):
        return "sev2"
    return "sev3"


def severity_to_priority(severity: str) -> str:
    return {
        "sev0": "p0",
        "sev1": "p1",
        "sev2": "p2",
        "sev3": "p3",
    }.get(severity, "p2")


def infer_component(ticket, available_components: list[str]) -> str:
    """Pick a component from ticket candidates and available list."""
    for candidate in ticket.component_candidates:
        if candidate in available_components:
            return candidate
    if available_components:
        return available_components[0]
    return "api-gateway"


def fallback_action(observation, ticket_plan: dict[str, dict]) -> tuple[ActionModel, str]:
    """Deterministic fallback policy to keep the run progressing."""
    ticket = observation.current_ticket
    if ticket is None:
        return ActionModel(action_type="next_ticket", next_ticket={}), "fallback_next"

    ticket_id = ticket.ticket_id
    plan = ticket_plan.setdefault(ticket_id, {"phase": 0})
    phase = int(plan.get("phase", 0))

    if phase == 0:
        suspected = ticket.suspected_duplicate_ids or []
        if suspected:
            plan["phase"] = 3
            return (
                ActionModel(
                    action_type="mark_duplicate",
                    mark_duplicate={"canonical_ticket_id": suspected[0]},
                ),
                "fallback_duplicate",
            )

        component = infer_component(ticket, observation.available_components)
        severity = infer_severity(ticket)
        priority = severity_to_priority(severity)

        plan["phase"] = 1
        plan["component"] = component
        plan["severity"] = severity

        return (
            ActionModel(
                action_type="classify",
                classify={
                    "severity": severity,
                    "priority": priority,
                    "component": component,
                },
            ),
            "fallback_classify",
        )

    if phase == 1:
        component = str(plan.get("component") or infer_component(ticket, observation.available_components))
        default_team = observation.available_teams[0] if observation.available_teams else "backend-api"
        team = COMPONENT_TEAM_MAP.get(component, default_team)

        plan["phase"] = 2
        return ActionModel(action_type="assign", assign={"team": team}), "fallback_assign"

    if phase == 2:
        severity = str(plan.get("severity", "sev2"))
        plan["phase"] = 3

        if severity in {"sev0", "sev1"}:
            return (
                ActionModel(
                    action_type="escalate_incident",
                    escalate_incident={"justification": "Heuristic critical ticket escalation"},
                ),
                "fallback_escalate",
            )

        return ActionModel(action_type="next_ticket", next_ticket={}), "fallback_next"

    return ActionModel(action_type="next_ticket", next_ticket={}), "fallback_next"


def apply_progress_guards(
    action: ActionModel,
    observation,
    action_history_by_ticket: dict[str, list[str]],
    step_count_by_ticket: dict[str, int],
    max_steps_per_ticket: int,
) -> tuple[ActionModel, str | None]:
    """Prevent action loops and force progress through the queue."""
    ticket = observation.current_ticket
    if ticket is None:
        return action, None

    ticket_id = ticket.ticket_id
    history = action_history_by_ticket[ticket_id]
    steps_on_ticket = step_count_by_ticket[ticket_id]

    if steps_on_ticket >= max_steps_per_ticket and action.action_type != "next_ticket":
        return ActionModel(action_type="next_ticket", next_ticket={}), "forced_next:max_steps_per_ticket"

    if action.action_type == "request_info" and "request_info" in history:
        return ActionModel(action_type="next_ticket", next_ticket={}), "forced_next:repeat_request_info"

    if len(history) >= 2 and history[-1] == history[-2] == action.action_type and action.action_type != "next_ticket":
        return ActionModel(action_type="next_ticket", next_ticket={}), "forced_next:repeat_action_loop"

    return action, None


def is_rate_limit_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return "429" in text or "rate limit" in text or "too many requests" in text


def create_prompt(observation) -> str:
    """Create prompt for the model based on observation."""
    if observation.current_ticket is None:
        return "No more tickets to process."

    ticket = observation.current_ticket
    prompt = f"""You are a bug triage engineer. Analyze the ticket and choose exactly ONE next action.

Current Ticket:
- ID: {ticket.ticket_id}
- Title: {ticket.title}
- Description: {ticket.description}
- Reporter: {ticket.reporter_type}
- Service: {ticket.service}
- Customer Tier: {ticket.customer_tier}
- Has Repro Steps: {ticket.repro_steps_present}
- Has Logs: {ticket.logs_present}
- Attachments: {ticket.attachments_count}
- Suspected Duplicates: {ticket.suspected_duplicate_ids}

Previous action result on this environment step history:
- {observation.last_action_result}

Queue Status:
- Remaining: {observation.queue_stats.remaining_count}
- Urgent: {observation.queue_stats.urgent_count}
- SLA at Risk: {observation.queue_stats.sla_at_risk_count}

Available Teams: {', '.join(observation.available_teams)}
Available Components: {', '.join(observation.available_components)}

Valid action_type values:
- classify
- assign
- mark_duplicate
- request_info
- defer
- close
- escalate_incident
- next_ticket

Rules:
- Do not repeat request_info on the same ticket.
- Avoid repeating the same action in a loop.
- If unsure, choose classify or next_ticket.
- Return ONLY valid JSON (no markdown fences).

Example:
{{
  "action_type": "classify",
  "classify": {{
    "severity": "sev2",
    "priority": "p2",
    "component": "api-gateway"
  }}
}}
"""
    return prompt


def parse_model_response(response_text: str) -> ActionModel:
    """Parse model response into ActionModel."""
    try:
        response_text = response_text.strip()
        if "```json" in response_text:
            start = response_text.find("```json") + 7
            end = response_text.find("```", start)
            response_text = response_text[start:end].strip()
        elif "```" in response_text:
            start = response_text.find("```") + 3
            end = response_text.find("```", start)
            response_text = response_text[start:end].strip()

        action_dict = json.loads(response_text)
        if not isinstance(action_dict, dict) or "action_type" not in action_dict:
            raise ValueError("Invalid action JSON")
        return ActionModel(**action_dict)
    except Exception as e:
        print(f"Error parsing response: {e}")
        print(f"Response was: {response_text}")
        return ActionModel(action_type="next_ticket", next_ticket={})


def run_episode(
    env: BugTriageEnv,
    client: OpenAI,
    model: str,
    task_id: str,
    seed: int,
    max_steps_per_ticket: int,
):
    """Run one episode for a task."""
    print(f"\n{'='*60}")
    print(f"Running Task: {task_id}")
    print(f"{'='*60}")

    obs = env.reset(task_id=task_id, seed=seed)
    done = False
    step_count = 0
    episode_actions = []
    info = {"metrics": {}}

    api_disabled = False
    ticket_plan: dict[str, dict] = {}
    action_history_by_ticket: dict[str, list[str]] = defaultdict(list)
    step_count_by_ticket: dict[str, int] = defaultdict(int)

    while not done:
        step_count += 1
        current_ticket_id = obs.current_ticket.ticket_id if obs.current_ticket else None

        print(f"\nStep {step_count}")
        print(f"Current Ticket: {current_ticket_id if current_ticket_id else 'None'}")

        action_source = "model"

        if not api_disabled:
            prompt = create_prompt(obs)
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are an expert bug triage engineer. Respond with valid JSON actions only.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0,
                    max_tokens=220,
                )

                response_text = response.choices[0].message.content or ""
                action = parse_model_response(response_text)
            except Exception as e:
                print(f"API Error: {e}")
                if is_rate_limit_error(e):
                    api_disabled = True
                    print("Rate limit detected. Switching to fallback policy for the rest of this episode.")
                action, action_source = fallback_action(obs, ticket_plan)
        else:
            action, action_source = fallback_action(obs, ticket_plan)

        action, guard_reason = apply_progress_guards(
            action=action,
            observation=obs,
            action_history_by_ticket=action_history_by_ticket,
            step_count_by_ticket=step_count_by_ticket,
            max_steps_per_ticket=max_steps_per_ticket,
        )
        if guard_reason:
            action_source = guard_reason

        try:
            obs, reward, done, info = env.step(action)

            print(f"Action: {action.action_type} ({action_source})")
            print(f"Reward: {reward.step_reward:.3f} (cumulative: {reward.cumulative_reward:.3f})")
            print(f"Result: {obs.last_action_result}")

            episode_actions.append(
                {
                    "step": step_count,
                    "action": action.model_dump(),
                    "reward": reward.step_reward,
                    "source": action_source,
                }
            )

            if current_ticket_id:
                action_history_by_ticket[current_ticket_id].append(action.action_type)
                step_count_by_ticket[current_ticket_id] += 1

        except Exception as e:
            print(f"Step Error: {e}")
            break

        hard_limit = (env.current_task.step_budget + 20) if env.current_task else 220
        if step_count > hard_limit:
            print("Hit safety step limit")
            break

    state = env.state()
    grader = BugTriageGrader(task_id=task_id)

    grader_result = grader.grade_episode(
        episode_actions=episode_actions,
        ground_truths=[gt.model_dump() for gt in env.current_task.ground_truths],
        metrics=info.get("metrics", {}),
    )

    print(f"\n{'='*60}")
    print(f"Task Complete: {task_id}")
    print(f"Final Score: {grader_result.score:.3f}")
    print(f"Passed: {grader_result.passed}")
    print("\nSubscores:")
    for key, value in grader_result.subscores.items():
        print(f"  {key}: {value:.3f}")

    if grader_result.mistakes:
        print("\nMistakes:")
        for mistake in grader_result.mistakes:
            print(f"  - {mistake}")
    print(f"{'='*60}\n")

    return {
        "task_id": task_id,
        "score": grader_result.score,
        "subscores": grader_result.subscores,
        "mistakes": grader_result.mistakes,
        "passed": grader_result.passed,
        "steps_used": state.steps_used,
        "cumulative_reward": state.cumulative_reward,
    }


def main():
    parser = argparse.ArgumentParser(description="Run baseline inference for Bug Triage OpenEnv")
    parser.add_argument(
        "--provider",
        type=str,
        choices=["groq", "openai"],
        default=None,
        help="LLM provider (default: LLM_PROVIDER in .env, otherwise groq)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Model name (defaults to GROQ_MODEL/OPENAI_MODEL in .env)",
    )
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="Random seed")
    parser.add_argument(
        "--max-steps-per-ticket",
        type=int,
        default=4,
        help="Force next_ticket after this many actions on one ticket.",
    )
    parser.add_argument(
        "--tasks",
        nargs="+",
        default=["bug_triage_easy", "bug_triage_medium", "bug_triage_hard"],
        help="Tasks to run",
    )
    args = parser.parse_args()

    provider = (args.provider or DEFAULT_PROVIDER).strip().lower()
    model = args.model or get_default_model(provider)

    try:
        client = build_client(provider)
    except ValueError as e:
        print(f"Error: {e}")
        return

    print(f"Provider: {provider}")
    print(f"Model: {model}")

    env = BugTriageEnv()

    results = []
    for task_id in args.tasks:
        try:
            result = run_episode(
                env=env,
                client=client,
                model=model,
                task_id=task_id,
                seed=args.seed,
                max_steps_per_ticket=args.max_steps_per_ticket,
            )
            results.append(result)
        except Exception as e:
            print(f"Error running task {task_id}: {e}")
            import traceback

            traceback.print_exc()

    if results:
        mean_score = sum(r["score"] for r in results) / len(results)

        print("\n" + "=" * 60)
        print("FINAL RESULTS")
        print("=" * 60)
        print(f"\n{'Task':<25} {'Score':<10} {'Passed':<10}")
        print("-" * 60)
        for r in results:
            print(f"{r['task_id']:<25} {r['score']:<10.3f} {str(r['passed']):<10}")
        print("-" * 60)
        print(f"{'Mean Score':<25} {mean_score:<10.3f}")
        print("=" * 60)

        output = {
            "timestamp": datetime.now().isoformat(),
            "provider": provider,
            "model": model,
            "seed": args.seed,
            "max_steps_per_ticket": args.max_steps_per_ticket,
            "results": results,
            "mean_score": mean_score,
        }

        os.makedirs("artifacts", exist_ok=True)
        output_file = "artifacts/baseline_scores.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2)

        print(f"\nResults saved to: {output_file}")


if __name__ == "__main__":
    main()
