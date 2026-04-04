"""
Reward calculation logic for bug triage environment.
"""

from typing import Optional
from .models import ActionModel, TicketGroundTruth


class RewardCalculator:
    """Calculates rewards for bug triage actions."""
    
    # Dense progress signals
    CORRECT_SEVERITY = 0.20
    CORRECT_PRIORITY = 0.15
    CORRECT_COMPONENT = 0.15
    CORRECT_TEAM = 0.10
    CORRECT_DUPLICATE = 0.15
    CORRECT_REQUEST_INFO = 0.10
    CORRECT_ESCALATION = 0.15
    
    # Negative signals
    INCORRECT_CLOSE_DEFER = -0.20
    MISSED_ESCALATION = -0.15
    INVALID_ACTION = -0.05
    REPEATED_NOOP = -0.02
    UNNECESSARY_SWITCH = -0.01
    
    # Terminal bonuses/penalties
    ALL_CRITICAL_TRIAGED = 0.10
    BUDGET_EXHAUSTED_CRITICAL_REMAINING = -0.10
    
    def __init__(self):
        self.action_history = []
    
    def calculate_step_reward(
        self,
        action: ActionModel,
        ground_truth: TicketGroundTruth,
        ticket_id: str,
        is_valid: bool,
        is_critical_ticket: bool,
        is_terminal: bool = False,
        all_critical_triaged: bool = False,
        budget_exhausted_with_critical: bool = False,
    ) -> tuple[float, dict[str, float]]:
        """
        Calculate reward for a single step.
        
        Returns:
            tuple of (clamped_reward, breakdown_dict)
        """
        breakdown = {}
        total_reward = 0.0
        
        if not is_valid:
            breakdown["invalid_action"] = self.INVALID_ACTION
            total_reward += self.INVALID_ACTION
            return self._clamp_reward(total_reward), breakdown
        
        # Track action history for loop detection
        self.action_history.append((ticket_id, action.action_type))
        
        # Check for classify action
        if action.action_type == "classify" and action.classify:
            if action.classify.severity == ground_truth.true_severity:
                breakdown["correct_severity"] = self.CORRECT_SEVERITY
                total_reward += self.CORRECT_SEVERITY
            
            if action.classify.priority == ground_truth.true_priority:
                breakdown["correct_priority"] = self.CORRECT_PRIORITY
                total_reward += self.CORRECT_PRIORITY
            
            if action.classify.component == ground_truth.true_component:
                breakdown["correct_component"] = self.CORRECT_COMPONENT
                total_reward += self.CORRECT_COMPONENT
        
        # Check for assign action
        if action.action_type == "assign" and action.assign:
            if action.assign.team == ground_truth.true_assignee_team:
                breakdown["correct_team"] = self.CORRECT_TEAM
                total_reward += self.CORRECT_TEAM
        
        # Check for duplicate marking
        if action.action_type == "mark_duplicate" and action.mark_duplicate:
            if ground_truth.duplicate_of == action.mark_duplicate.canonical_ticket_id:
                breakdown["correct_duplicate"] = self.CORRECT_DUPLICATE
                total_reward += self.CORRECT_DUPLICATE
        
        # Check for request info
        if action.action_type == "request_info" and action.request_info:
            if ground_truth.needs_more_info:
                breakdown["correct_request_info"] = self.CORRECT_REQUEST_INFO
                total_reward += self.CORRECT_REQUEST_INFO
        
        # Check for escalation
        if action.action_type == "escalate_incident" and action.escalate_incident:
            if ground_truth.true_severity in ["sev0", "sev1"]:
                breakdown["correct_escalation"] = self.CORRECT_ESCALATION
                total_reward += self.CORRECT_ESCALATION
        
        # Penalize incorrect close/defer
        if action.action_type in ["close", "defer"]:
            if not ground_truth.duplicate_of and ground_truth.needs_more_info:
                breakdown["incorrect_close_defer"] = self.INCORRECT_CLOSE_DEFER
                total_reward += self.INCORRECT_CLOSE_DEFER
        
        # Penalize missed critical escalation
        if is_critical_ticket and action.action_type != "escalate_incident":
            if ground_truth.true_severity in ["sev0", "sev1"]:
                breakdown["missed_escalation"] = self.MISSED_ESCALATION
                total_reward += self.MISSED_ESCALATION
        
        # Check for repeated no-op behavior
        if len(self.action_history) >= 3:
            last_three = self.action_history[-3:]
            if last_three[0] == last_three[1] == last_three[2]:
                breakdown["repeated_noop"] = self.REPEATED_NOOP
                total_reward += self.REPEATED_NOOP
        
        # Terminal bonuses/penalties
        if is_terminal:
            if all_critical_triaged:
                breakdown["all_critical_triaged"] = self.ALL_CRITICAL_TRIAGED
                total_reward += self.ALL_CRITICAL_TRIAGED
            
            if budget_exhausted_with_critical:
                breakdown["budget_exhausted"] = self.BUDGET_EXHAUSTED_CRITICAL_REMAINING
                total_reward += self.BUDGET_EXHAUSTED_CRITICAL_REMAINING
        
        return self._clamp_reward(total_reward), breakdown
    
    def _clamp_reward(self, reward: float) -> float:
        """Clamp reward to [-1.0, 1.0] range."""
        return max(-1.0, min(1.0, reward))
    
    def reset(self):
        """Reset action history."""
        self.action_history = []
