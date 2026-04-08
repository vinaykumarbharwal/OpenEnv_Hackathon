"""Deterministic baseline runner for Bug Triage OpenEnv."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

from openai import OpenAI


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import inference as inference_module  # noqa: E402
from inference import (  # noqa: E402
    MAX_STEPS,
    MAX_STEPS_PER_TICKET,
    MODEL_NAME as DEFAULT_MODEL_NAME,
    SEED as DEFAULT_SEED,
    TASKS as DEFAULT_TASKS,
    _fallback_action,
    _guard_action,
    _request_model_action,
)
from openenv_bug_triage import BugTriageEnv  # noqa: E402
from openenv_bug_triage.grader import BugTriageGrader  # noqa: E402

API_BASE_URL = os.getenv("API_BASE_URL", "https://router.huggingface.co/v1")
MODEL_NAME = os.getenv("MODEL_NAME", DEFAULT_MODEL_NAME)
HF_TOKEN = os.getenv("HF_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


def _as_bool(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _build_client(offline_mode: bool) -> OpenAI | None:
    if offline_mode:
        return None

    api_key = HF_TOKEN or OPENAI_API_KEY
    if not api_key:
        raise ValueError(
            "HF_TOKEN is required for live baseline runs. "
            "OPENAI_API_KEY is also accepted for direct OpenAI endpoints."
        )

    return OpenAI(
        api_key=api_key,
        base_url=API_BASE_URL,
        max_retries=0,
        timeout=30,
    )


def run_task(
    task_id: str,
    seed: int,
    model_name: str,
    max_steps_per_ticket: int,
    offline_mode: bool,
    client: OpenAI | None,
) -> dict[str, object]:
    """Run one task and return reproducible grading metadata."""
    env = BugTriageEnv()
    obs = env.reset(task_id=task_id, seed=seed)

    done = False
    step_no = 0
    plans: dict[str, dict] = {}
    action_history_by_ticket: dict[str, list[str]] = defaultdict(list)
    steps_by_ticket: dict[str, int] = defaultdict(int)
    episode_actions: list[dict] = []
    info: dict[str, object] = {"metrics": {}}
    rewards: list[float] = []
    api_disabled = offline_mode

    while not done and step_no < MAX_STEPS:
        step_no += 1
        current_ticket_id = obs.current_ticket.ticket_id if obs.current_ticket else None

        if client is not None and not api_disabled:
            try:
                action = _request_model_action(client, obs)
                action_source = "model"
            except Exception:
                api_disabled = True
                action = _fallback_action(obs, plans)
                action_source = "fallback"
        else:
            action = _fallback_action(obs, plans)
            action_source = "fallback"

        action = _guard_action(action, obs, action_history_by_ticket, steps_by_ticket)
        obs, reward, done, info = env.step(action)

        rewards.append(reward.step_reward)
        episode_actions.append(
            {
                "step": step_no,
                "action": action.model_dump(exclude_none=True),
                "source": action_source,
                "reward": reward.step_reward,
            }
        )

        if current_ticket_id:
            action_history_by_ticket[current_ticket_id].append(action.action_type)
            steps_by_ticket[current_ticket_id] += 1

        if current_ticket_id and steps_by_ticket[current_ticket_id] > max_steps_per_ticket:
            # The guard should already prevent this, but keeping a hard assertion
            # here makes debugging easier if the policy ever regresses.
            raise RuntimeError(
                f"Exceeded max_steps_per_ticket for {current_ticket_id}: {steps_by_ticket[current_ticket_id]}"
            )

    grader = BugTriageGrader(task_id=task_id)
    ground_truths = [gt.model_dump() for gt in env.current_task.ground_truths] if env.current_task else []
    grader_result = grader.grade_episode(
        episode_actions=episode_actions,
        ground_truths=ground_truths,
        metrics=info.get("metrics", {}),
    )
    final_state = env.state()

    return {
        "task_id": task_id,
        "seed": seed,
        "model": model_name,
        "offline_mode": offline_mode,
        "score": grader_result.score,
        "passed": grader_result.passed,
        "steps_used": final_state.steps_used,
        "cumulative_reward": final_state.cumulative_reward,
        "subscores": grader_result.subscores,
        "mistakes": grader_result.mistakes,
        "metrics": info.get("metrics", {}),
        "rewards": rewards,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run deterministic baseline evaluation.")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="Task shuffle seed.")
    parser.add_argument(
        "--tasks",
        nargs="+",
        default=list(DEFAULT_TASKS),
        help="Task ids to evaluate.",
    )
    parser.add_argument(
        "--model",
        default=MODEL_NAME,
        help="Model name for live runs. Ignored in offline mode.",
    )
    parser.add_argument(
        "--max-steps-per-ticket",
        type=int,
        default=MAX_STEPS_PER_TICKET,
        help="Safety cap before the policy is forced to move on.",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Run the deterministic fallback policy without calling the API.",
    )
    args = parser.parse_args()

    offline_mode = args.offline or _as_bool(os.getenv("OPENENV_OFFLINE"))

    try:
        client = _build_client(offline_mode=offline_mode)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    inference_module.MODEL_NAME = args.model

    results = [
        run_task(
            task_id=task_id,
            seed=args.seed,
            model_name=args.model,
            max_steps_per_ticket=args.max_steps_per_ticket,
            offline_mode=offline_mode,
            client=client,
        )
        for task_id in args.tasks
    ]

    mean_score = sum(float(item["score"]) for item in results) / len(results) if results else 0.0
    payload = {
        "api_base_url": API_BASE_URL,
        "model": args.model,
        "offline_mode": offline_mode,
        "seed": args.seed,
        "max_steps_per_ticket": args.max_steps_per_ticket,
        "results": results,
        "mean_score": mean_score,
    }

    artifacts_dir = PROJECT_ROOT / "artifacts"
    artifacts_dir.mkdir(exist_ok=True)
    output_path = artifacts_dir / "baseline_scores.json"
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print("Baseline results")
    for result in results:
        print(
            f"- {result['task_id']}: score={result['score']:.4f} "
            f"passed={result['passed']} steps={result['steps_used']}"
        )
    print(f"Mean score: {mean_score:.4f}")
    print(f"Saved artifact: {output_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
