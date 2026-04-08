"""Test OpenEnv API contract compliance."""

import pytest

from openenv_bug_triage import BugTriageEnv
from openenv_bug_triage.models import ActionModel, ClassifyAction


def test_reset_all_tasks():
    """Environment reset should work for all registered tasks."""
    env = BugTriageEnv()
    for task_id in ["bug_triage_easy", "bug_triage_medium", "bug_triage_hard"]:
        obs = env.reset(task_id=task_id, seed=42)
        assert obs.current_ticket is not None
        assert obs.steps_used == 0


def test_step():
    """Test environment step."""
    env = BugTriageEnv()
    obs = env.reset(task_id="bug_triage_easy", seed=42)

    action = ActionModel(
        action_type="classify",
        classify=ClassifyAction(
            severity="sev2",
            priority="p2",
            component="api-gateway",
        ),
    )

    obs, reward, done, info = env.step(action)
    assert -1.0 <= reward.step_reward <= 1.0
    assert obs.steps_used == 1


def test_state():
    """Test state retrieval."""
    env = BugTriageEnv()
    env.reset(task_id="bug_triage_easy", seed=42)
    state = env.state()
    assert state.current_task_id == "bug_triage_easy"
    assert state.episode_done is False


def test_action_model_rejects_mismatched_payloads():
    """Typed actions should reject payloads that do not match the action type."""
    with pytest.raises(ValueError):
        ActionModel(
            action_type="next_ticket",
            classify=ClassifyAction(
                severity="sev2",
                priority="p2",
                component="api-gateway",
            ),
        )
