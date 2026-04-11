"""Hard-task grader logic."""

from __future__ import annotations

from typing import Callable


def grade_hard(
    ground_truths: list[dict],
    metrics: dict,
    safe_ratio: Callable[[float, float, float], float],
    clamp01: Callable[[float], float],
) -> tuple[dict[str, float], list[str]]:
    """Grade hard task episode."""
    subscores: dict[str, float] = {}
    mistakes: list[str] = []

    critical_severity_correct = metrics.get("critical_severity_correct", 0)
    critical_severity_total = metrics.get(
        "critical_severity_total",
        sum(1 for gt in ground_truths if gt.get("true_severity") in {"sev0", "sev1"}),
    )
    subscores["critical_severity_accuracy"] = safe_ratio(
        critical_severity_correct,
        critical_severity_total,
        1.0,
    )

    priority_correct = metrics.get("priority_correct", 0)
    label_total = metrics.get(
        "label_total",
        sum(1 for gt in ground_truths if gt.get("duplicate_of") is None),
    )
    team_total = metrics.get("assignment_total", label_total)
    subscores["priority_accuracy"] = safe_ratio(priority_correct, label_total, 0.0)

    component_correct = metrics.get("component_correct", 0)
    team_correct = metrics.get("team_correct", 0)
    subscores["component_accuracy"] = safe_ratio(component_correct, label_total, 0.0)
    subscores["team_accuracy"] = safe_ratio(team_correct, team_total, 0.0)

    sla_met = metrics.get("sla_met", 0)
    sla_total = metrics.get("sla_total", critical_severity_total)
    subscores["sla_handling"] = safe_ratio(sla_met, sla_total, 1.0)

    escalation_correct = metrics.get("escalation_correct", 0)
    escalation_total = metrics.get("escalation_total", critical_severity_total)
    subscores["escalation_accuracy"] = safe_ratio(
        escalation_correct,
        escalation_total,
        1.0,
    )

    destructive_actions = metrics.get("destructive_actions", 0)
    subscores["policy_quality"] = (
        clamp01(1.0 - safe_ratio(destructive_actions, label_total, 0.0))
        if label_total > 0
        else 1.0
    )

    if metrics.get("missed_critical_escalation", 0) > 0:
        mistakes.append(f"Missed critical escalations: {metrics.get('missed_critical_escalation', 0)}")

    if subscores["critical_severity_accuracy"] < 0.8:
        mistakes.append("Critical severity accuracy below 80%")

    return subscores, mistakes
