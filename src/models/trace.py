"""Decision trace models for observability."""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Dict, List, Optional, Any


@dataclass
class TaskFeatures:
    """Computed features for a task during scheduling."""
    
    task_id: str
    due_in_days: float
    effort_minutes: int
    overrun_factor: float
    slack_days: float
    dependency_ready: bool
    risk_score: Optional[float] = None
    risk_components: Optional[Dict[str, float]] = None


@dataclass
class SchedulingDecision:
    """Records a single scheduling decision."""
    
    task_id: str
    scheduled_date: datetime
    scheduled_minutes: int
    reason: str
    constraint_applied: Optional[str] = None


@dataclass
class DecisionTrace:
    """Complete trace of a scheduling run."""
    
    run_id: str
    timestamp: datetime
    policy_name: str
    config: Dict[str, Any]
    task_features: List[TaskFeatures]
    decisions: List[SchedulingDecision]
    summary_stats: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert trace to dictionary for JSON export."""
        return asdict(self)
    
    def to_human_readable(self) -> str:
        """Generate human-readable log format."""
        lines = [
            f"=== Scheduling Run: {self.run_id} ===",
            f"Policy: {self.policy_name}",
            f"Timestamp: {self.timestamp}",
            f"",
            "Configuration:",
        ]
        
        for key, value in self.config.items():
            lines.append(f"  {key}: {value}")
        
        lines.extend([
            "",
            "Task Features:",
        ])
        
        for tf in self.task_features:
            lines.append(f"  Task {tf.task_id}:")
            lines.append(f"    Due in: {tf.due_in_days:.1f} days")
            lines.append(f"    Effort: {tf.effort_minutes} minutes")
            lines.append(f"    Overrun factor: {tf.overrun_factor:.2f}")
            lines.append(f"    Slack: {tf.slack_days:.1f} days")
            lines.append(f"    Dependencies ready: {tf.dependency_ready}")
            if tf.risk_score is not None:
                lines.append(f"    Risk score: {tf.risk_score:.3f}")
                if tf.risk_components:
                    lines.append(f"    Risk components: {tf.risk_components}")
        
        lines.extend([
            "",
            "Scheduling Decisions:",
        ])
        
        for decision in self.decisions:
            lines.append(f"  {decision.task_id} -> {decision.scheduled_date.date()}: {decision.scheduled_minutes} min")
            lines.append(f"    Reason: {decision.reason}")
            if decision.constraint_applied:
                lines.append(f"    Constraint: {decision.constraint_applied}")
        
        lines.extend([
            "",
            "Summary Statistics:",
        ])
        
        for key, value in self.summary_stats.items():
            lines.append(f"  {key}: {value}")
        
        lines.append("=" * 50)
        
        return "\n".join(lines)

