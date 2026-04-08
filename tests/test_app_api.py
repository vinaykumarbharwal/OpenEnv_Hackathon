"""Tests for app-specific helper endpoints."""

from fastapi.testclient import TestClient

from openenv_bug_triage.app import app
from openenv_bug_triage.models import ActionModel


client = TestClient(app)


def test_baseline_endpoint_returns_summary():
    response = client.get("/baseline")

    assert response.status_code == 200
    payload = response.json()
    assert "mean_score" in payload
    assert isinstance(payload.get("results"), list)


def test_suggest_action_returns_typed_action_for_active_ticket():
    reset_response = client.post("/reset", json={"task_id": "bug_triage_easy", "seed": 42})
    assert reset_response.status_code == 200

    response = client.get("/suggest_action")
    assert response.status_code == 200

    payload = response.json()
    assert "reason" in payload
    assert isinstance(payload.get("history"), list)

    action = ActionModel(**payload["action"])
    assert action.action_type in {
        "classify",
        "assign",
        "mark_duplicate",
        "request_info",
        "defer",
        "close",
        "escalate_incident",
        "next_ticket",
    }


def test_openenv_reset_post_accepts_empty_body():
    response = client.post("/openenv/reset")

    assert response.status_code == 200
    payload = response.json()
    assert "current_ticket" in payload
    assert "steps_remaining" in payload
