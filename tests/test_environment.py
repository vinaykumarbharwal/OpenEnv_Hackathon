"""
Tests for the BugTriageEnv environment (server/environment.py).

Covers the reset/step/done lifecycle along with reward calculation and
metric tracking correctness.
"""

from __future__ import annotations

import pytest
from models import ActionModel
from server.environment import BugTriageEnv


@pytest.fixture()
def env() -> BugTriageEnv:
    return BugTriageEnv()


@pytest.fixture()
def easy_env(env: BugTriageEnv) -> BugTriageEnv:
    env.reset(task_id="bug_triage_easy", seed=42)
    return env


# ---------------------------------------------------------------------------
# Reset
# ---------------------------------------------------------------------------

class TestReset:
    def test_reset_returns_observation(self, env):
        obs = env.reset(task_id="bug_triage_easy", seed=42)
        assert obs.current_ticket is not None

    def test_reset_sets_steps_to_zero(self, easy_env):
        assert easy_env.steps_used == 0

    def test_reset_episode_not_done(self, easy_env):
        assert easy_env.episode_done is False

    def test_reset_clears_cumulative_reward(self, easy_env):
        assert easy_env.cumulative_reward == 0.0

    def test_reset_all_tasks(self, env):
        for task_id in ("bug_triage_easy", "bug_triage_medium", "bug_triage_hard"):
            obs = env.reset(task_id=task_id, seed=42)
            assert obs.current_ticket is not None

    def test_reset_unknown_task_raises(self, env):
        with pytest.raises((FileNotFoundError, ValueError)):
            env.reset(task_id="nonexistent_task")


# ---------------------------------------------------------------------------
# Step — basic lifecycle
# ---------------------------------------------------------------------------

class TestStep:
    def test_step_before_reset_raises(self, env):
        action = ActionModel(action_type="next_ticket", next_ticket={})
        with pytest.raises(RuntimeError):
            env.step(action)

    def test_step_returns_four_values(self, easy_env):
        action = ActionModel(action_type="next_ticket", next_ticket={})
        result = easy_env.step(action)
        assert len(result) == 4

    def test_step_increments_steps_used(self, easy_env):
        action = ActionModel(action_type="next_ticket", next_ticket={})
        easy_env.step(action)
        assert easy_env.steps_used == 1

    def test_step_reward_in_range(self, easy_env):
        action = ActionModel(action_type="next_ticket", next_ticket={})
        _, reward, _, _ = easy_env.step(action)
        assert 0.0 <= reward.step_reward <= 1.0

    def test_next_ticket_advances_index(self, easy_env):
        initial_ticket_id = easy_env.current_task.tickets[easy_env.current_ticket_index].ticket_id
        action = ActionModel(action_type="next_ticket", next_ticket={})
        obs, _, _, _ = easy_env.step(action)
        if obs.current_ticket:
            assert obs.current_ticket.ticket_id != initial_ticket_id


# ---------------------------------------------------------------------------
# Classify action
# ---------------------------------------------------------------------------

class TestClassifyAction:
    def _classify(self, env, severity, priority, component):
        return ActionModel(
            action_type="classify",
            classify={"severity": severity, "priority": priority, "component": component},
        )

    def test_classify_returns_valid_reward(self, easy_env):
        action = self._classify(easy_env, "sev2", "p2", "ios-app")
        _, reward, _, _ = easy_env.step(action)
        assert 0.0 <= reward.step_reward <= 1.0

    def test_classify_invalid_component_rejected(self, easy_env):
        action = self._classify(easy_env, "sev2", "p2", "nonexistent-component")
        _, _, _, info = easy_env.step(action)
        assert info.get("validation_error") is not None


# ---------------------------------------------------------------------------
# Episode done conditions
# ---------------------------------------------------------------------------

class TestEpisodeDone:
    def test_episode_ends_when_budget_exhausted(self, env):
        obs = env.reset(task_id="bug_triage_easy", seed=42)
        budget = env.current_task.step_budget
        action = ActionModel(action_type="next_ticket", next_ticket={})
        done = False
        for _ in range(budget + 5):
            if done:
                break
            _, _, done, _ = env.step(action)
        assert env.episode_done is True

    def test_step_after_done_raises(self, easy_env):
        easy_env.episode_done = True
        action = ActionModel(action_type="next_ticket", next_ticket={})
        with pytest.raises(RuntimeError):
            easy_env.step(action)


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

class TestState:
    def test_state_before_reset_raises(self, env):
        with pytest.raises(RuntimeError):
            env.state()

    def test_state_returns_correct_task_id(self, easy_env):
        state = easy_env.state()
        assert state.current_task_id == "bug_triage_easy"

    def test_state_total_tickets(self, easy_env):
        state = easy_env.state()
        assert state.total_tickets == len(easy_env.current_task.tickets)


# ---------------------------------------------------------------------------
# Partial score
# ---------------------------------------------------------------------------

class TestPartialScore:
    def test_partial_score_zero_before_steps(self, easy_env):
        assert easy_env._calculate_partial_score() == 0.0

    def test_partial_score_in_range_after_step(self, easy_env):
        action = ActionModel(action_type="next_ticket", next_ticket={})
        easy_env.step(action)
        score = easy_env._calculate_partial_score()
        assert 0.0 <= score <= 1.0
