"""Shared deterministic triage policy used by the API and offline runner."""

from __future__ import annotations

from models import ActionModel
from server.heuristics import (
    COMPONENT_TEAM_MAP,
    infer_component,
    infer_priority,
    infer_severity,
    needs_more_info,
    suggested_info_type,
)


def recommend_action(observation, action_history: list[str] | None = None) -> tuple[ActionModel, str]:
    """Return the next deterministic action for the current ticket."""
    ticket = observation.current_ticket
    history = set(action_history or [])

    if ticket is None:
        return (
            ActionModel(action_type="next_ticket", next_ticket={}),
            "No active ticket is loaded, so moving to the next ticket is safest.",
        )

    duplicate_id = (ticket.suspected_duplicate_ids or [None])[0]
    component = infer_component(ticket, observation.available_components)
    severity = infer_severity(ticket, component)
    priority = infer_priority(ticket, severity)

    if duplicate_id:
        if "mark_duplicate" not in history:
            return (
                ActionModel(
                    action_type="mark_duplicate",
                    mark_duplicate={"canonical_ticket_id": str(duplicate_id)},
                ),
                f"Duplicate hints point to {duplicate_id}, so linking it should happen first.",
            )
        return (
            ActionModel(action_type="next_ticket", next_ticket={}),
            "This ticket is already linked as a duplicate, so continuing would only waste steps.",
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
            "Classification is still missing, so severity, priority, and component come first.",
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
            "This looks like a critical ticket, so escalation should happen before moving on.",
        )

    if needs_more_info(ticket) and "request_info" not in history:
        info_type = suggested_info_type(ticket)
        return (
            ActionModel(
                action_type="request_info",
                request_info={"info_type": info_type},
            ),
            "The report is missing enough evidence that requesting more information is justified.",
        )

    return (
        ActionModel(action_type="next_ticket", next_ticket={}),
        "The important triage steps for this ticket are already covered, so moving on is reasonable.",
    )

