"""Deterministic helper policy for demos and UI suggestions."""

from __future__ import annotations

from .models import ActionModel


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
