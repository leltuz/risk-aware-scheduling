"""Base scheduling policy interface."""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import List

from ..models.task import Task
from ..models.trace import TaskFeatures


class SchedulingPolicy(ABC):
    """Abstract base class for scheduling policies."""
    
    def __init__(self, config: dict):
        """Initialize policy with configuration."""
        self.config = config
    
    @abstractmethod
    def compute_task_features(
        self,
        task: Task,
        today: datetime,
        historical_outcomes: dict,
        scheduled_tasks: dict,
    ) -> TaskFeatures:
        """Compute features for a task given current state."""
        pass
    
    @abstractmethod
    def order_tasks(
        self,
        tasks: List[Task],
        today: datetime,
        historical_outcomes: dict,
        scheduled_tasks: dict,
    ) -> List[Task]:
        """Order tasks according to policy logic."""
        pass
    
    @abstractmethod
    def get_policy_name(self) -> str:
        """Return the name of this policy."""
        pass

