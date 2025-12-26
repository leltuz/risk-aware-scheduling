"""Task and outcome generator for evaluation."""

import random
from datetime import datetime, timedelta
from typing import List, Dict

from ..models.task import Task, TaskOutcome


class TaskGenerator:
    """Generates deterministic task sets and outcomes for evaluation."""
    
    def __init__(self, seed: int = 42, config: dict = None):
        """Initialize generator with seed for reproducibility."""
        self.seed = seed
        self.random = random.Random(seed)
        self.config = config or {}
        self.eval_config = self.config.get('evaluation', {})
    
    def generate_tasks(
        self,
        count: int,
        start_date: datetime,
        due_date_range_days: int = 30,
    ) -> List[Task]:
        """Generate a set of tasks with realistic properties."""
        tasks = []
        categories = ['development', 'meeting', 'review', 'planning', 'maintenance']
        
        for i in range(count):
            task_id = f"task_{i:03d}"
            
            # Vary task sizes (some small, some large)
            if self.random.random() < 0.3:
                estimated_minutes = self.random.randint(30, 120)  # Small
            elif self.random.random() < 0.7:
                estimated_minutes = self.random.randint(120, 480)  # Medium
            else:
                estimated_minutes = self.random.randint(480, 1440)  # Large
            
            # Due dates distributed across range
            days_offset = self.random.randint(1, due_date_range_days)
            due_date = start_date + timedelta(days=days_offset)
            
            # Priorities (1-5, higher = more important)
            priority = self.random.randint(1, 5)
            
            # Some tasks have categories
            category = self.random.choice(categories) if self.random.random() < 0.7 else None
            
            # Base overrun factor (will be updated from outcomes)
            overrun_factor = 1.0
            
            # Some tasks have dependencies (create chains)
            depends_on = []
            if i > 0 and self.random.random() < 0.2:
                # Create dependency on a previous task
                dep_idx = self.random.randint(0, i - 1)
                depends_on = [f"task_{dep_idx:03d}"]
            
            task = Task(
                task_id=task_id,
                title=f"Task {i}",
                due_date=due_date,
                estimated_minutes=estimated_minutes,
                priority=priority,
                category=category,
                created_at=start_date - timedelta(days=self.random.randint(0, 7)),
                historical_overrun_factor=overrun_factor,
                depends_on=depends_on,
            )
            
            tasks.append(task)
        
        return tasks
    
    def generate_outcomes(
        self,
        tasks: List[Task],
        overrun_mean: float = 1.2,
        overrun_std: float = 0.3,
    ) -> Dict[str, TaskOutcome]:
        """Generate historical outcomes for tasks."""
        outcomes = {}
        
        for task in tasks:
            # Generate overrun factor from normal distribution
            overrun_factor = max(1.0, self.random.gauss(overrun_mean, overrun_std))
            
            actual_minutes = int(task.estimated_minutes * overrun_factor)
            
            # Completion date is after due date if overrun is high
            completion_delta = timedelta(
                days=max(0, int((overrun_factor - 1.0) * 2))
            )
            completed_at = task.due_date + completion_delta
            
            outcome = TaskOutcome(
                task_id=task.task_id,
                estimated_minutes=task.estimated_minutes,
                actual_minutes=actual_minutes,
                completed_at=completed_at,
                notes=f"Generated outcome with overrun {overrun_factor:.2f}",
            )
            
            outcomes[task.task_id] = outcome
        
        return outcomes
    
    def generate_task_stream(
        self,
        start_date: datetime,
        task_count: int = None,
        due_date_range_days: int = None,
        overrun_mean: float = None,
        overrun_std: float = None,
    ) -> tuple[List[Task], Dict[str, TaskOutcome]]:
        """Generate a complete task stream with outcomes."""
        task_count = task_count or self.eval_config.get('task_count', 50)
        due_date_range_days = due_date_range_days or self.eval_config.get('due_date_range_days', 30)
        overrun_mean = overrun_mean or self.eval_config.get('overrun_mean', 1.2)
        overrun_std = overrun_std or self.eval_config.get('overrun_std', 0.3)
        
        tasks = self.generate_tasks(task_count, start_date, due_date_range_days)
        outcomes = self.generate_outcomes(tasks, overrun_mean, overrun_std)
        
        return tasks, outcomes

