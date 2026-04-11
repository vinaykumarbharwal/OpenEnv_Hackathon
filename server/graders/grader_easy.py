"""Easy-task grader logic."""

from __future__ import annotations

from typing import Callable


def grade_easy(
    ground_truths: list[dict],
    metrics: dict,
    safe_ratio: Callable[[float, float, float], float],
    efficiency_score: Callable[[int, int], float],
) -> tuple[dict[str, float], list[str]]:
    """Grade easy task episode."""
    subscores: dict[str, float] = {}
    mistakes: list[str] = []

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

    subscores["severity_accuracy"] = safe_ratio(severity_correct, label_total, 0.0)
    subscores["priority_accuracy"] = safe_ratio(priority_correct, label_total, 0.0)
    subscores["component_accuracy"] = safe_ratio(component_correct, label_total, 0.0)
    subscores["team_accuracy"] = safe_ratio(team_correct, team_total, 0.0)
    subscores["duplicate_handling"] = safe_ratio(
        duplicate_correct,
        duplicate_expected_total,
        1.0,
    )

    steps_used = metrics.get("steps_used", 0)
    optimal_steps = (label_total * 3) + (duplicate_expected_total * 4)
    subscores["efficiency"] = efficiency_score(steps_used, optimal_steps)

    major_mistakes = metrics.get("major_mistakes", 0)
    if major_mistakes > 1:
        mistakes.append(f"Too many major mistakes: {major_mistakes}")

    return subscores, mistakes
