
"""Task definitions and data loaders for Bug Triage OpenEnv."""

from __future__ import annotations

import random
from copy import deepcopy
from datetime import datetime
from typing import Optional

from models import TicketGroundTruth, TicketModel

from . import task_easy, task_hard, task_medium


TASK_MODULES = {
    task_easy.TASK_ID: task_easy,
    task_medium.TASK_ID: task_medium,
    task_hard.TASK_ID: task_hard,
}


class TaskDefinition:
    """Represents a task with tickets and ground truth."""

    def __init__(
        self,
        task_id: str,
        tickets: list[TicketModel],
        ground_truths: list[TicketGroundTruth],
        step_budget: int,
        available_teams: list[str],
        available_components: list[str],
    ):
        self.task_id = task_id
        self.tickets = tickets
        self.ground_truths = ground_truths
        self.step_budget = step_budget
        self.available_teams = available_teams
        self.available_components = available_components
        self._validate_integrity()
        self.truth_map = {gt.ticket_id: gt for gt in ground_truths}

    def get_ground_truth(self, ticket_id: str) -> Optional[TicketGroundTruth]:
        """Get ground truth for a ticket."""
        return self.truth_map.get(ticket_id)

    def _validate_integrity(self) -> None:
        """Ensure ticket and ground-truth ids are unique and aligned."""
        ticket_ids = [ticket.ticket_id for ticket in self.tickets]
        ground_truth_ids = [truth.ticket_id for truth in self.ground_truths]

        if len(ticket_ids) != len(set(ticket_ids)):
            raise ValueError("Duplicate ticket_id values found in tickets")
        if len(ground_truth_ids) != len(set(ground_truth_ids)):
            raise ValueError("Duplicate ticket_id values found in ground truths")

        ticket_id_set = set(ticket_ids)
        ground_truth_id_set = set(ground_truth_ids)
        if ticket_id_set != ground_truth_id_set:
            missing_truth = sorted(ticket_id_set - ground_truth_id_set)
            extra_truth = sorted(ground_truth_id_set - ticket_id_set)
            raise ValueError(
                "Tickets and ground truths must contain the same ticket ids. "
                f"missing_ground_truth={missing_truth}, extra_ground_truth={extra_truth}"
            )

    def shuffle_tickets(self, seed: int):
        """Shuffle tickets deterministically."""
        self._validate_integrity()
        if not self.tickets:
            self.truth_map = {}
            return

        rng = random.Random(seed)
        shuffled_tickets = list(self.tickets)
        rng.shuffle(shuffled_tickets)

        ground_truth_by_id = {truth.ticket_id: truth for truth in self.ground_truths}
        self.tickets = shuffled_tickets
        self.ground_truths = [ground_truth_by_id[ticket.ticket_id] for ticket in self.tickets]
        self.truth_map = dict(ground_truth_by_id)


def _task_data(task_id: str) -> dict:
    module = TASK_MODULES.get(task_id)
    if module is None:
        raise FileNotFoundError(f"Unknown task id: {task_id}")
    return deepcopy(module.TASK_DATA)


def load_task(task_id: str, seed: Optional[int] = None) -> TaskDefinition:
    """
    Load a task from in-memory fixture.

    Args:
        task_id: One of 'bug_triage_easy', 'bug_triage_medium', 'bug_triage_hard'
        seed: Random seed for deterministic shuffling

    Returns:
        TaskDefinition with loaded tickets and ground truth
    """
    data = _task_data(task_id)

    tickets = []
    for ticket_data in data["tickets"]:
        ticket_data["created_at"] = datetime.fromisoformat(ticket_data["created_at"])
        tickets.append(TicketModel(**ticket_data))

    ground_truths = [TicketGroundTruth(**gt_data) for gt_data in data["ground_truths"]]

    task = TaskDefinition(
        task_id=task_id,
        tickets=tickets,
        ground_truths=ground_truths,
        step_budget=data["step_budget"],
        available_teams=data["available_teams"],
        available_components=data["available_components"],
    )

    if seed is not None:
        task.shuffle_tickets(seed)
    return task


def list_tasks() -> dict:
    """List all available tasks."""
    return {
        task_id: {
            "difficulty": module.DIFFICULTY,
            "description": module.DESCRIPTION,
        }
        for task_id, module in TASK_MODULES.items()
    }


__all__ = [
    "TaskDefinition",
    "load_task",
    "list_tasks",
]
