"""Risk-aware scheduling policy."""

from datetime import datetime
from typing import Dict, List

from ..models.task import Task
from ..models.trace import TaskFeatures
from .base import SchedulingPolicy


class RiskAwarePolicy(SchedulingPolicy):
    """Risk-aware policy using risk scoring."""
    
    def __init__(self, config: dict):
        """Initialize risk-aware policy."""
        super().__init__(config)
        self.risk_weights = config.get('risk_weights', {
            'due_proximity': 0.3,
            'effort': 0.2,
            'overrun': 0.3,
            'slack': 0.1,
            'dependencies': 0.1,
        })
    
    def compute_task_features(
        self,
        task: Task,
        today: datetime,
        historical_outcomes: Dict[str, float],
        scheduled_tasks: Dict[str, datetime],
    ) -> TaskFeatures:
        """Compute features and risk score for a task."""
        due_delta = task.due_date - today
        due_in_days = due_delta.total_seconds() / (24 * 3600)
        
        overrun_factor = historical_outcomes.get(task.task_id, task.historical_overrun_factor)
        risk_adjusted_estimate = int(task.estimated_minutes * overrun_factor)
        
        # Check dependencies
        dependency_ready = all(
            dep_id in scheduled_tasks or scheduled_tasks.get(dep_id) is not None
            for dep_id in task.depends_on
        )
        
        # Calculate slack
        daily_capacity = self.config.get('scheduling', {}).get('daily_capacity_minutes', 480)
        estimated_days = risk_adjusted_estimate / daily_capacity
        slack_days = due_in_days - estimated_days
        
        # Compute risk score components
        components = self._compute_risk_components(
            due_in_days,
            risk_adjusted_estimate,
            overrun_factor,
            slack_days,
            dependency_ready,
        )
        
        # Weighted risk score (higher = more risky)
        risk_score = sum(
            components[key] * self.risk_weights.get(key, 0.0)
            for key in components
        )
        
        return TaskFeatures(
            task_id=task.task_id,
            due_in_days=due_in_days,
            effort_minutes=risk_adjusted_estimate,
            overrun_factor=overrun_factor,
            slack_days=slack_days,
            dependency_ready=dependency_ready,
            risk_score=risk_score,
            risk_components=components,
        )
    
    def _compute_risk_components(
        self,
        due_in_days: float,
        effort_minutes: int,
        overrun_factor: float,
        slack_days: float,
        dependency_ready: bool,
    ) -> Dict[str, float]:
        """Compute normalized risk components (0-1 scale, higher = riskier)."""
        # Due proximity: closer to deadline = higher risk
        # Normalize: 0 days = 1.0, 30+ days = 0.0
        due_proximity = max(0.0, min(1.0, 1.0 - (due_in_days / 30.0)))
        
        # Effort: larger tasks = higher risk (normalize by typical max, e.g., 8 hours)
        max_typical_effort = 480  # 8 hours
        effort = min(1.0, effort_minutes / max_typical_effort)
        
        # Overrun: higher overrun factor = higher risk
        # Normalize: 1.0 = 0.0 risk, 2.0+ = 1.0 risk
        overrun = max(0.0, min(1.0, (overrun_factor - 1.0)))
        
        # Slack: negative slack = high risk, positive slack = lower risk
        # Normalize: -7 days = 1.0, 7+ days = 0.0
        slack = max(0.0, min(1.0, (7.0 - slack_days) / 14.0))
        
        # Dependencies: unready = higher risk
        dependencies = 0.0 if dependency_ready else 1.0
        
        return {
            'due_proximity': due_proximity,
            'effort': effort,
            'overrun': overrun,
            'slack': slack,
            'dependencies': dependencies,
        }
    
    def order_tasks(
        self,
        tasks: List[Task],
        today: datetime,
        historical_outcomes: Dict[str, float],
        scheduled_tasks: Dict[str, datetime],
    ) -> List[Task]:
        """Order tasks by risk score (highest first), then deadline, then priority."""
        # Compute features for all tasks
        task_features = {}
        for task in tasks:
            features = self.compute_task_features(task, today, historical_outcomes, scheduled_tasks)
            task_features[task.task_id] = features
        
        tie_break = self.config.get('tie_break', {})
        secondary = tie_break.get('secondary', 'created_at')
        
        def sort_key(task: Task):
            features = task_features[task.task_id]
            
            # Primary: risk score (higher first, so negate)
            risk_key = -features.risk_score if features.risk_score is not None else 0.0
            
            # Secondary: due date (earlier first)
            due_key = task.due_date
            
            # Tertiary: priority (higher first, so negate)
            priority_key = -task.priority
            
            # Quaternary: created_at
            created_key = task.created_at if secondary == 'created_at' else datetime.min
            
            return (risk_key, due_key, priority_key, created_key)
        
        return sorted(tasks, key=sort_key)
    
    def get_policy_name(self) -> str:
        """Return policy name."""
        return "RISK-AWARE"

