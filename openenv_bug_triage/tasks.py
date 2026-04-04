"""
Task definitions and data loaders for Bug Triage OpenEnv.
"""

import json
import random
from pathlib import Path
from typing import Optional
from datetime import datetime
from .models import TicketModel, TicketGroundTruth


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
        
        # Create lookup for ground truth
        self.truth_map = {gt.ticket_id: gt for gt in ground_truths}
    
    def get_ground_truth(self, ticket_id: str) -> Optional[TicketGroundTruth]:
        """Get ground truth for a ticket."""
        return self.truth_map.get(ticket_id)
    
    def shuffle_tickets(self, seed: int):
        """Shuffle tickets deterministically."""
        rng = random.Random(seed)
        combined = list(zip(self.tickets, self.ground_truths))
        rng.shuffle(combined)
        self.tickets, self.ground_truths = zip(*combined)
        self.tickets = list(self.tickets)
        self.ground_truths = list(self.ground_truths)
        # Rebuild truth map
        self.truth_map = {gt.ticket_id: gt for gt in self.ground_truths}


def load_task(task_id: str, seed: Optional[int] = None) -> TaskDefinition:
    """
    Load a task from JSON fixture.
    
    Args:
        task_id: One of 'bug_triage_easy', 'bug_triage_medium', 'bug_triage_hard'
        seed: Random seed for deterministic shuffling
    
    Returns:
        TaskDefinition with loaded tickets and ground truth
    """
    # Get path to data file
    data_dir = Path(__file__).parent / "data" / "tasks"
    data_file = data_dir / f"{task_id}.json"
    
    if not data_file.exists():
        raise FileNotFoundError(f"Task data not found: {data_file}")
    
    # Load JSON
    with open(data_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Parse tickets
    tickets = []
    for ticket_data in data["tickets"]:
        # Convert created_at string to datetime
        ticket_data["created_at"] = datetime.fromisoformat(ticket_data["created_at"])
        tickets.append(TicketModel(**ticket_data))
    
    # Parse ground truths
    ground_truths = []
    for gt_data in data["ground_truths"]:
        ground_truths.append(TicketGroundTruth(**gt_data))
    
    # Create task definition
    task = TaskDefinition(
        task_id=task_id,
        tickets=tickets,
        ground_truths=ground_truths,
        step_budget=data["step_budget"],
        available_teams=data["available_teams"],
        available_components=data["available_components"],
    )
    
    # Shuffle if seed provided
    if seed is not None:
        task.shuffle_tickets(seed)
    
    return task


# Task registry
TASKS = {
    "bug_triage_easy": {
        "difficulty": "easy",
        "description": "8 clear tickets, minimal duplicates",
    },
    "bug_triage_medium": {
        "difficulty": "medium",
        "description": "15 mixed-quality tickets, several duplicates",
    },
    "bug_triage_hard": {
        "difficulty": "hard",
        "description": "25 noisy tickets, strict SLA pressure",
    },
}


def list_tasks() -> dict:
    """List all available tasks."""
    return TASKS
