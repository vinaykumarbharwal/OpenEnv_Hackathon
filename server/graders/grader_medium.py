"""Medium-task grader logic."""

from __future__ import annotations

from typing import Callable


def grade_medium(
    ground_truths: list[dict],
    metrics: dict,
    safe_ratio: Callable[[float, float, float], float],
) -> tuple[dict[str, float], list[str]]:
    """Grade medium task episode."""
    subscores: dict[str, float] = {}
    mistakes: list[str] = []

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

    subscores["severity_accuracy"] = safe_ratio(severity_correct, label_total, 0.0)
    subscores["priority_accuracy"] = safe_ratio(priority_correct, label_total, 0.0)
    subscores["component_accuracy"] = safe_ratio(component_correct, label_total, 0.0)
    subscores["team_accuracy"] = safe_ratio(team_correct, team_total, 0.0)

    if duplicate_expected_total > 0 or duplicate_predicted_total > 0:
        precision = safe_ratio(duplicate_correct, duplicate_predicted_total, 0.0)
        recall = safe_ratio(duplicate_correct, duplicate_expected_total, 0.0)
        if precision + recall > 0:
            subscores["duplicate_handling"] = 2 * precision * recall / (precision + recall)
        else:
            subscores["duplicate_handling"] = 0.0
    else:
        subscores["duplicate_handling"] = 1.0

    if info_needed_total > 0:
        subscores["info_request_accuracy"] = safe_ratio(info_request_correct, info_needed_total, 0.0)
    else:
        subscores["info_request_accuracy"] = 1.0

    steps_used = metrics.get("steps_used", 0)
    step_budget = metrics.get("step_budget", 100)
    subscores["efficiency"] = safe_ratio(max(0, step_budget - steps_used), step_budget, 0.0)

    if metrics.get("incorrect_close_count", 0) > 0:
        mistakes.append(f"Incorrect close actions: {metrics.get('incorrect_close_count', 0)}")

    return subscores, mistakes
