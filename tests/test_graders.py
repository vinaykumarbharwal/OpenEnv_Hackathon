"""Test grader logic."""
import pytest
from openenv_bug_triage.grader import BugTriageGrader


def test_grader_initialization():
    """Test grader initialization."""
    grader = BugTriageGrader(task_id="bug_triage_easy")
    assert grader.task_id == "bug_triage_easy"
    assert grader.threshold == 0.75


def test_grader_weights():
    """Test that grader has correct weights."""
    grader_easy = BugTriageGrader(task_id="bug_triage_easy")
    grader_medium = BugTriageGrader(task_id="bug_triage_medium")
    grader_hard = BugTriageGrader(task_id="bug_triage_hard")
    
    assert "severity_accuracy" in grader_easy.weights
    assert "duplicate_handling" in grader_medium.weights
    assert "critical_severity_accuracy" in grader_hard.weights


def test_final_score_strictly_between_zero_and_one():
    """Final task scores must avoid exact 0.0/1.0 boundaries."""
    grader = BugTriageGrader(task_id="bug_triage_easy")
    ground_truths = [{"duplicate_of": None}]

    perfect_metrics = {
        "label_total": 1,
        "assignment_total": 1,
        "duplicate_expected_total": 0,
        "severity_correct": 1,
        "priority_correct": 1,
        "component_correct": 1,
        "team_correct": 1,
        "duplicate_correct": 0,
        "steps_used": 1,
        "major_mistakes": 0,
    }
    worst_metrics = {
        "label_total": 1,
        "assignment_total": 1,
        "duplicate_expected_total": 1,
        "severity_correct": 0,
        "priority_correct": 0,
        "component_correct": 0,
        "team_correct": 0,
        "duplicate_correct": 0,
        "steps_used": 999,
        "major_mistakes": 2,
    }

    perfect = grader.grade_episode([], ground_truths, perfect_metrics)
    worst = grader.grade_episode([], ground_truths, worst_metrics)

    assert 0.0 < perfect.score < 1.0
    assert 0.0 < worst.score < 1.0
