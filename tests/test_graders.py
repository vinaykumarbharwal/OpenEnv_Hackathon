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
