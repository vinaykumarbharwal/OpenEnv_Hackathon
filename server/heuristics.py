"""
Deterministic heuristics for bug-triage inference and action suggestion.

This module is the single source of truth for all rule-based logic that
maps ticket attributes to severity, priority, component, and team.  Both
the standalone ``inference.py`` runner and the FastAPI ``server/app.py``
import from here so that fixes only need to be applied in one place.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Lookup tables
# ---------------------------------------------------------------------------

#: Maps a component slug to the engineering team responsible for it.
COMPONENT_TEAM_MAP: dict[str, str] = {
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

#: Free-text keywords that strongly suggest a component when found in a ticket.
COMPONENT_KEYWORDS: dict[str, tuple[str, ...]] = {
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

#: A service name may hint that certain components are likely candidates.
SERVICE_COMPONENT_HINTS: dict[str, tuple[str, ...]] = {
    "api": ("api-gateway", "user-service"),
    "auth": ("auth-service",),
    "identity": ("user-service",),
    "payments": ("payment-service",),
    "web-app": ("web-app", "cdn", "database", "cache"),
    "mobile-app": ("ios-app", "android-app", "auth-service"),
}


# ---------------------------------------------------------------------------
# Helper — build a single lowercase string from a ticket for keyword search
# ---------------------------------------------------------------------------

def ticket_text(ticket) -> str:
    """Return a single lowercase string combining ticket fields for keyword search."""
    return " ".join(
        str(part)
        for part in (
            ticket.title,
            ticket.description,
            ticket.service,
            " ".join(ticket.component_candidates),
        )
    ).lower()


# ---------------------------------------------------------------------------
# Component inference
# ---------------------------------------------------------------------------

def infer_component(ticket, available_components: list[str]) -> str:
    """
    Pick the most likely component for *ticket* from *available_components*.

    Scoring heuristic (higher wins):
    - Position bonus: earlier in ``component_candidates`` ← up to +3
    - Service hint match                                   ← +3
    - Component name appears in ticket text                ← +4
    - Keyword match                                        ← +3 per keyword
    - Ad-hoc tie-breakers for common patterns              ← +1
    """
    candidates = [c for c in ticket.component_candidates if c in available_components]
    if not candidates:
        return available_components[0] if available_components else "api-gateway"

    text = ticket_text(ticket)
    service_hints = SERVICE_COMPONENT_HINTS.get(ticket.service, ())
    best_candidate = candidates[0]
    best_score = -1

    for index, candidate in enumerate(candidates):
        score = max(0, 3 - index)  # position bonus

        if candidate in service_hints:
            score += 3

        normalized = candidate.replace("-", " ")
        if normalized in text:
            score += 4

        for keyword in COMPONENT_KEYWORDS.get(candidate, ()):
            if keyword in text:
                score += 3

        # Ad-hoc tie-breakers
        if candidate == "ios-app" and "login" in text:
            score += 1
        if candidate == "payment-service" and "gateway" in text:
            score += 1
        if candidate == "database" and "slow" in text:
            score += 1

        if score > best_score:
            best_score = score
            best_candidate = candidate

    return best_candidate


# ---------------------------------------------------------------------------
# Severity inference
# ---------------------------------------------------------------------------

def infer_severity(ticket, component: str) -> str:
    """
    Return the inferred severity level (``sev0``–``sev3``) for *ticket*.

    Rules are applied in priority order; the first match wins.
    """
    text = ticket_text(ticket)
    synthetic_high_signal = "signal quality is high" in text
    synthetic_low_signal = "signal quality is low" in text

    # sev0 — data / security / money corruption
    if any(k in text for k in ["security", "unauthorized", "double charge", "data loss", "corrupt"]):
        return "sev0"

    # sev0 — critical monitoring alert on enterprise
    if any(k in text for k in ["500 internal server error", "null pointer exception", "multiple monitoring alerts"]):
        if ticket.reporter_type == "monitoring" and ticket.customer_tier == "enterprise":
            return "sev0"

    # sev1 — high-signal synthetic flag on enterprise monitoring
    if synthetic_high_signal and ticket.reporter_type == "monitoring" and ticket.customer_tier == "enterprise":
        return "sev1"

    # sev1 — service down / timeout / outage
    if any(k in text for k in ["timeout", "timing out", "503", "outage", "down"]):
        return "sev1"

    # sev1 — high-signal on paid tiers
    if synthetic_high_signal and ticket.customer_tier in {"pro", "enterprise"}:
        return "sev1"

    # sev1/sev2 — incorrect tax (tier-dependent)
    if "incorrect tax" in text or ("tax" in text and "wrong" in text):
        return "sev1" if ticket.customer_tier in {"pro", "enterprise"} else "sev2"

    # sev2/sev3 — low-signal synthetic flag
    if synthetic_low_signal:
        return "sev3" if ticket.customer_tier == "free" else "sev2"

    # sev2 — clearly broken functionality
    if any(k in text for k in ["crash", "not responding", "not working", "broken image", "wrong values"]):
        return "sev2"

    # sev2 (or sev3 for free DB slowness) — degraded performance
    if any(k in text for k in ["latency", "slow", "degraded", "error", "failed"]):
        if component == "database" and ticket.customer_tier == "free":
            return "sev3"
        return "sev2"

    return "sev3"


# ---------------------------------------------------------------------------
# Priority inference
# ---------------------------------------------------------------------------

_SEV_TO_PRI: dict[str, str] = {
    "sev0": "p0",
    "sev1": "p1",
    "sev2": "p2",
    "sev3": "p3",
}


def severity_to_priority(severity: str) -> str:
    """Return the default priority matching *severity*."""
    return _SEV_TO_PRI.get(severity, "p2")


def infer_priority(ticket, severity: str) -> str:
    """
    Return the inferred priority for *ticket* given its *severity*.

    Upgrades sev2 → p1 when the ticket is enterprise, monitoring-sourced,
    or touches high-value areas (payments, CDN, images, shopping).
    """
    text = ticket_text(ticket)
    if severity == "sev2" and (
        ticket.customer_tier == "enterprise"
        or ticket.reporter_type == "monitoring"
        or any(k in text for k in ["payment", "checkout", "tax", "cdn", "image", "shopping"])
    ):
        return "p1"
    return severity_to_priority(severity)


# ---------------------------------------------------------------------------
# Info-request heuristics
# ---------------------------------------------------------------------------

def needs_more_info(ticket) -> bool:
    """Return ``True`` if the ticket is missing evidence needed for triage."""
    text = ticket_text(ticket)

    # Duplicates are handled separately; skip info request
    if ticket.suspected_duplicate_ids:
        return False

    if "signal quality is low" in text:
        return True

    if not ticket.repro_steps_present and not ticket.logs_present:
        return True

    # Non-monitoring reporters need repro steps
    if not ticket.repro_steps_present and ticket.reporter_type != "monitoring":
        return True

    # User/QA reporters should supply logs
    if not ticket.logs_present and ticket.reporter_type in {"user", "qa"}:
        return True

    return False


def suggested_info_type(ticket) -> str:
    """Return which type of information to request for *ticket*."""
    if not ticket.repro_steps_present and not ticket.logs_present:
        return "both"
    if not ticket.repro_steps_present:
        return "repro_steps"
    if not ticket.logs_present:
        return "logs"
    return "both"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

__all__ = [
    "COMPONENT_TEAM_MAP",
    "COMPONENT_KEYWORDS",
    "SERVICE_COMPONENT_HINTS",
    "ticket_text",
    "infer_component",
    "infer_severity",
    "infer_priority",
    "severity_to_priority",
    "needs_more_info",
    "suggested_info_type",
]
