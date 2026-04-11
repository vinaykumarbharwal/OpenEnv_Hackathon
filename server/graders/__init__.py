
"""Deterministic graders for bug triage tasks."""

from __future__ import annotations

from pydantic import BaseModel

from .grader_easy import grade_easy
from .grader_hard import grade_hard
from .grader_medium import grade_medium


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
        if task_id == "bug_triage_medium":
            return {
                "severity_accuracy": 0.20,
                "priority_accuracy": 0.15,
                "component_accuracy": 0.20,
                "team_accuracy": 0.15,
                "duplicate_handling": 0.15,
                "info_request_accuracy": 0.10,
                "efficiency": 0.05,
            }
        if task_id == "bug_triage_hard":
            return {
                "critical_severity_accuracy": 0.30,
                "priority_accuracy": 0.15,
                "component_accuracy": 0.15,
                "team_accuracy": 0.10,
                "sla_handling": 0.15,
                "escalation_accuracy": 0.10,
                "policy_quality": 0.05,
            }
        raise ValueError(f"Unknown task_id: {task_id}")

    def grade_episode(
        self,
        episode_actions: list[dict],
        ground_truths: list[dict],
        metrics: dict,
    ) -> GraderResult:
        """Grade a complete episode."""
        if self.task_id == "bug_triage_easy":
            subscores, mistakes = grade_easy(
                ground_truths=ground_truths,
                metrics=metrics,
                safe_ratio=self._safe_ratio,
                efficiency_score=self._efficiency_score,
            )
        elif self.task_id == "bug_triage_medium":
            subscores, mistakes = grade_medium(
                ground_truths=ground_truths,
                metrics=metrics,
                safe_ratio=self._safe_ratio,
            )
        elif self.task_id == "bug_triage_hard":
            subscores, mistakes = grade_hard(
                ground_truths=ground_truths,
                metrics=metrics,
                safe_ratio=self._safe_ratio,
                clamp01=self._clamp01,
            )
        else:
            raise ValueError(f"Unknown task_id: {self.task_id}")

        final_score = sum(subscores.get(key, 0.0) * weight for key, weight in self.weights.items())
        final_score = self._strict_unit_interval(final_score)
        passed = final_score >= self.threshold
        return GraderResult(
            score=final_score,
            subscores=subscores,
            mistakes=mistakes,
            passed=passed,
        )


__all__ = [
    "BugTriageGrader",
    "GraderResult",
]
