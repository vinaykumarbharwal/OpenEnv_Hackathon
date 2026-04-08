"""
Main BugTriageEnv implementation following OpenEnv specification.
"""

from typing import Optional
from .models import (
    ObservationModel,
    ActionModel,
    RewardModel,
    StateModel,
    CurrentTicketModel,
    QueueStatsModel,
    TicketStateModel,
)
from .tasks import load_task, TaskDefinition
from .reward import RewardCalculator
from .grader import BugTriageGrader


DEFAULT_SEED = 42


class BugTriageEnv:
    """
    Bug Triage OpenEnv Environment.
    
    Simulates real-world software bug triage workflows.
    """
    
    def __init__(self):
        self.current_task: Optional[TaskDefinition] = None
        self.current_ticket_index: int = 0
        self.steps_used: int = 0
        self.episode_done: bool = False
        self.reward_calculator = RewardCalculator()
        self.cumulative_reward: float = 0.0
        self.ticket_states: list[dict] = []
        self.last_action_result: Optional[str] = None
        
        # Metrics for grading
        self.metrics = {}
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
        Reset environment to start a new episode.
        
        Args:
            task_id: One of 'bug_triage_easy', 'bug_triage_medium', 'bug_triage_hard'
                     If None, defaults to 'bug_triage_easy'
            seed: Random seed for deterministic shuffling (default: 42)
        
        Returns:
            Initial observation
        """
        # Default values
        if task_id is None:
            task_id = "bug_triage_easy"
        if seed is None:
            seed = DEFAULT_SEED
        
        # Load task
        self.current_task = load_task(task_id, seed=seed)
        
        # Reset state
        self.current_ticket_index = 0
        self.steps_used = 0
        self.episode_done = False
        self.cumulative_reward = 0.0
        self.last_action_result = None
        
        # Initialize ticket states
        self.ticket_states = [
            {
                "ticket_id": ticket.ticket_id,
                "triaged": False,
                "actions_taken": [],
            }
            for ticket in self.current_task.tickets
        ]
        
        # Reset reward calculator
        self.reward_calculator.reset()
        
        self._critical_ticket_ids = {
            gt.ticket_id for gt in self.current_task.ground_truths
            if gt.true_severity in ["sev0", "sev1"]
        }
        self._duplicate_ticket_ids = {
            gt.ticket_id for gt in self.current_task.ground_truths
            if gt.duplicate_of is not None
        }
        self._info_needed_ticket_ids = {
            gt.ticket_id for gt in self.current_task.ground_truths
            if gt.needs_more_info
        }
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

        label_total = sum(
            1 for gt in self.current_task.ground_truths
            if gt.duplicate_of is None
        )

        # Initialize metrics
        self.metrics = {
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
            "critical_severity_total": len(self._critical_ticket_ids),
            "sla_met": 0,
            "sla_total": len(self._critical_ticket_ids),
            "escalation_correct": 0,
            "escalation_total": len(self._critical_ticket_ids),
            "destructive_actions": 0,
            "missed_critical_escalation": 0,
            "steps_used": 0,
            "step_budget": self.current_task.step_budget,
            "label_total": label_total,
            "assignment_total": label_total,
        }
        
        return self._get_observation()
    
    def step(
        self,
        action: ActionModel,
    ) -> tuple[ObservationModel, RewardModel, bool, dict]:
        """
        Execute one step with the given action.
        
        Args:
            action: Action to take
        
        Returns:
            tuple of (observation, reward, done, info)
        """
        if self.episode_done:
            raise RuntimeError("Episode is done. Call reset() to start new episode.")
        
        if self.current_task is None:
            raise RuntimeError("No task loaded. Call reset() first.")
        
        # Validate action
        is_valid, validation_error = self._validate_action(action)
        
        # Get current ticket
        current_ticket = self.current_task.tickets[self.current_ticket_index]
        ground_truth = self.current_task.get_ground_truth(current_ticket.ticket_id)
        
        # Calculate reward
        is_critical = ground_truth.true_severity in ["sev0", "sev1"]
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
        
        # Update metrics based on action
        if is_valid:
            self._update_metrics(action, ground_truth, current_ticket.ticket_id)
        else:
            self.metrics["major_mistakes"] += 1
        
        # Update ticket state
        self.ticket_states[self.current_ticket_index]["actions_taken"].append(
            action.action_type
        )
        
        # Handle action result
        if not is_valid:
            self.last_action_result = f"Invalid action: {validation_error}"
        else:
            self.last_action_result = self._execute_action(action, current_ticket)
        
        # Check if episode is done
        self._check_done()
        
        # Apply terminal bonus/penalty if done
        if self.episode_done:
            all_critical_triaged = self._all_critical_triaged()
            budget_exhausted = self.steps_used >= self.current_task.step_budget
            critical_remaining = self._has_critical_remaining()
            
            if all_critical_triaged:
                terminal_reward, _ = self.reward_calculator.calculate_step_reward(
                    action=action,
                    ground_truth=ground_truth,
                    ticket_id=current_ticket.ticket_id,
                    is_valid=True,
                    is_critical_ticket=False,
                    is_terminal=True,
                    all_critical_triaged=True,
                    budget_exhausted_with_critical=False,
                )
                self.cumulative_reward += terminal_reward
            elif budget_exhausted and critical_remaining:
                terminal_reward, _ = self.reward_calculator.calculate_step_reward(
                    action=action,
                    ground_truth=ground_truth,
                    ticket_id=current_ticket.ticket_id,
                    is_valid=True,
                    is_critical_ticket=False,
                    is_terminal=True,
                    all_critical_triaged=False,
                    budget_exhausted_with_critical=True,
                )
                self.cumulative_reward += terminal_reward
        
        # Create reward model
        reward_model = RewardModel(
            step_reward=step_reward,
            cumulative_reward=self.cumulative_reward,
            reward_breakdown=breakdown,
        )
        
        # Create observation
        observation = self._get_observation()
        
        # Info dict
        info = {
            "validation_error": validation_error if not is_valid else None,
            "metrics": self.metrics.copy(),
        }
        
        return observation, reward_model, self.episode_done, info
    
    def state(self) -> StateModel:
        """
        Get current environment state.
        
        Returns:
            Full state of the environment
        """
        if self.current_task is None:
            raise RuntimeError("No task loaded. Call reset() first.")
        
        ticket_states = [
            TicketStateModel(
                ticket_id=ts["ticket_id"],
                triaged=ts["triaged"],
                actions_taken=ts["actions_taken"],
            )
            for ts in self.ticket_states
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
    
    # Private helper methods
    
    def _get_observation(self) -> ObservationModel:
        """Create observation from current state."""
        if self.current_task is None or self.episode_done:
            # Return empty observation
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
        
        # Get current ticket
        current_ticket = self.current_task.tickets[self.current_ticket_index]
        
        # Calculate queue stats
        remaining_count = len(self.current_task.tickets) - self.current_ticket_index
        urgent_count = sum(
            1 for i in range(self.current_ticket_index, len(self.current_task.tickets))
            if self.current_task.get_ground_truth(
                self.current_task.tickets[i].ticket_id
            ).true_severity in ["sev0", "sev1"]
        )
        sla_at_risk_count = urgent_count  # Simplified: all urgent are at SLA risk
        
        return ObservationModel(
            current_ticket=CurrentTicketModel(**current_ticket.model_dump()),
            queue_stats=QueueStatsModel(
                remaining_count=remaining_count,
                urgent_count=urgent_count,
                sla_at_risk_count=sla_at_risk_count,
            ),
            last_action_result=self.last_action_result,
            available_teams=self.current_task.available_teams,
            available_components=self.current_task.available_components,
            steps_used=self.steps_used,
            steps_remaining=max(0, self.current_task.step_budget - self.steps_used),
            partial_score=self._calculate_partial_score(),
        )
    
    def _validate_action(self, action: ActionModel) -> tuple[bool, Optional[str]]:
        """Validate action is legal."""
        # Check if ticket exists for duplicate marking
        if action.action_type == "mark_duplicate" and action.mark_duplicate:
            canonical_id = action.mark_duplicate.canonical_ticket_id
            ticket_ids = [t.ticket_id for t in self.current_task.tickets]
            if canonical_id not in ticket_ids:
                return False, f"Unknown ticket ID: {canonical_id}"
        
        # Check if team is valid
        if action.action_type == "assign" and action.assign:
            if action.assign.team not in self.current_task.available_teams:
                return False, f"Unknown team: {action.assign.team}"
        
        # Check if component is valid
        if action.action_type == "classify" and action.classify:
            if action.classify.component not in self.current_task.available_components:
                return False, f"Unknown component: {action.classify.component}"
        
        return True, None
    
    def _execute_action(self, action: ActionModel, current_ticket) -> str:
        """Execute action and return result message."""
        if action.action_type == "next_ticket":
            if self.current_ticket_index < len(self.current_task.tickets) - 1:
                self.current_ticket_index += 1
                return "Moved to next ticket"
            else:
                # Move pointer past the end so _check_done can terminate the episode.
                self.current_ticket_index = len(self.current_task.tickets)
                return "No more tickets in queue"
        
        elif action.action_type == "classify":
            self.ticket_states[self.current_ticket_index]["triaged"] = True
            return f"Classified as {action.classify.severity}/{action.classify.priority}"
        
        elif action.action_type == "assign":
            return f"Assigned to team: {action.assign.team}"
        
        elif action.action_type == "mark_duplicate":
            return f"Marked as duplicate of {action.mark_duplicate.canonical_ticket_id}"
        
        elif action.action_type == "request_info":
            return f"Requested {action.request_info.info_type}"
        
        elif action.action_type == "defer":
            return f"Deferred: {action.defer.reason}"
        
        elif action.action_type == "close":
            return f"Closed: {action.close.reason}"
        
        elif action.action_type == "escalate_incident":
            return f"Escalated incident"
        
        return "Action executed"
    
    def _update_metrics(self, action: ActionModel, ground_truth, ticket_id: str):
        """Update metrics for grading."""
        is_duplicate_ticket = ground_truth.duplicate_of is not None
        is_critical_ticket = ground_truth.true_severity in ["sev0", "sev1"]

        if is_critical_ticket and action.action_type in ["classify", "mark_duplicate", "escalate_incident"]:
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

        if action.action_type in ["close", "defer"]:
            if not ground_truth.duplicate_of and ground_truth.needs_more_info:
                self.metrics["incorrect_close_count"] += 1
                self.metrics["destructive_actions"] += 1

        if action.action_type == "escalate_incident":
            if is_critical_ticket:
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
    
    def _check_done(self):
        """Check if episode should end."""
        # Episode ends if:
        # 1. Step budget exhausted
        # 2. All tickets processed (moved past last ticket)
        
        if self.steps_used >= self.current_task.step_budget:
            self.episode_done = True
        
        # If moved past last ticket
        if self.current_ticket_index >= len(self.current_task.tickets):
            self.episode_done = True
    
    def _all_critical_triaged(self) -> bool:
        """Check if all critical tickets have been triaged."""
        for i, ticket in enumerate(self.current_task.tickets):
            gt = self.current_task.get_ground_truth(ticket.ticket_id)
            if gt.true_severity in ["sev0", "sev1"]:
                if not self.ticket_states[i]["triaged"]:
                    return False
        return True
    
    def _has_critical_remaining(self) -> bool:
        """Check if there are untriaged critical tickets."""
        for i in range(self.current_ticket_index, len(self.current_task.tickets)):
            ticket = self.current_task.tickets[i]
            gt = self.current_task.get_ground_truth(ticket.ticket_id)
            if gt.true_severity in ["sev0", "sev1"]:
                if not self.ticket_states[i]["triaged"]:
                    return True
        return False
    
    def _calculate_partial_score(self) -> float:
        """Calculate partial score for intermediate feedback."""
        if self.steps_used == 0:
            return 0.0
        
        total_tickets = len(self.current_task.tickets) if self.current_task else 1
        
        # Simple weighted average of correctness
        score = 0.0
        score += self.metrics.get("severity_correct", 0) / total_tickets * 0.25
        score += self.metrics.get("priority_correct", 0) / total_tickets * 0.20
        score += self.metrics.get("component_correct", 0) / total_tickets * 0.25
        score += self.metrics.get("team_correct", 0) / total_tickets * 0.15
        
        return min(1.0, score)


if __name__ == "__main__":
    # Quick test
    env = BugTriageEnv()
    obs = env.reset(task_id="bug_triage_easy", seed=42)
    print(f"Reset complete. Current ticket: {obs.current_ticket.ticket_id if obs.current_ticket else 'None'}")
    print(f"Queue stats: {obs.queue_stats}")
    state = env.state()
    print(f"State: {state.current_task_id}, {state.total_tickets} tickets")

