"""FastAPI app wrapper for running Bug Triage OpenEnv in containerized environments."""

from __future__ import annotations

import os
import threading
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

env = BugTriageEnv()
ENV_LOCK = threading.RLock()
STATIC_DIR = Path(__file__).resolve().parents[1] / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

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

COMPONENT_TEAM_MAP = {
    "api-gateway": "backend-api",
    "auth-service": "backend-api",
    "user-service": "backend-api",
    "payment-service": "backend-api",
    "web-app": "frontend-web",
    "ios-app": "mobile-ios",
    "android-app": "mobile-android",
    "database": "data-platform",
    "cache": "infrastructure",
    "cdn": "infrastructure",
}

COMPONENT_KEYWORDS = {
    "api-gateway": ("api gateway", "gateway", "edge", "proxy", "routing", "/api/"),
    "auth-service": ("auth", "authentication", "login", "signin", "token", "session"),
    "user-service": ("user service", "users endpoint", "profile", "identity", "account"),
    "payment-service": ("payment", "checkout", "charge", "billing", "tax", "order"),
    "web-app": ("web app", "web-app", "browser", "dashboard", "frontend", "page"),
    "ios-app": ("ios", "iphone", "ipad", "apple"),
    "android-app": ("android",),
    "database": ("database", "query", "sql", "db", "index"),
    "cache": ("cache", "redis", "memcache"),
    "cdn": ("cdn", "image", "asset", "static content"),
}

SERVICE_COMPONENT_HINTS = {
    "api": ("api-gateway", "user-service"),
    "auth": ("auth-service",),
    "identity": ("user-service",),
    "payments": ("payment-service",),
    "web-app": ("web-app", "cdn", "database", "cache"),
    "mobile-app": ("ios-app", "android-app", "auth-service"),
}


def severity_to_priority(severity: str) -> str:
    return {
        "sev0": "p0",
        "sev1": "p1",
        "sev2": "p2",
        "sev3": "p3",
    }.get(severity, "p2")


def ticket_text(ticket) -> str:
    return " ".join(
        str(part)
        for part in (
            ticket.title,
            ticket.description,
            ticket.service,
            " ".join(ticket.component_candidates),
        )
    ).lower()


def infer_component(ticket, available_components: list[str]) -> str:
    candidates = [c for c in ticket.component_candidates if c in available_components]
    if not candidates:
        return available_components[0] if available_components else "api-gateway"

    text = ticket_text(ticket)
    service_hints = SERVICE_COMPONENT_HINTS.get(ticket.service, ())
    best_candidate = candidates[0]
    best_score = -1

    for index, candidate in enumerate(candidates):
        score = 0
        score += max(0, 3 - index)

        if candidate in service_hints:
            score += 3

        normalized = candidate.replace("-", " ")
        if normalized in text:
            score += 4

        for keyword in COMPONENT_KEYWORDS.get(candidate, ()):
            if keyword in text:
                score += 3

        if score > best_score:
            best_score = score
            best_candidate = candidate

    return best_candidate


def infer_severity(ticket, component: str) -> str:
    text = ticket_text(ticket)
    synthetic_high_signal = "signal quality is high" in text
    synthetic_low_signal = "signal quality is low" in text

    if any(k in text for k in ["security", "unauthorized", "double charge", "data loss", "corrupt"]):
        return "sev0"

    if any(k in text for k in ["500 internal server error", "null pointer exception", "multiple monitoring alerts"]):
        if ticket.reporter_type == "monitoring" and ticket.customer_tier == "enterprise":
            return "sev0"

    if synthetic_high_signal and ticket.reporter_type == "monitoring" and ticket.customer_tier == "enterprise":
        return "sev1"

    if any(k in text for k in ["timeout", "timing out", "503", "outage", "down"]):
        return "sev1"

    if synthetic_high_signal and ticket.customer_tier in {"pro", "enterprise"}:
        return "sev1"

    if "incorrect tax" in text or ("tax" in text and "wrong" in text):
        return "sev1" if ticket.customer_tier in {"pro", "enterprise"} else "sev2"

    if synthetic_low_signal:
        return "sev3" if ticket.customer_tier == "free" else "sev2"

    if any(k in text for k in ["crash", "not responding", "not working", "broken image", "wrong values"]):
        return "sev2"

    if any(k in text for k in ["latency", "slow", "degraded", "error", "failed"]):
        if component == "database" and ticket.customer_tier == "free":
            return "sev3"
        return "sev2"

    return "sev3"


def infer_priority(ticket, severity: str) -> str:
    text = ticket_text(ticket)

    if severity == "sev2" and (
        ticket.customer_tier == "enterprise"
        or ticket.reporter_type == "monitoring"
        or any(k in text for k in ["payment", "checkout", "tax", "cdn", "image", "shopping"])
    ):
        return "p1"

    return severity_to_priority(severity)


def needs_more_info(ticket) -> bool:
    text = ticket_text(ticket)

    if ticket.suspected_duplicate_ids:
        return False

    if "signal quality is low" in text:
        return True

    if not ticket.repro_steps_present and not ticket.logs_present:
        return True

    if not ticket.repro_steps_present and ticket.reporter_type != "monitoring":
        return True

    if not ticket.logs_present and ticket.reporter_type in {"user", "qa"}:
        return True

    return False


def suggested_info_type(ticket) -> str:
    if not ticket.repro_steps_present and not ticket.logs_present:
        return "both"
    if not ticket.repro_steps_present:
        return "repro_steps"
    if not ticket.logs_present:
        return "logs"
    return "both"


def suggest_action(observation, action_history: list[str] | None = None) -> tuple[ActionModel, str]:
    """Return a deterministic next-step suggestion for the active ticket."""
    ticket = observation.current_ticket
    history = set(action_history or [])

    if ticket is None:
        return (
            ActionModel(action_type="next_ticket", next_ticket={}),
            "No active ticket is loaded, so the safest action is next_ticket.",
        )

    duplicate_id = (ticket.suspected_duplicate_ids or [None])[0]
    component = infer_component(ticket, observation.available_components)
    severity = infer_severity(ticket, component)
    priority = infer_priority(ticket, severity)

    if duplicate_id and "mark_duplicate" not in history:
        return (
            ActionModel(
                action_type="mark_duplicate",
                mark_duplicate={"canonical_ticket_id": str(duplicate_id)},
            ),
            f"Duplicate hints point to {duplicate_id}, so linking it is the most efficient next step.",
        )

    if "classify" not in history:
        return (
            ActionModel(
                action_type="classify",
                classify={
                    "severity": severity,
                    "priority": priority,
                    "component": component,
                },
            ),
            "Classification is still missing, so the suggestion fills severity, priority, and component first.",
        )

    if "assign" not in history:
        default_team = observation.available_teams[0] if observation.available_teams else "backend-api"
        team = COMPONENT_TEAM_MAP.get(component, default_team)
        return (
            ActionModel(action_type="assign", assign={"team": team}),
            f"The inferred component maps best to {team}, so routing is the next step.",
        )

    if severity in {"sev0", "sev1"} and "escalate_incident" not in history:
        return (
            ActionModel(
                action_type="escalate_incident",
                escalate_incident={"justification": "High-impact production risk detected"},
            ),
            "This looks like a critical ticket, so escalation is recommended before moving on.",
        )

    if needs_more_info(ticket) and "request_info" not in history:
        info_type = suggested_info_type(ticket)
        return (
            ActionModel(
                action_type="request_info",
                request_info={"info_type": info_type},
            ),
            "The ticket is still missing supporting evidence, so requesting more information is recommended.",
        )

    return (
        ActionModel(action_type="next_ticket", next_ticket={}),
        "The key triage steps for this ticket are already covered, so moving to the next ticket is reasonable.",
    )


class ResetRequest(BaseModel):
    task_id: Optional[str] = None
    seed: Optional[int] = None


class StepRequest(BaseModel):
    action: ActionModel


def _app_base_path(request: Request) -> str:
    """Return proxy-aware base path without a trailing slash."""
    root_path = (request.scope.get("root_path") or "").rstrip("/")
    return root_path


def _as_bool(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


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
    return FALLBACK_BASELINE


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
