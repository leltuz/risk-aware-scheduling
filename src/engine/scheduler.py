"""Core scheduling engine."""

import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from ..models.task import Task, TaskOutcome
from ..models.trace import DecisionTrace, SchedulingDecision, TaskFeatures
from ..policies.base import SchedulingPolicy
from ..utils.datetime_utils import get_working_days, is_working_day


class ScheduledTask:
    """Represents a scheduled task assignment."""
    
    def __init__(self, task_id: str, date: datetime, minutes: int):
        self.task_id = task_id
        self.date = date
        self.minutes = minutes


class Scheduler:
    """Core scheduling engine."""
    
    def __init__(self, policy: SchedulingPolicy, config: dict):
        """Initialize scheduler with policy and configuration."""
        self.policy = policy
        self.config = config
        self.scheduling_config = config.get('scheduling', {})
        self.daily_capacity = self.scheduling_config.get('daily_capacity_minutes', 480)
        self.horizon_days = self.scheduling_config.get('planning_horizon_days', 14)
        self.working_days = self.scheduling_config.get('working_days', [0, 1, 2, 3, 4])
    
    def schedule(
        self,
        tasks: List[Task],
        today: datetime,
        historical_outcomes: Optional[Dict[str, TaskOutcome]] = None,
    ) -> tuple[List[ScheduledTask], DecisionTrace]:
        """Generate a schedule for tasks."""
        run_id = str(uuid.uuid4())[:8]
        
        # Build historical outcomes map
        outcomes_map = {}
        if historical_outcomes:
            for task_id, outcome in historical_outcomes.items():
                outcomes_map[task_id] = outcome.get_overrun_factor()
        
        # Compute task features
        scheduled_tasks_map = {}
        task_features_list = []
        
        for task in tasks:
            features = self.policy.compute_task_features(
                task, today, outcomes_map, scheduled_tasks_map
            )
            task_features_list.append(features)
        
        # Order tasks according to policy
        ordered_tasks = self.policy.order_tasks(tasks, today, outcomes_map, scheduled_tasks_map)
        
        # Generate schedule
        end_date = today + timedelta(days=self.horizon_days)
        working_days_list = get_working_days(today, end_date, self.working_days)
        
        if not working_days_list:
            # No working days in horizon
            return [], self._create_empty_trace(run_id, today, task_features_list)
        
        scheduled = []
        decisions = []
        daily_allocations: Dict[datetime, int] = {day: 0 for day in working_days_list}
        
        # Track which tasks are fully scheduled
        task_remaining: Dict[str, int] = {}
        for task in ordered_tasks:
            task_remaining[task.task_id] = task.estimated_minutes
        
        # Schedule tasks
        for task in ordered_tasks:
            if not self._are_dependencies_scheduled(task, scheduled):
                decisions.append(SchedulingDecision(
                    task_id=task.task_id,
                    scheduled_date=datetime.min,
                    scheduled_minutes=0,
                    reason="Dependencies not scheduled",
                    constraint_applied="dependency_block"
                ))
                continue
            
            remaining = task_remaining[task.task_id]
            if remaining <= 0:
                continue
            
            # Find earliest available slot
            scheduled_parts = []
            for day in working_days_list:
                if day < today:
                    continue
                
                if not is_working_day(day, self.working_days):
                    continue
                
                available = self.daily_capacity - daily_allocations[day]
                
                # Respect task constraints
                if task.min_start_time and day < task.min_start_time:
                    continue
                
                if task.max_daily_minutes:
                    available = min(available, task.max_daily_minutes)
                
                if available > 0 and remaining > 0:
                    allocate = min(available, remaining)
                    daily_allocations[day] += allocate
                    remaining -= allocate
                    
                    scheduled.append(ScheduledTask(task.task_id, day, allocate))
                    scheduled_parts.append((day, allocate))
            
            # Record decision
            if scheduled_parts:
                total_scheduled = sum(minutes for _, minutes in scheduled_parts)
                if len(scheduled_parts) > 1:
                    reason = f"Scheduled across {len(scheduled_parts)} days due to capacity"
                    constraint = "task_split"
                else:
                    reason = "Scheduled by policy ordering"
                    constraint = None
                
                decisions.append(SchedulingDecision(
                    task_id=task.task_id,
                    scheduled_date=scheduled_parts[0][0],
                    scheduled_minutes=total_scheduled,
                    reason=reason,
                    constraint_applied=constraint
                ))
                
                task_remaining[task.task_id] = remaining
            else:
                decisions.append(SchedulingDecision(
                    task_id=task.task_id,
                    scheduled_date=datetime.min,
                    scheduled_minutes=0,
                    reason="No capacity available in horizon",
                    constraint_applied="capacity_exhausted"
                ))
        
        # Compute summary statistics
        summary = self._compute_summary_stats(scheduled, daily_allocations, decisions, tasks)
        
        trace = DecisionTrace(
            run_id=run_id,
            timestamp=datetime.now(),
            policy_name=self.policy.get_policy_name(),
            config={
                'daily_capacity': self.daily_capacity,
                'horizon_days': self.horizon_days,
                'working_days': self.working_days,
            },
            task_features=task_features_list,
            decisions=decisions,
            summary_stats=summary,
        )
        
        return scheduled, trace
    
    def _are_dependencies_scheduled(self, task: Task, scheduled: List[ScheduledTask]) -> bool:
        """Check if all dependencies are scheduled."""
        if not task.depends_on:
            return True
        
        scheduled_task_ids = {s.task_id for s in scheduled}
        return all(dep_id in scheduled_task_ids for dep_id in task.depends_on)
    
    def _compute_summary_stats(
        self,
        scheduled: List[ScheduledTask],
        daily_allocations: Dict[datetime, int],
        decisions: List[SchedulingDecision],
        tasks: List[Task],
    ) -> Dict[str, any]:
        """Compute summary statistics for the trace."""
        task_ids_scheduled = {s.task_id for s in scheduled}
        tasks_scheduled = len(task_ids_scheduled)
        tasks_total = len(tasks)
        
        # Count splits
        task_day_counts: Dict[str, int] = {}
        for s in scheduled:
            task_day_counts[s.task_id] = task_day_counts.get(s.task_id, 0) + 1
        splits = sum(1 for count in task_day_counts.values() if count > 1)
        
        # Count crunch days
        stress_threshold = self.config.get('evaluation', {}).get('stress_threshold_percent', 90)
        stress_minutes = int(self.daily_capacity * (stress_threshold / 100.0))
        crunch_days = sum(1 for allocated in daily_allocations.values() if allocated >= stress_minutes)
        
        # Total scheduled minutes
        total_minutes = sum(s.minutes for s in scheduled)
        
        return {
            'tasks_scheduled': tasks_scheduled,
            'tasks_total': tasks_total,
            'tasks_unscheduled': tasks_total - tasks_scheduled,
            'total_scheduled_minutes': total_minutes,
            'task_splits': splits,
            'crunch_days': crunch_days,
            'average_daily_utilization': (total_minutes / len(daily_allocations) / self.daily_capacity * 100) if daily_allocations else 0,
        }
    
    def _create_empty_trace(
        self,
        run_id: str,
        today: datetime,
        task_features: List[TaskFeatures],
    ) -> DecisionTrace:
        """Create an empty trace when no schedule can be generated."""
        return DecisionTrace(
            run_id=run_id,
            timestamp=datetime.now(),
            policy_name=self.policy.get_policy_name(),
            config={
                'daily_capacity': self.daily_capacity,
                'horizon_days': self.horizon_days,
                'working_days': self.working_days,
            },
            task_features=task_features,
            decisions=[],
            summary_stats={
                'tasks_scheduled': 0,
                'tasks_total': len(task_features),
                'tasks_unscheduled': len(task_features),
            },
        )

