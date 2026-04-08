"""FastAPI app wrapper for running Bug Triage OpenEnv in containerized environments."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import Body, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .env import BugTriageEnv
from .models import ActionModel


app = FastAPI(
    title="Bug Triage OpenEnv",
    version="0.1.0",
    description="Real-world OpenEnv environment for bug triage training",
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


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/reset")
def reset_get(task_id: Optional[str] = None, seed: Optional[int] = None) -> dict:
    """Validator-friendly reset endpoint (GET)."""
    observation = env.reset(task_id=task_id, seed=seed)
    return observation.model_dump(mode="json")


@app.post("/reset")
def reset_post(req: Optional[ResetRequest] = Body(default=None)) -> dict:
    """Typed reset endpoint (POST). Accepts optional body for validator compatibility."""
    task_id = req.task_id if req is not None else None
    seed = req.seed if req is not None else None
    observation = env.reset(task_id=task_id, seed=seed)
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
    try:
        current_state = env.state()
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return current_state.model_dump(mode="json")
