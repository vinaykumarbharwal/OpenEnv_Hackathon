"""
Pydantic models for the Bug Triage OpenEnv environment.
"""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class TicketModel(BaseModel):
    """Represents a bug ticket in the system."""

    ticket_id: str
    title: str
    description: str
    reporter_type: Literal["user", "qa", "monitoring"]
    service: str
    component_candidates: list[str]
    created_at: datetime
    customer_tier: Literal["free", "pro", "enterprise"]
    repro_steps_present: bool
    logs_present: bool
    attachments_count: int
    suspected_duplicate_ids: list[str]


class TicketGroundTruth(BaseModel):
    """Hidden ground truth for a ticket."""

    ticket_id: str
    true_severity: Literal["sev0", "sev1", "sev2", "sev3"]
    true_priority: Literal["p0", "p1", "p2", "p3"]
    true_component: str
    true_assignee_team: str
    duplicate_of: Optional[str] = None
    needs_more_info: bool


class CurrentTicketModel(BaseModel):
    """Current ticket being focused on."""

    ticket_id: str
    title: str
    description: str
    reporter_type: Literal["user", "qa", "monitoring"]
    service: str
    component_candidates: list[str]
    created_at: datetime
    customer_tier: Literal["free", "pro", "enterprise"]
    repro_steps_present: bool
    logs_present: bool
    attachments_count: int
    suspected_duplicate_ids: list[str]


class QueueStatsModel(BaseModel):
    """Statistics about the ticket queue."""

    remaining_count: int
    urgent_count: int
    sla_at_risk_count: int


class ObservationModel(BaseModel):
    """Observation returned by the environment."""

    current_ticket: Optional[CurrentTicketModel] = None
    queue_stats: QueueStatsModel
    last_action_result: Optional[str] = None
    available_teams: list[str]
    available_components: list[str]
    steps_used: int
    steps_remaining: int
    partial_score: Optional[float] = None


class ClassifyAction(BaseModel):
    """Classify ticket with severity, priority, and component."""

    severity: Literal["sev0", "sev1", "sev2", "sev3"]
    priority: Literal["p0", "p1", "p2", "p3"]
    component: str


class AssignAction(BaseModel):
    """Assign ticket to a team."""

    team: str


class MarkDuplicateAction(BaseModel):
    """Mark ticket as duplicate of another."""

    canonical_ticket_id: str


class RequestInfoAction(BaseModel):
    """Request more information from reporter."""

    info_type: Literal["repro_steps", "logs", "both"]


class DeferAction(BaseModel):
    """Defer ticket to backlog."""

    reason: str


class CloseAction(BaseModel):
    """Close ticket with reason."""

    reason: Literal["invalid", "wont_fix", "cannot_reproduce", "resolved"]


class EscalateAction(BaseModel):
    """Escalate ticket as urgent incident."""

    justification: str


class NextTicketAction(BaseModel):
    """Move to next ticket."""

    pass


class ActionModel(BaseModel):
    """Action that can be taken in the environment."""

    action_type: Literal[
        "classify",
        "assign",
        "mark_duplicate",
        "request_info",
        "defer",
        "close",
        "escalate_incident",
        "next_ticket",
    ]
    classify: Optional[ClassifyAction] = None
    assign: Optional[AssignAction] = None
    mark_duplicate: Optional[MarkDuplicateAction] = None
    request_info: Optional[RequestInfoAction] = None
    defer: Optional[DeferAction] = None
    close: Optional[CloseAction] = None
    escalate_incident: Optional[EscalateAction] = None
    next_ticket: Optional[NextTicketAction] = None

    def model_post_init(self, __context):
        """Validate that the action payload matches the action type."""
        action_map = {
            "classify": self.classify,
            "assign": self.assign,
            "mark_duplicate": self.mark_duplicate,
            "request_info": self.request_info,
            "defer": self.defer,
            "close": self.close,
            "escalate_incident": self.escalate_incident,
            "next_ticket": self.next_ticket,
        }

        expected_field = action_map.get(self.action_type)
        if expected_field is None and self.action_type != "next_ticket":
            raise ValueError(f"Missing payload for action_type '{self.action_type}'")

        unexpected_fields = [
            field_name
            for field_name, payload in action_map.items()
            if field_name != self.action_type and payload is not None
        ]
        if unexpected_fields:
            extras = ", ".join(sorted(unexpected_fields))
            raise ValueError(
                f"Unexpected payload field(s) for action_type '{self.action_type}': {extras}"
            )


class RewardModel(BaseModel):
    """Reward information for a step."""

    step_reward: float = Field(..., ge=0.0, le=1.0)
    cumulative_reward: float
    reward_breakdown: dict[str, float] = Field(default_factory=dict)


class TicketStateModel(BaseModel):
    """State of a single ticket in the triage process."""

    ticket_id: str
    triaged: bool
    actions_taken: list[str]


class StateModel(BaseModel):
    """Full state of the environment."""

    current_task_id: str
    current_ticket_index: int
    total_tickets: int
    tickets_state: list[TicketStateModel]
    steps_used: int
    steps_remaining: int
    cumulative_reward: float
    episode_done: bool
