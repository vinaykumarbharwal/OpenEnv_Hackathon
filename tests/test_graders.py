"""
Tests for the BugTriageGrader (server/graders/__init__.py, grader_*.py).

Verifies that each difficulty's grader produces expected scores given
known metric inputs and that the GraderResult model is valid.
"""

from __future__ import annotations

import pytest
from server.graders import BugTriageGrader, GraderResult

# Representative metrics that correspond to a perfect easy-task run:
_PERFECT_EASY_METRICS = {
    "severity_correct": 7,
    "priority_correct": 7,
    "component_correct": 7,
    "team_correct": 7,
    "duplicate_correct": 1,
    "duplicate_total": 1,
    "duplicate_expected_total": 1,
    "info_request_correct": 1,
    "info_needed_total": 1,
    "major_mistakes": 0,
    "incorrect_close_count": 0,
    "critical_severity_correct": 2,
    "critical_severity_total": 2,
    "sla_met": 2,
    "sla_total": 2,
    "escalation_correct": 2,
    "escalation_total": 2,
    "destructive_actions": 0,
    "missed_critical_escalation": 0,
    "steps_used": 21,
    "step_budget": 50,
    "label_total": 7,
    "assignment_total": 7,
}

_ZERO_METRICS: dict = {k: 0 for k in _PERFECT_EASY_METRICS}
_ZERO_METRICS["step_budget"] = 50
_ZERO_METRICS["label_total"] = 7
_ZERO_METRICS["assignment_total"] = 7
_ZERO_METRICS["duplicate_expected_total"] = 1
_ZERO_METRICS["info_needed_total"] = 1
_ZERO_METRICS["critical_severity_total"] = 2
_ZERO_METRICS["sla_total"] = 2
_ZERO_METRICS["escalation_total"] = 2


class TestBugTriageGraderEasy:
    def test_unknown_task_raises(self):
        with pytest.raises(ValueError):
            BugTriageGrader(task_id="nonexistent")

    def test_returns_grader_result(self):
        grader = BugTriageGrader(task_id="bug_triage_easy")
        result = grader.grade_episode([], [], _PERFECT_EASY_METRICS)
        assert isinstance(result, GraderResult)

    def test_perfect_metrics_score_close_to_one(self):
        grader = BugTriageGrader(task_id="bug_triage_easy")
        result = grader.grade_episode([], [], _PERFECT_EASY_METRICS)
        assert result.score > 0.9

    def test_zero_metrics_score_below_threshold(self):
        grader = BugTriageGrader(task_id="bug_triage_easy")
        result = grader.grade_episode([], [], _ZERO_METRICS)
        assert result.score < 0.75
        assert result.passed is False

    def test_score_strictly_in_open_interval(self):
        grader = BugTriageGrader(task_id="bug_triage_easy")
        result = grader.grade_episode([], [], _PERFECT_EASY_METRICS)
        assert 0.0 < result.score < 1.0

    def test_passed_false_when_score_below_threshold(self):
        grader = BugTriageGrader(task_id="bug_triage_easy", threshold=0.99)
        result = grader.grade_episode([], [], _ZERO_METRICS)
        assert result.passed is False


class TestBugTriageGraderMedium:
    def test_grade_medium_runs(self):
        grader = BugTriageGrader(task_id="bug_triage_medium")
        metrics = dict(_PERFECT_EASY_METRICS)
        result = grader.grade_episode([], [], metrics)
        assert isinstance(result, GraderResult)
        assert 0.0 < result.score < 1.0


class TestBugTriageGraderHard:
    def test_grade_hard_runs(self):
        grader = BugTriageGrader(task_id="bug_triage_hard")
        metrics = dict(_PERFECT_EASY_METRICS)
        result = grader.grade_episode([], [], metrics)
        assert isinstance(result, GraderResult)
        assert 0.0 < result.score < 1.0

    def test_zero_critical_accuracy_generates_mistake(self):
        grader = BugTriageGrader(task_id="bug_triage_hard")
        metrics = dict(_ZERO_METRICS)
        metrics["critical_severity_total"] = 4
        result = grader.grade_episode([], [], metrics)
        assert any("Critical severity" in m for m in result.mistakes)
