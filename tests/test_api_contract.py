from __future__ import annotations

from fastapi.testclient import TestClient

from server.app import app


client = TestClient(app)


def test_health_contract() -> None:
    response = client.get("/health")
    assert response.status_code == 200

    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["environment"] == "bug-triage-openenv"


def test_baseline_contract() -> None:
    response = client.get("/baseline")
    assert response.status_code == 200

    payload = response.json()
    assert payload["offline_mode"] is True
    assert "mean_score" in payload
    assert "results" in payload
    assert len(payload["results"]) == 3


def test_reset_step_and_state_contract() -> None:
    reset_response = client.post("/reset", json={"task_id": "bug_triage_easy", "seed": 42})
    assert reset_response.status_code == 200
    observation = reset_response.json()

    assert "current_ticket" in observation
    assert "queue_stats" in observation
    assert "steps_used" in observation
    assert "steps_remaining" in observation

    step_response = client.post(
        "/step",
        json={"action": {"action_type": "next_ticket", "next_ticket": {}}},
    )
    assert step_response.status_code == 200
    step_payload = step_response.json()

    assert set(step_payload.keys()) == {"observation", "reward", "done", "info"}
    assert isinstance(step_payload["done"], bool)

    state_response = client.get("/state")
    assert state_response.status_code == 200
    state_payload = state_response.json()

    assert "initialized" in state_payload
    assert "steps_used" in state_payload
    assert "current_task_id" in state_payload


def test_state_before_reset_contract() -> None:
    # Ensure endpoint always returns a stable shape even before init in fresh process.
    response = client.get("/state")
    assert response.status_code == 200
    payload = response.json()

    assert "initialized" in payload
    assert "episode_done" in payload
