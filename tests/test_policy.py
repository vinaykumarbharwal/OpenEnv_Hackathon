from __future__ import annotations

from server.environment import BugTriageEnv
from server.policy import recommend_action


def test_duplicate_ticket_short_circuits_after_mark_duplicate() -> None:
    env = BugTriageEnv()
    observation = env.reset(task_id="bug_triage_easy", seed=42)

    duplicate_index = next(
        index
        for index, ticket in enumerate(env.current_task.tickets)
        if ticket.ticket_id == "BUG-1004"
    )
    env.current_ticket_index = duplicate_index
    observation = env._get_observation()

    first_action, _ = recommend_action(observation, action_history=[])
    second_action, _ = recommend_action(observation, action_history=["mark_duplicate"])

    assert first_action.action_type == "mark_duplicate"
    assert second_action.action_type == "next_ticket"
