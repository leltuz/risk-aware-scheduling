"""Task and outcome data models."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass
class Task:
    """Represents a schedulable task with metadata."""
    
    task_id: str
    title: str
    due_date: datetime
    estimated_minutes: int
    priority: int
    category: Optional[str] = None
    created_at: Optional[datetime] = None
    historical_overrun_factor: float = 1.0
    depends_on: List[str] = field(default_factory=list)
    min_start_time: Optional[datetime] = None
    max_daily_minutes: Optional[int] = None
    
    def __post_init__(self):
        """Initialize default created_at if not provided."""
        if self.created_at is None:
            self.created_at = datetime.now()
    
    def get_risk_adjusted_estimate(self) -> int:
        """Get estimate adjusted for historical overrun."""
        return int(self.estimated_minutes * self.historical_overrun_factor)


@dataclass
class TaskOutcome:
    """Represents historical completion data for a task."""
    
    task_id: str
    estimated_minutes: int
    actual_minutes: int
    completed_at: datetime
    notes: Optional[str] = None
    
    def get_overrun_factor(self) -> float:
        """Calculate overrun factor (actual / estimated)."""
        if self.estimated_minutes == 0:
            return 1.0
        return self.actual_minutes / self.estimated_minutes

