"""FastAPI app wrapper for running Bug Triage OpenEnv in containerized environments."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from fastapi import Body, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .env import BugTriageEnv
from .models import ActionModel
from .policy import suggest_action
from .tasks import list_tasks


app = FastAPI(
    title="Bug Triage OpenEnv",
    version="0.1.0",
    description="Real-world OpenEnv environment for bug triage training",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

UI_DIR = Path(__file__).parent / "ui"
if UI_DIR.exists():
    app.mount("/ui", StaticFiles(directory=str(UI_DIR)), name="ui")

env = BugTriageEnv()
BASELINE_ARTIFACT = Path(__file__).resolve().parents[1] / "artifacts" / "baseline_scores.json"
FALLBACK_BASELINE = {
    "model": "offline-heuristic",
    "offline_mode": True,
    "mean_score": 0.7698,
    "results": [
        {"task_id": "bug_triage_easy", "score": 0.9920, "passed": True},
        {"task_id": "bug_triage_medium", "score": 0.6715, "passed": False},
        {"task_id": "bug_triage_hard", "score": 0.6460, "passed": False},
    ],
}


class ResetRequest(BaseModel):
    task_id: Optional[str] = None
    seed: Optional[int] = None


class StepRequest(BaseModel):
    action: ActionModel


def _app_base_path(request: Request) -> str:
    """Return proxy-aware base path without a trailing slash."""
    root_path = (request.scope.get("root_path") or "").rstrip("/")
    return root_path


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    """Serve the frontend with proxy-aware asset URLs."""
    index_file = UI_DIR / "index.html"
    if index_file.exists():
        html = index_file.read_text(encoding="utf-8")
        html = html.replace("__APP_BASE__", _app_base_path(request))
        return HTMLResponse(content=html)
    return {"message": "Bug Triage OpenEnv API", "docs": "/docs"}


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> Response:
    """Serve a small favicon so browser startup stays clean."""
    icon_file = UI_DIR / "favicon.svg"
    if icon_file.exists():
        return FileResponse(icon_file, media_type="image/svg+xml")
    return Response(status_code=204)


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "environment": "bug-triage-openenv",
        "version": app.version,
    }


@app.get("/tasks")
def tasks() -> dict:
    registry = list_tasks()
    return {
        "total": len(registry),
        "tasks": [
            {
                "id": task_id,
                "difficulty": meta["difficulty"],
                "description": meta["description"],
            }
            for task_id, meta in registry.items()
        ],
    }


@app.get("/baseline")
def baseline() -> dict:
    if BASELINE_ARTIFACT.exists():
        try:
            return json.loads(BASELINE_ARTIFACT.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
    return FALLBACK_BASELINE


@app.get("/suggest_action")
def suggest_current_action() -> dict:
    observation = env._get_observation()
    history: list[str] = []

    if env.current_task is not None and env.current_ticket_index < len(env.ticket_states):
        history = list(env.ticket_states[env.current_ticket_index]["actions_taken"])

    action, reason = suggest_action(observation=observation, action_history=history)
    return {
        "action": action.model_dump(mode="json", exclude_none=True),
        "reason": reason,
        "history": history,
    }


@app.get("/reset")
def reset_get(task_id: Optional[str] = None, seed: Optional[int] = None) -> dict:
    """Validator-friendly reset endpoint (GET)."""
    try:
        observation = env.reset(task_id=task_id, seed=seed)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return observation.model_dump(mode="json")


@app.post("/reset")
def reset_post(req: Optional[ResetRequest] = Body(default=None)) -> dict:
    """Typed reset endpoint (POST), compatible with empty-body validator calls."""
    task_id = req.task_id if req is not None else None
    seed = req.seed if req is not None else None
    try:
        observation = env.reset(task_id=task_id, seed=seed)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return observation.model_dump(mode="json")


@app.post("/step")
def step(req: StepRequest) -> dict:
    try:
        observation, reward, done, info = env.step(req.action)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "observation": observation.model_dump(mode="json"),
        "reward": reward.model_dump(mode="json"),
        "done": done,
        "info": info,
    }


@app.get("/state")
def state() -> dict:
    if env.current_task is None:
        return {
            "initialized": False,
            "current_task_id": None,
            "current_ticket_index": 0,
            "total_tickets": 0,
            "tickets_state": [],
            "steps_used": 0,
            "steps_remaining": 0,
            "cumulative_reward": 0.0,
            "episode_done": False,
        }

    current_state = env.state()
    payload = current_state.model_dump(mode="json")
    payload["initialized"] = True
    return payload
