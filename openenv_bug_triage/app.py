"""FastAPI app wrapper for running Bug Triage OpenEnv in containerized environments."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .env import BugTriageEnv
from .models import ActionModel
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


class ResetRequest(BaseModel):
    task_id: Optional[str] = None
    seed: Optional[int] = None


class StepRequest(BaseModel):
    action: ActionModel


@app.get("/")
def index():
    """Serve the dark-mode frontend."""
    index_file = UI_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
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


@app.get("/reset")
def reset_get(task_id: Optional[str] = None, seed: Optional[int] = None) -> dict:
    """Validator-friendly reset endpoint (GET)."""
    try:
        observation = env.reset(task_id=task_id, seed=seed)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return observation.model_dump(mode="json")


@app.post("/reset")
def reset_post(req: ResetRequest) -> dict:
    """Typed reset endpoint (POST)."""
    try:
        observation = env.reset(task_id=req.task_id, seed=req.seed)
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
