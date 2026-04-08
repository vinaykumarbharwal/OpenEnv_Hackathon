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
    SCORE_EPSILON = 1e-6
    
    def __init__(self, task_id: str, threshold: float = 0.75):
        self.task_id = task_id
        self.threshold = threshold
        self.weights = self._get_task_weights(task_id)

    @staticmethod
    def _clamp01(value: float) -> float:
        return max(0.0, min(1.0, value))

    def _strict_unit_interval(self, value: float) -> float:
        """Clamp to a strict open interval (0, 1) for validator compatibility."""
        clamped = self._clamp01(value)
        return max(self.SCORE_EPSILON, min(1.0 - self.SCORE_EPSILON, clamped))

    def _safe_ratio(self, numerator: float, denominator: float, default: float = 1.0) -> float:
        if denominator <= 0:
            return default
        return self._clamp01(numerator / denominator)

    def _efficiency_score(self, steps_used: int, optimal_steps: int) -> float:
        if steps_used <= 0 or optimal_steps <= 0:
            return 0.0
        if steps_used <= optimal_steps:
            return 1.0
        return self._clamp01(1.0 - ((steps_used - optimal_steps) / optimal_steps))
    
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
        
        # Keep final task score strictly in (0, 1) for submission validators.
        final_score = self._strict_unit_interval(final_score)
        
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
        
        label_total = metrics.get(
            "label_total",
            sum(1 for gt in ground_truths if gt.get("duplicate_of") is None),
        )
        team_total = metrics.get("assignment_total", label_total)
        duplicate_expected_total = metrics.get(
            "duplicate_expected_total",
            sum(1 for gt in ground_truths if gt.get("duplicate_of") is not None),
        )
        
        subscores["severity_accuracy"] = self._safe_ratio(severity_correct, label_total, default=0.0)
        subscores["priority_accuracy"] = self._safe_ratio(priority_correct, label_total, default=0.0)
        subscores["component_accuracy"] = self._safe_ratio(component_correct, label_total, default=0.0)
        subscores["team_accuracy"] = self._safe_ratio(team_correct, team_total, default=0.0)
        subscores["duplicate_handling"] = self._safe_ratio(
            duplicate_correct,
            duplicate_expected_total,
            default=1.0,
        )
        
        # Efficiency score
        steps_used = metrics.get("steps_used", 0)
        optimal_steps = (label_total * 3) + (duplicate_expected_total * 4)
        subscores["efficiency"] = self._efficiency_score(steps_used, optimal_steps)
        
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
        
        label_total = metrics.get(
            "label_total",
            sum(1 for gt in ground_truths if gt.get("duplicate_of") is None),
        )
        team_total = metrics.get("assignment_total", label_total)
        duplicate_expected_total = metrics.get(
            "duplicate_expected_total",
            sum(1 for gt in ground_truths if gt.get("duplicate_of") is not None),
        )
        duplicate_predicted_total = metrics.get("duplicate_total", 0)
        info_needed_total = metrics.get(
            "info_needed_total",
            sum(1 for gt in ground_truths if gt.get("needs_more_info")),
        )
        
        subscores["severity_accuracy"] = self._safe_ratio(severity_correct, label_total, default=0.0)
        subscores["priority_accuracy"] = self._safe_ratio(priority_correct, label_total, default=0.0)
        subscores["component_accuracy"] = self._safe_ratio(component_correct, label_total, default=0.0)
        subscores["team_accuracy"] = self._safe_ratio(team_correct, team_total, default=0.0)
        
        # Duplicate F1-like score
        if duplicate_expected_total > 0 or duplicate_predicted_total > 0:
            precision = self._safe_ratio(duplicate_correct, duplicate_predicted_total, default=0.0)
            recall = self._safe_ratio(duplicate_correct, duplicate_expected_total, default=0.0)
            if precision + recall > 0:
                subscores["duplicate_handling"] = 2 * precision * recall / (precision + recall)
            else:
                subscores["duplicate_handling"] = 0.0
        else:
            subscores["duplicate_handling"] = 1.0
        
        # Info request accuracy
        if info_needed_total > 0:
            subscores["info_request_accuracy"] = self._safe_ratio(info_request_correct, info_needed_total, default=0.0)
        else:
            subscores["info_request_accuracy"] = 1.0
        
        # Efficiency
        steps_used = metrics.get("steps_used", 0)
        step_budget = metrics.get("step_budget", 100)
        subscores["efficiency"] = self._safe_ratio(max(0, step_budget - steps_used), step_budget, default=0.0)
        
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
        critical_severity_total = metrics.get(
            "critical_severity_total",
            sum(1 for gt in ground_truths if gt.get("true_severity") in {"sev0", "sev1"}),
        )
        subscores["critical_severity_accuracy"] = self._safe_ratio(
            critical_severity_correct,
            critical_severity_total,
            default=1.0,
        )

        # Priority accuracy
        priority_correct = metrics.get("priority_correct", 0)
        label_total = metrics.get(
            "label_total",
            sum(1 for gt in ground_truths if gt.get("duplicate_of") is None),
        )
        team_total = metrics.get("assignment_total", label_total)
        subscores["priority_accuracy"] = self._safe_ratio(priority_correct, label_total, default=0.0)

        # Component and team
        component_correct = metrics.get("component_correct", 0)
        team_correct = metrics.get("team_correct", 0)
        subscores["component_accuracy"] = self._safe_ratio(component_correct, label_total, default=0.0)
        subscores["team_accuracy"] = self._safe_ratio(team_correct, team_total, default=0.0)

        # SLA handling
        sla_met = metrics.get("sla_met", 0)
        sla_total = metrics.get("sla_total", critical_severity_total)
        subscores["sla_handling"] = self._safe_ratio(sla_met, sla_total, default=1.0)

        # Escalation accuracy
        escalation_correct = metrics.get("escalation_correct", 0)
        escalation_total = metrics.get("escalation_total", critical_severity_total)
        subscores["escalation_accuracy"] = self._safe_ratio(
            escalation_correct,
            escalation_total,
            default=1.0,
        )

        # Policy quality (avoid destructive shortcuts)
        destructive_actions = metrics.get("destructive_actions", 0)
        subscores["policy_quality"] = self._clamp01(
            1.0 - self._safe_ratio(destructive_actions, label_total, default=0.0)
        ) if label_total > 0 else 1.0
        
        # Track critical mistakes
        if metrics.get("missed_critical_escalation", 0) > 0:
            mistakes.append(f"Missed critical escalations: {metrics.get('missed_critical_escalation', 0)}")
        
        if subscores["critical_severity_accuracy"] < 0.8:
            mistakes.append("Critical severity accuracy below 80%")
        
        return subscores, mistakes
