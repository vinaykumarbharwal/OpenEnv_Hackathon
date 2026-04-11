"""FastAPI app wrapper for running Bug Triage OpenEnv in containerized environments."""

from __future__ import annotations

import os
import threading
from functools import lru_cache
from pathlib import Path
from typing import Optional

import uvicorn
from fastapi import Body, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from models import ActionModel
from server.environment import BugTriageEnv
from server.graders import BugTriageGrader
from server.policy import recommend_action
from server.tasks import list_tasks


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

# ---------------------------------------------------------------------------
# Global singleton environment
# NOTE: This server is designed for single-user / validator use.  The
# environment is shared across all HTTP requests and protected by ENV_LOCK.
# Running multiple concurrent sessions will interleave state; deploy separate
# server instances if multi-tenancy is required.
# ---------------------------------------------------------------------------
env = BugTriageEnv()
ENV_LOCK = threading.RLock()
STATIC_DIR = Path(__file__).resolve().parents[1] / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


def _as_bool(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


@lru_cache(maxsize=1)
def _offline_baseline_snapshot(seed: int = 42) -> dict:
    """Run the built-in offline policy against every task and cache the snapshot."""
    task_ids = list(list_tasks().keys())
    results: list[dict[str, object]] = []
    total_score = 0.0

    for task_id in task_ids:
        runner = BugTriageEnv()
        observation = runner.reset(task_id=task_id, seed=seed)
        done = False
        info: dict = {"metrics": {}}

        while not done:
            history: list[str] = []
            if runner.current_task is not None and runner.current_ticket_index < len(runner.ticket_states):
                history = list(runner.ticket_states[runner.current_ticket_index]["actions_taken"])

            action, _ = suggest_action(observation=observation, action_history=history)
            observation, _, done, info = runner.step(action)

        grader = BugTriageGrader(task_id=task_id)
        grader_result = grader.grade_episode(
            episode_actions=[],
            ground_truths=[gt.model_dump(mode="json") for gt in runner.current_task.ground_truths],
            metrics=info.get("metrics", {}),
        )
        total_score += grader_result.score
        results.append(
            {
                "task_id": task_id,
                "score": round(grader_result.score, 4),
                "passed": grader_result.passed,
            }
        )

    mean_score = total_score / len(results) if results else 0.0
    return {
        "model": "offline-heuristic",
        "offline_mode": True,
        "seed": seed,
        "mean_score": round(mean_score, 4),
        "results": results,
    }


def suggest_action(observation, action_history: list[str] | None = None) -> tuple[ActionModel, str]:
    """Return a deterministic next-step suggestion for the active ticket."""
    return recommend_action(observation=observation, action_history=action_history)


class ResetRequest(BaseModel):
    task_id: Optional[str] = None
    seed: Optional[int] = None


class StepRequest(BaseModel):
    action: ActionModel


def _app_base_path(request: Request) -> str:
    """Return proxy-aware base path without a trailing slash."""
    root_path = (request.scope.get("root_path") or "").rstrip("/")
    return root_path


@app.get("/")
def index(request: Request):
    """Serve the frontend with proxy-aware asset URLs."""
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        html = index_file.read_text(encoding="utf-8")
        html = html.replace("__APP_BASE__", _app_base_path(request))
        return HTMLResponse(content=html)

    root_path = _app_base_path(request)
    docs_path = f"{root_path}/docs" if root_path else "/docs"
    return {"message": "Bug Triage OpenEnv API", "docs": docs_path}


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> Response:
    """Serve favicon for browser clients."""
    icon_file = STATIC_DIR / "favicon.svg"
    if icon_file.exists():
        return FileResponse(icon_file, media_type="image/svg+xml")
    return Response(status_code=204)


@app.get("/health")
@app.get("/openenv/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "environment": "bug-triage-openenv",
        "version": app.version,
    }


@app.get("/tasks")
@app.get("/openenv/tasks")
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
    return _offline_baseline_snapshot()


@app.get("/suggest_action")
def suggest_current_action() -> dict:
    with ENV_LOCK:
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
@app.get("/openenv/reset")
def reset_get(task_id: Optional[str] = None, seed: Optional[int] = None) -> dict:
    """Validator-friendly reset endpoint (GET)."""
    try:
        with ENV_LOCK:
            observation = env.reset(task_id=task_id, seed=seed)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return observation.model_dump(mode="json")


@app.post("/reset")
@app.post("/openenv/reset")
def reset_post(req: Optional[ResetRequest] = Body(default=None)) -> dict:
    """Typed reset endpoint (POST), compatible with empty-body validator calls."""
    task_id = req.task_id if req is not None else None
    seed = req.seed if req is not None else None
    try:
        with ENV_LOCK:
            observation = env.reset(task_id=task_id, seed=seed)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return observation.model_dump(mode="json")


@app.post("/step")
@app.post("/openenv/step")
def step(req: StepRequest) -> dict:
    try:
        with ENV_LOCK:
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
@app.get("/openenv/state")
def state() -> dict:
    with ENV_LOCK:
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


def main() -> None:
    """Run the API server with optional env-driven overrides."""
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "7860"))
    reload_enabled = _as_bool(os.getenv("RELOAD", "false"))

    uvicorn.run(
        "server.app:app",
        host=host,
        port=port,
        reload=reload_enabled,
    )


if __name__ == "__main__":
    main()
