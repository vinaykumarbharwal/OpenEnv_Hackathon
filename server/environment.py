"""Main BugTriageEnv implementation following the OpenEnv API shape."""

from __future__ import annotations

from typing import Any, Optional

from models import (
    ActionModel,
    CurrentTicketModel,
    ObservationModel,
    QueueStatsModel,
    RewardModel,
    StateModel,
    TicketStateModel,
)
from server.tasks import TaskDefinition, load_task

DEFAULT_SEED = 42
DEFAULT_TASK_ID = "bug_triage_easy"
CRITICAL_SEVERITIES = {"sev0", "sev1"}


class RewardCalculator:
    """Calculates rewards for bug triage actions."""

    BASE_REWARD = 0.50

    CORRECT_SEVERITY = 0.20
    CORRECT_PRIORITY = 0.15
    CORRECT_COMPONENT = 0.15
    CORRECT_TEAM = 0.10
    CORRECT_DUPLICATE = 0.15
    CORRECT_REQUEST_INFO = 0.10
    CORRECT_ESCALATION = 0.15

    INCORRECT_CLOSE_DEFER = 0.20
    MISSED_ESCALATION = 0.15
    INVALID_ACTION = 0.30
    REPEATED_NOOP = 0.10
    UNNECESSARY_SWITCH = 0.05

    ALL_CRITICAL_TRIAGED = 0.10
    BUDGET_EXHAUSTED_CRITICAL_REMAINING = 0.10

    def __init__(self):
        self.action_history = []

    def calculate_step_reward(
        self,
        action: ActionModel,
        ground_truth,
        ticket_id: str,
        is_valid: bool,
        is_critical_ticket: bool,
        is_terminal: bool = False,
        all_critical_triaged: bool = False,
        budget_exhausted_with_critical: bool = False,
    ) -> tuple[float, dict[str, float]]:
        """
        Calculate reward for a single step.
        Rewards are in range [0.0, 1.0].

        Returns:
            tuple of (clamped_reward, breakdown_dict)
        """
        breakdown = {}
        total_reward = self.BASE_REWARD

        if not is_valid:
            breakdown["invalid_action_penalty"] = -self.INVALID_ACTION
            total_reward -= self.INVALID_ACTION
            return self._clamp_reward(total_reward), breakdown

        self.action_history.append((ticket_id, action.action_type))

        if action.action_type == "classify" and action.classify:
            if action.classify.severity == ground_truth.true_severity:
                breakdown["correct_severity"] = self.CORRECT_SEVERITY
                total_reward += self.CORRECT_SEVERITY

            if action.classify.priority == ground_truth.true_priority:
                breakdown["correct_priority"] = self.CORRECT_PRIORITY
                total_reward += self.CORRECT_PRIORITY

            if action.classify.component == ground_truth.true_component:
                breakdown["correct_component"] = self.CORRECT_COMPONENT
                total_reward += self.CORRECT_COMPONENT

        if action.action_type == "assign" and action.assign:
            if action.assign.team == ground_truth.true_assignee_team:
                breakdown["correct_team"] = self.CORRECT_TEAM
                total_reward += self.CORRECT_TEAM

        if action.action_type == "mark_duplicate" and action.mark_duplicate:
            if ground_truth.duplicate_of == action.mark_duplicate.canonical_ticket_id:
                breakdown["correct_duplicate"] = self.CORRECT_DUPLICATE
                total_reward += self.CORRECT_DUPLICATE

        if action.action_type == "request_info" and action.request_info:
            if ground_truth.needs_more_info:
                breakdown["correct_request_info"] = self.CORRECT_REQUEST_INFO
                total_reward += self.CORRECT_REQUEST_INFO

        if action.action_type == "escalate_incident" and action.escalate_incident:
            if ground_truth.true_severity in ["sev0", "sev1"]:
                breakdown["correct_escalation"] = self.CORRECT_ESCALATION
                total_reward += self.CORRECT_ESCALATION

        if action.action_type in ["close", "defer"]:
            if not ground_truth.duplicate_of and ground_truth.needs_more_info:
                breakdown["incorrect_close_defer_penalty"] = -self.INCORRECT_CLOSE_DEFER
                total_reward -= self.INCORRECT_CLOSE_DEFER

        if is_critical_ticket and action.action_type != "escalate_incident":
            if ground_truth.true_severity in ["sev0", "sev1"]:
                breakdown["missed_escalation_penalty"] = -self.MISSED_ESCALATION
                total_reward -= self.MISSED_ESCALATION

        if len(self.action_history) >= 3:
            last_three = self.action_history[-3:]
            if last_three[0] == last_three[1] == last_three[2]:
                breakdown["repeated_noop_penalty"] = -self.REPEATED_NOOP
                total_reward -= self.REPEATED_NOOP

        if is_terminal:
            if all_critical_triaged:
                breakdown["all_critical_triaged"] = self.ALL_CRITICAL_TRIAGED
                total_reward += self.ALL_CRITICAL_TRIAGED

            if budget_exhausted_with_critical:
                breakdown["budget_exhausted_penalty"] = -self.BUDGET_EXHAUSTED_CRITICAL_REMAINING
                total_reward -= self.BUDGET_EXHAUSTED_CRITICAL_REMAINING

        return self._clamp_reward(total_reward), breakdown

    def _clamp_reward(self, reward: float) -> float:
        """Clamp reward to [0.0, 1.0] range."""
        return max(0.0, min(1.0, reward))

    def reset(self):
        """Reset action history."""
        self.action_history = []


class BugTriageEnv:
    """Environment simulating a software bug triage workflow."""

    def __init__(self) -> None:
        self.current_task: Optional[TaskDefinition] = None
        self.current_ticket_index: int = 0
        self.steps_used: int = 0
        self.episode_done: bool = False
        self.cumulative_reward: float = 0.0
        self.last_action_result: Optional[str] = None
        self.ticket_states: list[dict[str, Any]] = []
        self._all_ticket_ids: set[str] = set()

        self.reward_calculator = RewardCalculator()
        self.metrics: dict[str, int | float] = {}

        self._critical_ticket_ids: set[str] = set()
        self._duplicate_ticket_ids: set[str] = set()
        self._info_needed_ticket_ids: set[str] = set()

        self._severity_scored_tickets: set[str] = set()
        self._critical_severity_scored_tickets: set[str] = set()
        self._priority_scored_tickets: set[str] = set()
        self._component_scored_tickets: set[str] = set()
        self._team_scored_tickets: set[str] = set()
        self._duplicate_scored_tickets: set[str] = set()
        self._info_request_scored_tickets: set[str] = set()
        self._escalated_ticket_ids: set[str] = set()
        self._escalation_scored_tickets: set[str] = set()
        self._sla_met_ticket_ids: set[str] = set()
        self._missed_critical_ticket_ids: set[str] = set()

    def reset(
        self,
        task_id: Optional[str] = None,
        seed: Optional[int] = None,
    ) -> ObservationModel:
        """
        Reset the environment to start a new episode.

        Args:
            task_id: One of `bug_triage_easy`, `bug_triage_medium`, `bug_triage_hard`.
            seed: Deterministic shuffle seed.
        """
        resolved_task_id = task_id or DEFAULT_TASK_ID
        resolved_seed = DEFAULT_SEED if seed is None else seed

        self.current_task = load_task(resolved_task_id, seed=resolved_seed)
        self._reset_episode_state()
        self._index_ticket_groups()
        self._reset_dedup_metric_sets()
        self.metrics = self._build_metrics()

        return self._get_observation()

    def step(
        self,
        action: ActionModel,
    ) -> tuple[ObservationModel, RewardModel, bool, dict[str, Any]]:
        """Execute one step and return `(observation, reward, done, info)`."""
        if self.episode_done:
            raise RuntimeError("Episode is done. Call reset() to start new episode.")
        if self.current_task is None:
            raise RuntimeError("No task loaded. Call reset() first.")

        current_ticket = self.current_task.tickets[self.current_ticket_index]
        ground_truth = self._ground_truth_or_raise(current_ticket.ticket_id)
        is_valid, validation_error = self._validate_action(action)
        is_critical = self._is_critical_severity(ground_truth.true_severity)

        step_reward, breakdown = self.reward_calculator.calculate_step_reward(
            action=action,
            ground_truth=ground_truth,
            ticket_id=current_ticket.ticket_id,
            is_valid=is_valid,
            is_critical_ticket=is_critical,
        )

        self.cumulative_reward += step_reward
        self.steps_used += 1
        self.metrics["steps_used"] = self.steps_used

        if is_valid:
            self._update_metrics(action, ground_truth, current_ticket.ticket_id)
        else:
            self.metrics["major_mistakes"] += 1

        self.ticket_states[self.current_ticket_index]["actions_taken"].append(action.action_type)

        if not is_valid:
            self.last_action_result = f"Invalid action: {validation_error}"
        else:
            self.last_action_result = self._execute_action(action, current_ticket.ticket_id)

        self._check_done()
        if self.episode_done:
            self._apply_terminal_reward(action, ground_truth, current_ticket.ticket_id)

        reward_model = RewardModel(
            step_reward=step_reward,
            cumulative_reward=self.cumulative_reward,
            reward_breakdown=breakdown,
        )

        error_value = validation_error if not is_valid else None
        info = {
            "validation_error": error_value,
            "last_action_error": error_value,
            "metrics": self.metrics.copy(),
        }
        return self._get_observation(), reward_model, self.episode_done, info

    def state(self) -> StateModel:
        """Return the current full environment state."""
        if self.current_task is None:
            raise RuntimeError("No task loaded. Call reset() first.")

        ticket_states = [
            TicketStateModel(
                ticket_id=ticket_state["ticket_id"],
                triaged=ticket_state["triaged"],
                actions_taken=ticket_state["actions_taken"],
            )
            for ticket_state in self.ticket_states
        ]

        return StateModel(
            current_task_id=self.current_task.task_id,
            current_ticket_index=self.current_ticket_index,
            total_tickets=len(self.current_task.tickets),
            tickets_state=ticket_states,
            steps_used=self.steps_used,
            steps_remaining=max(0, self.current_task.step_budget - self.steps_used),
            cumulative_reward=self.cumulative_reward,
            episode_done=self.episode_done,
        )

    def close(self) -> None:
        """No-op close hook for runners expecting a closeable environment."""
        self.current_task = None
        self.ticket_states = []
        self._all_ticket_ids = set()
        self.episode_done = True

    def _reset_episode_state(self) -> None:
        if self.current_task is None:
            return

        self.current_ticket_index = 0
        self.steps_used = 0
        self.episode_done = False
        self.cumulative_reward = 0.0
        self.last_action_result = None
        self._all_ticket_ids = {ticket.ticket_id for ticket in self.current_task.tickets}

        self.ticket_states = [
            {"ticket_id": ticket.ticket_id, "triaged": False, "actions_taken": []}
            for ticket in self.current_task.tickets
        ]
        self.reward_calculator.reset()

    def _index_ticket_groups(self) -> None:
        if self.current_task is None:
            return

        self._critical_ticket_ids = {
            ground_truth.ticket_id
            for ground_truth in self.current_task.ground_truths
            if self._is_critical_severity(ground_truth.true_severity)
        }
        self._duplicate_ticket_ids = {
            ground_truth.ticket_id
            for ground_truth in self.current_task.ground_truths
            if ground_truth.duplicate_of is not None
        }
        self._info_needed_ticket_ids = {
            ground_truth.ticket_id
            for ground_truth in self.current_task.ground_truths
            if ground_truth.needs_more_info
        }

    def _reset_dedup_metric_sets(self) -> None:
        self._severity_scored_tickets = set()
        self._critical_severity_scored_tickets = set()
        self._priority_scored_tickets = set()
        self._component_scored_tickets = set()
        self._team_scored_tickets = set()
        self._duplicate_scored_tickets = set()
        self._info_request_scored_tickets = set()
        self._escalated_ticket_ids = set()
        self._escalation_scored_tickets = set()
        self._sla_met_ticket_ids = set()
        self._missed_critical_ticket_ids = set()

    def _build_metrics(self) -> dict[str, int | float]:
        if self.current_task is None:
            return {}

        label_total = sum(
            1 for ground_truth in self.current_task.ground_truths if ground_truth.duplicate_of is None
        )
        critical_total = len(self._critical_ticket_ids)

        return {
            "severity_correct": 0,
            "priority_correct": 0,
            "component_correct": 0,
            "team_correct": 0,
            "duplicate_correct": 0,
            "duplicate_total": 0,
            "duplicate_expected_total": len(self._duplicate_ticket_ids),
            "info_request_correct": 0,
            "info_needed_total": len(self._info_needed_ticket_ids),
            "major_mistakes": 0,
            "incorrect_close_count": 0,
            "critical_severity_correct": 0,
            "critical_severity_total": critical_total,
            "sla_met": 0,
            "sla_total": critical_total,
            "escalation_correct": 0,
            "escalation_total": critical_total,
            "destructive_actions": 0,
            "missed_critical_escalation": 0,
            "steps_used": 0,
            "step_budget": self.current_task.step_budget,
            "label_total": label_total,
            "assignment_total": label_total,
        }

    def _ground_truth_or_raise(self, ticket_id: str):
        if self.current_task is None:
            raise RuntimeError("No task loaded. Call reset() first.")
        ground_truth = self.current_task.get_ground_truth(ticket_id)
        if ground_truth is None:
            raise RuntimeError(f"Ground truth missing for ticket: {ticket_id}")
        return ground_truth

    @staticmethod
    def _is_critical_severity(severity: str) -> bool:
        return severity in CRITICAL_SEVERITIES

    def _get_observation(self) -> ObservationModel:
        """Build an observation from the current internal state."""
        if self.current_task is None or self.episode_done:
            return ObservationModel(
                current_ticket=None,
                queue_stats=QueueStatsModel(
                    remaining_count=0,
                    urgent_count=0,
                    sla_at_risk_count=0,
                ),
                last_action_result=self.last_action_result,
                available_teams=[],
                available_components=[],
                steps_used=self.steps_used,
                steps_remaining=0,
                partial_score=self._calculate_partial_score(),
            )

        current_ticket = self.current_task.tickets[self.current_ticket_index]
        remaining_count = len(self.current_task.tickets) - self.current_ticket_index
        urgent_count = sum(
            1
            for idx in range(self.current_ticket_index, len(self.current_task.tickets))
            if self._is_critical_severity(
                self._ground_truth_or_raise(self.current_task.tickets[idx].ticket_id).true_severity
            )
        )

        return ObservationModel(
            current_ticket=CurrentTicketModel(**current_ticket.model_dump()),
            queue_stats=QueueStatsModel(
                remaining_count=remaining_count,
                urgent_count=urgent_count,
                sla_at_risk_count=urgent_count,
            ),
            last_action_result=self.last_action_result,
            available_teams=self.current_task.available_teams,
            available_components=self.current_task.available_components,
            steps_used=self.steps_used,
            steps_remaining=max(0, self.current_task.step_budget - self.steps_used),
            partial_score=self._calculate_partial_score(),
        )

    def _validate_action(self, action: ActionModel) -> tuple[bool, Optional[str]]:
        """Validate action legality in the current task context."""
        if self.current_task is None:
            return False, "No task loaded"

        if action.action_type == "mark_duplicate" and action.mark_duplicate:
            canonical_id = action.mark_duplicate.canonical_ticket_id
            if canonical_id not in self._all_ticket_ids:
                return False, f"Unknown ticket ID: {canonical_id}"

        if action.action_type == "assign" and action.assign:
            if action.assign.team not in self.current_task.available_teams:
                return False, f"Unknown team: {action.assign.team}"

        if action.action_type == "classify" and action.classify:
            if action.classify.component not in self.current_task.available_components:
                return False, f"Unknown component: {action.classify.component}"

        return True, None

    def _execute_action(self, action: ActionModel, ticket_id: str) -> str:
        """Apply action side-effects and return a short status message."""
        if self.current_task is None:
            return "No task loaded"

        if action.action_type == "next_ticket":
            if self.current_ticket_index < len(self.current_task.tickets) - 1:
                self.current_ticket_index += 1
                return "Moved to next ticket"
            self.current_ticket_index = len(self.current_task.tickets)
            return "No more tickets in queue"

        if action.action_type == "classify" and action.classify:
            self.ticket_states[self.current_ticket_index]["triaged"] = True
            return f"Classified as {action.classify.severity}/{action.classify.priority}"

        if action.action_type == "assign" and action.assign:
            return f"Assigned to team: {action.assign.team}"

        if action.action_type == "mark_duplicate" and action.mark_duplicate:
            return f"Marked as duplicate of {action.mark_duplicate.canonical_ticket_id}"

        if action.action_type == "request_info" and action.request_info:
            return f"Requested {action.request_info.info_type}"

        if action.action_type == "defer" and action.defer:
            return f"Deferred: {action.defer.reason}"

        if action.action_type == "close" and action.close:
            return f"Closed: {action.close.reason}"

        if action.action_type == "escalate_incident":
            return "Escalated incident"

        return f"Action executed for {ticket_id}"

    def _update_metrics(self, action: ActionModel, ground_truth, ticket_id: str) -> None:
        """Update deterministic grading metrics for this step."""
        is_duplicate_ticket = ground_truth.duplicate_of is not None
        is_critical_ticket = self._is_critical_severity(ground_truth.true_severity)

        if is_critical_ticket and action.action_type in {"classify", "mark_duplicate", "escalate_incident"}:
            if ticket_id not in self._sla_met_ticket_ids:
                self._sla_met_ticket_ids.add(ticket_id)
                self.metrics["sla_met"] += 1

        if action.action_type == "classify" and action.classify and not is_duplicate_ticket:
            if action.classify.severity == ground_truth.true_severity:
                if ticket_id not in self._severity_scored_tickets:
                    self._severity_scored_tickets.add(ticket_id)
                    self.metrics["severity_correct"] += 1

                if is_critical_ticket and ticket_id not in self._critical_severity_scored_tickets:
                    self._critical_severity_scored_tickets.add(ticket_id)
                    self.metrics["critical_severity_correct"] += 1

            if action.classify.priority == ground_truth.true_priority:
                if ticket_id not in self._priority_scored_tickets:
                    self._priority_scored_tickets.add(ticket_id)
                    self.metrics["priority_correct"] += 1

            if action.classify.component == ground_truth.true_component:
                if ticket_id not in self._component_scored_tickets:
                    self._component_scored_tickets.add(ticket_id)
                    self.metrics["component_correct"] += 1

        if action.action_type == "assign" and action.assign and not is_duplicate_ticket:
            if action.assign.team == ground_truth.true_assignee_team:
                if ticket_id not in self._team_scored_tickets:
                    self._team_scored_tickets.add(ticket_id)
                    self.metrics["team_correct"] += 1

        if action.action_type == "mark_duplicate" and action.mark_duplicate:
            self.metrics["duplicate_total"] += 1
            if (
                ground_truth.duplicate_of == action.mark_duplicate.canonical_ticket_id
                and ticket_id not in self._duplicate_scored_tickets
            ):
                self._duplicate_scored_tickets.add(ticket_id)
                self.metrics["duplicate_correct"] += 1

        if action.action_type == "request_info" and ground_truth.needs_more_info:
            if ticket_id not in self._info_request_scored_tickets:
                self._info_request_scored_tickets.add(ticket_id)
                self.metrics["info_request_correct"] += 1

        if action.action_type in {"close", "defer"}:
            if not ground_truth.duplicate_of and ground_truth.needs_more_info:
                self.metrics["incorrect_close_count"] += 1
                self.metrics["destructive_actions"] += 1

        if action.action_type == "escalate_incident" and is_critical_ticket:
            self._escalated_ticket_ids.add(ticket_id)
            if ticket_id not in self._escalation_scored_tickets:
                self._escalation_scored_tickets.add(ticket_id)
                self.metrics["escalation_correct"] += 1

        if (
            action.action_type == "next_ticket"
            and is_critical_ticket
            and ticket_id not in self._escalated_ticket_ids
            and ticket_id not in self._missed_critical_ticket_ids
        ):
            self._missed_critical_ticket_ids.add(ticket_id)
            self.metrics["missed_critical_escalation"] += 1

    def _check_done(self) -> None:
        if self.current_task is None:
            return
        if self.steps_used >= self.current_task.step_budget:
            self.episode_done = True
        if self.current_ticket_index >= len(self.current_task.tickets):
            self.episode_done = True

    def _apply_terminal_reward(self, action: ActionModel, ground_truth, ticket_id: str) -> None:
        if self.current_task is None:
            return

        all_critical_triaged = self._all_critical_triaged()
        budget_exhausted = self.steps_used >= self.current_task.step_budget
        critical_remaining = self._has_critical_remaining()

        if all_critical_triaged:
            terminal_reward, _ = self.reward_calculator.calculate_step_reward(
                action=action,
                ground_truth=ground_truth,
                ticket_id=ticket_id,
                is_valid=True,
                is_critical_ticket=False,
                is_terminal=True,
                all_critical_triaged=True,
                budget_exhausted_with_critical=False,
            )
            self.cumulative_reward += terminal_reward
            return

        if budget_exhausted and critical_remaining:
            terminal_reward, _ = self.reward_calculator.calculate_step_reward(
                action=action,
                ground_truth=ground_truth,
                ticket_id=ticket_id,
                is_valid=True,
                is_critical_ticket=False,
                is_terminal=True,
                all_critical_triaged=False,
                budget_exhausted_with_critical=True,
            )
            self.cumulative_reward += terminal_reward

    def _all_critical_triaged(self) -> bool:
        if self.current_task is None:
            return True

        for index, ticket in enumerate(self.current_task.tickets):
            ground_truth = self._ground_truth_or_raise(ticket.ticket_id)
            if self._is_critical_severity(ground_truth.true_severity) and not self.ticket_states[index]["triaged"]:
                return False
        return True

    def _has_critical_remaining(self) -> bool:
        if self.current_task is None:
            return False

        for index in range(self.current_ticket_index, len(self.current_task.tickets)):
            ticket = self.current_task.tickets[index]
            ground_truth = self._ground_truth_or_raise(ticket.ticket_id)
            if self._is_critical_severity(ground_truth.true_severity) and not self.ticket_states[index]["triaged"]:
                return True
        return False

    def _calculate_partial_score(self) -> float:
        """Compute a normalised [0, 1] partial score based on grading metrics so far."""
        if self.steps_used == 0 or self.current_task is None:
            return 0.0

        total_tickets = len(self.current_task.tickets)
        if total_tickets == 0:
            return 0.0

        score = 0.0
        score += self.metrics.get("severity_correct", 0) / total_tickets * 0.25
        score += self.metrics.get("priority_correct", 0) / total_tickets * 0.20
        score += self.metrics.get("component_correct", 0) / total_tickets * 0.25
        score += self.metrics.get("team_correct", 0) / total_tickets * 0.15
        return min(1.0, score)


if __name__ == "__main__":
    env = BugTriageEnv()
    observation = env.reset(task_id=DEFAULT_TASK_ID, seed=DEFAULT_SEED)
    print(
        "Reset complete. Current ticket:",
        observation.current_ticket.ticket_id if observation.current_ticket else "None",
    )
    print(f"Queue stats: {observation.queue_stats}")
    print(f"State: {env.state().current_task_id}, {env.state().total_tickets} tickets")
