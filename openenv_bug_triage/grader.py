"""
Deterministic graders for bug triage tasks.
"""

from typing import Optional
from pydantic import BaseModel


class GraderResult(BaseModel):
    """Result from grading an episode."""
    score: float
    subscores: dict[str, float]
    mistakes: list[str]
    passed: bool


class BugTriageGrader:
    """Deterministic grader for bug triage episodes."""
    
    def __init__(self, task_id: str, threshold: float = 0.75):
        self.task_id = task_id
        self.threshold = threshold
        self.weights = self._get_task_weights(task_id)
    
    def _get_task_weights(self, task_id: str) -> dict[str, float]:
        """Get scoring weights based on task difficulty."""
        if task_id == "bug_triage_easy":
            return {
                "severity_accuracy": 0.25,
                "priority_accuracy": 0.20,
                "component_accuracy": 0.25,
                "team_accuracy": 0.15,
                "duplicate_handling": 0.10,
                "efficiency": 0.05,
            }
        elif task_id == "bug_triage_medium":
            return {
                "severity_accuracy": 0.20,
                "priority_accuracy": 0.15,
                "component_accuracy": 0.20,
                "team_accuracy": 0.15,
                "duplicate_handling": 0.15,
                "info_request_accuracy": 0.10,
                "efficiency": 0.05,
            }
        elif task_id == "bug_triage_hard":
            return {
                "critical_severity_accuracy": 0.30,
                "priority_accuracy": 0.15,
                "component_accuracy": 0.15,
                "team_accuracy": 0.10,
                "sla_handling": 0.15,
                "escalation_accuracy": 0.10,
                "policy_quality": 0.05,
            }
        else:
            raise ValueError(f"Unknown task_id: {task_id}")
    
    def grade_episode(
        self,
        episode_actions: list[dict],
        ground_truths: list[dict],
        metrics: dict,
    ) -> GraderResult:
        """
        Grade a complete episode.
        
        Args:
            episode_actions: List of actions taken during the episode
            ground_truths: List of ground truth labels for each ticket
            metrics: Additional metrics collected during the episode
        
        Returns:
            GraderResult with score, subscores, mistakes, and pass/fail
        """
        subscores = {}
        mistakes = []
        
        # Calculate subscores based on task type
        if self.task_id == "bug_triage_easy":
            subscores, mistakes = self._grade_easy(episode_actions, ground_truths, metrics)
        elif self.task_id == "bug_triage_medium":
            subscores, mistakes = self._grade_medium(episode_actions, ground_truths, metrics)
        elif self.task_id == "bug_triage_hard":
            subscores, mistakes = self._grade_hard(episode_actions, ground_truths, metrics)
        
        # Calculate weighted final score
        final_score = sum(
            subscores.get(key, 0.0) * weight
            for key, weight in self.weights.items()
        )
        
        # Clamp to [0, 1]
        final_score = max(0.0, min(1.0, final_score))
        
        passed = final_score >= self.threshold
        
        return GraderResult(
            score=final_score,
            subscores=subscores,
            mistakes=mistakes,
            passed=passed,
        )
    
    def _grade_easy(
        self,
        episode_actions: list[dict],
        ground_truths: list[dict],
        metrics: dict,
    ) -> tuple[dict[str, float], list[str]]:
        """Grade easy task episode."""
        subscores = {}
        mistakes = []
        
        # Count correct classifications
        severity_correct = metrics.get("severity_correct", 0)
        priority_correct = metrics.get("priority_correct", 0)
        component_correct = metrics.get("component_correct", 0)
        team_correct = metrics.get("team_correct", 0)
        duplicate_correct = metrics.get("duplicate_correct", 0)
        
        total_tickets = len(ground_truths)
        
        if total_tickets > 0:
            subscores["severity_accuracy"] = severity_correct / total_tickets
            subscores["priority_accuracy"] = priority_correct / total_tickets
            subscores["component_accuracy"] = component_correct / total_tickets
            subscores["team_accuracy"] = team_correct / total_tickets
            subscores["duplicate_handling"] = duplicate_correct / max(1, metrics.get("duplicate_total", 1))
        
        # Efficiency score
        steps_used = metrics.get("steps_used", 0)
        optimal_steps = total_tickets * 2  # Classify + assign per ticket
        subscores["efficiency"] = max(0.0, 1.0 - (steps_used - optimal_steps) / optimal_steps) if optimal_steps > 0 else 0.0
        
        # Track major mistakes
        major_mistakes = metrics.get("major_mistakes", 0)
        if major_mistakes > 1:
            mistakes.append(f"Too many major mistakes: {major_mistakes}")
        
        return subscores, mistakes
    
    def _grade_medium(
        self,
        episode_actions: list[dict],
        ground_truths: list[dict],
        metrics: dict,
    ) -> tuple[dict[str, float], list[str]]:
        """Grade medium task episode."""
        subscores = {}
        mistakes = []
        
        severity_correct = metrics.get("severity_correct", 0)
        priority_correct = metrics.get("priority_correct", 0)
        component_correct = metrics.get("component_correct", 0)
        team_correct = metrics.get("team_correct", 0)
        duplicate_correct = metrics.get("duplicate_correct", 0)
        info_request_correct = metrics.get("info_request_correct", 0)
        
        total_tickets = len(ground_truths)
        
        if total_tickets > 0:
            subscores["severity_accuracy"] = severity_correct / total_tickets
            subscores["priority_accuracy"] = priority_correct / total_tickets
            subscores["component_accuracy"] = component_correct / total_tickets
            subscores["team_accuracy"] = team_correct / total_tickets
        
        # Duplicate F1-like score
        duplicate_total = metrics.get("duplicate_total", 0)
        if duplicate_total > 0:
            subscores["duplicate_handling"] = duplicate_correct / duplicate_total
        else:
            subscores["duplicate_handling"] = 1.0
        
        # Info request accuracy
        info_needed_total = metrics.get("info_needed_total", 0)
        if info_needed_total > 0:
            subscores["info_request_accuracy"] = info_request_correct / info_needed_total
        else:
            subscores["info_request_accuracy"] = 1.0
        
        # Efficiency
        steps_used = metrics.get("steps_used", 0)
        step_budget = metrics.get("step_budget", 100)
        subscores["efficiency"] = 1.0 - (steps_used / step_budget) if step_budget > 0 else 0.0
        
        # Check for destructive actions
        if metrics.get("incorrect_close_count", 0) > 0:
            mistakes.append(f"Incorrect close actions: {metrics.get('incorrect_close_count', 0)}")
        
        return subscores, mistakes
    
    def _grade_hard(
        self,
        episode_actions: list[dict],
        ground_truths: list[dict],
        metrics: dict,
    ) -> tuple[dict[str, float], list[str]]:
        """Grade hard task episode."""
        subscores = {}
        mistakes = []
        
        # Critical severity accuracy (sev0/sev1)
        critical_severity_correct = metrics.get("critical_severity_correct", 0)
        critical_severity_total = metrics.get("critical_severity_total", 1)
        subscores["critical_severity_accuracy"] = critical_severity_correct / critical_severity_total
        
        # Priority accuracy
        priority_correct = metrics.get("priority_correct", 0)
        total_tickets = len(ground_truths)
        subscores["priority_accuracy"] = priority_correct / total_tickets if total_tickets > 0 else 0.0
        
        # Component and team
        component_correct = metrics.get("component_correct", 0)
        team_correct = metrics.get("team_correct", 0)
        subscores["component_accuracy"] = component_correct / total_tickets if total_tickets > 0 else 0.0
        subscores["team_accuracy"] = team_correct / total_tickets if total_tickets > 0 else 0.0
        
        # SLA handling
        sla_met = metrics.get("sla_met", 0)
        sla_total = metrics.get("sla_total", 1)
        subscores["sla_handling"] = sla_met / sla_total
        
        # Escalation accuracy
        escalation_correct = metrics.get("escalation_correct", 0)
        escalation_total = metrics.get("escalation_total", 1)
        subscores["escalation_accuracy"] = escalation_correct / escalation_total
        
        # Policy quality (avoid destructive shortcuts)
        destructive_actions = metrics.get("destructive_actions", 0)
        subscores["policy_quality"] = max(0.0, 1.0 - (destructive_actions / total_tickets)) if total_tickets > 0 else 1.0
        
        # Track critical mistakes
        if metrics.get("missed_critical_escalation", 0) > 0:
            mistakes.append(f"Missed critical escalations: {metrics.get('missed_critical_escalation', 0)}")
        
        if subscores["critical_severity_accuracy"] < 0.8:
            mistakes.append("Critical severity accuracy below 80%")
        
        return subscores, mistakes
