"""Baseline deadline-then-priority scheduling policy."""

from datetime import datetime, timedelta
from typing import Dict, List

from ..models.task import Task
from ..models.trace import TaskFeatures
from .base import SchedulingPolicy


class BaselinePolicy(SchedulingPolicy):
    """Baseline policy: deadline first, then priority."""
    
    def compute_task_features(
        self,
        task: Task,
        today: datetime,
        historical_outcomes: Dict[str, float],
        scheduled_tasks: Dict[str, datetime],
    ) -> TaskFeatures:
        """Compute features for baseline policy."""
        due_delta = task.due_date - today
        due_in_days = due_delta.total_seconds() / (24 * 3600)
        
        overrun_factor = historical_outcomes.get(task.task_id, task.historical_overrun_factor)
        
        # Check if dependencies are scheduled/completed
        dependency_ready = all(
            dep_id in scheduled_tasks or scheduled_tasks.get(dep_id) is not None
            for dep_id in task.depends_on
        )
        
        # Simple slack: days until due - estimated days needed
        estimated_days = task.estimated_minutes / (60 * 8)  # Assume 8 hours per day
        slack_days = due_in_days - estimated_days
        
        return TaskFeatures(
            task_id=task.task_id,
            due_in_days=due_in_days,
            effort_minutes=task.estimated_minutes,
            overrun_factor=overrun_factor,
            slack_days=slack_days,
            dependency_ready=dependency_ready,
        )
    
    def order_tasks(
        self,
        tasks: List[Task],
        today: datetime,
        historical_outcomes: Dict[str, float],
        scheduled_tasks: Dict[str, datetime],
    ) -> List[Task]:
        """Order tasks by deadline, then priority, then created_at."""
        tie_break = self.config.get('tie_break', {})
        primary = tie_break.get('primary', 'priority')
        secondary = tie_break.get('secondary', 'created_at')
        
        def sort_key(task: Task):
            # Primary: due date (earlier first)
            due_date_key = task.due_date
            
            # Secondary: priority (higher first, so negate)
            priority_key = -task.priority if primary == 'priority' else 0
            
            # Tertiary: created_at (earlier first)
            created_key = task.created_at if secondary == 'created_at' else datetime.min
            
            return (due_date_key, priority_key, created_key)
        
        return sorted(tasks, key=sort_key)
    
    def get_policy_name(self) -> str:
        """Return policy name."""
        return "BASELINE"

