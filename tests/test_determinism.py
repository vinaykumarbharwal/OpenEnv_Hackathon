"""Test determinism and reproducibility."""
import pytest
from openenv_bug_triage import BugTriageEnv


def test_deterministic_reset():
    """Test that reset with same seed produces same initial state."""
    env1 = BugTriageEnv()
    env2 = BugTriageEnv()
    
    obs1 = env1.reset(task_id="bug_triage_easy", seed=42)
    obs2 = env2.reset(task_id="bug_triage_easy", seed=42)
    
    assert obs1.current_ticket.ticket_id == obs2.current_ticket.ticket_id


def test_different_seeds():
    """Test that different seeds may produce different orderings."""
    env1 = BugTriageEnv()
    env2 = BugTriageEnv()
    
    obs1 = env1.reset(task_id="bug_triage_easy", seed=42)
    obs2 = env2.reset(task_id="bug_triage_easy", seed=999)
    
    # Both should return valid observations
    assert obs1.current_ticket is not None
    assert obs2.current_ticket is not None
