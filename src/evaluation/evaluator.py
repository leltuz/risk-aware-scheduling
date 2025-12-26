"""Offline evaluation suite."""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple

from ..engine.scheduler import Scheduler, ScheduledTask
from ..models.task import Task, TaskOutcome
from ..models.trace import DecisionTrace
from ..policies.baseline import BaselinePolicy
from ..policies.risk_aware import RiskAwarePolicy
from .generator import TaskGenerator


class EvaluationResult:
    """Results from evaluating a policy."""
    
    def __init__(self, policy_name: str):
        self.policy_name = policy_name
        self.tasks_completed_on_time = 0
        self.tasks_total = 0
        self.total_lateness_minutes = 0
        self.crunch_days = 0
        self.task_splits = 0
        self.schedule_churn = 0.0
        self.average_slack = 0.0
        self.traces: List[DecisionTrace] = []
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON export."""
        on_time_rate = (self.tasks_completed_on_time / self.tasks_total * 100) if self.tasks_total > 0 else 0
        
        return {
            'policy': self.policy_name,
            'on_time_rate_percent': on_time_rate,
            'tasks_completed_on_time': self.tasks_completed_on_time,
            'tasks_total': self.tasks_total,
            'total_lateness_minutes': self.total_lateness_minutes,
            'crunch_days': self.crunch_days,
            'task_splits': self.task_splits,
            'schedule_churn': self.schedule_churn,
            'average_slack': self.average_slack,
        }


class Evaluator:
    """Offline evaluation suite comparing policies."""
    
    def __init__(self, config: dict):
        """Initialize evaluator with configuration."""
        self.config = config
        self.generator = TaskGenerator(seed=42, config=config)
    
    def evaluate_policy(
        self,
        scheduler: Scheduler,
        tasks: List[Task],
        outcomes: Dict[str, TaskOutcome],
        today: datetime,
        simulate_days: int = 14,
    ) -> EvaluationResult:
        """Evaluate a policy using simulation."""
        result = EvaluationResult(scheduler.policy.get_policy_name())
        result.tasks_total = len(tasks)
        
        # Run scheduling
        scheduled, trace = scheduler.schedule(tasks, today, outcomes)
        result.traces.append(trace)
        
        # Build schedule: task_id -> list of (date, minutes) assignments
        task_schedule: Dict[str, List[Tuple[datetime, int]]] = {}
        for s in scheduled:
            if s.task_id not in task_schedule:
                task_schedule[s.task_id] = []
            task_schedule[s.task_id].append((s.date, s.minutes))
        
        # Check on-time completion
        for task in tasks:
            if task.task_id in task_schedule:
                # Find start date (earliest scheduled day)
                schedule_entries = sorted(task_schedule[task.task_id], key=lambda x: x[0])
                start_date = schedule_entries[0][0]
                
                # Get actual minutes from outcome, or use estimate if no outcome
                outcome = outcomes.get(task.task_id)
                actual_minutes = outcome.actual_minutes if outcome else task.estimated_minutes
                
                # Calculate completion: start date + actual minutes
                # Assume work happens during working hours
                daily_capacity = self.config.get('scheduling', {}).get('daily_capacity_minutes', 480)
                completion_days = actual_minutes / daily_capacity
                actual_completion = start_date + timedelta(days=completion_days)
                
                if actual_completion <= task.due_date:
                    result.tasks_completed_on_time += 1
                else:
                    lateness = (actual_completion - task.due_date).total_seconds() / 60
                    result.total_lateness_minutes += max(0, lateness)
            else:
                # Unscheduled task counts as late
                outcome = outcomes.get(task.task_id)
                actual_minutes = outcome.actual_minutes if outcome else task.estimated_minutes
                result.total_lateness_minutes += actual_minutes
        
        # Extract metrics from trace
        summary = trace.summary_stats
        result.crunch_days = summary.get('crunch_days', 0)
        result.task_splits = summary.get('task_splits', 0)
        
        # Calculate average slack
        if trace.task_features:
            slacks = [tf.slack_days for tf in trace.task_features if tf.slack_days is not None]
            result.average_slack = sum(slacks) / len(slacks) if slacks else 0.0
        
        # Calculate schedule churn (simplified: measure day-to-day changes)
        # For now, set to 0 (would require multi-day simulation)
        result.schedule_churn = 0.0
        
        return result
    
    def compare_policies(
        self,
        tasks: List[Task],
        outcomes: Dict[str, TaskOutcome],
        today: datetime,
        config: dict,
    ) -> Tuple[EvaluationResult, EvaluationResult]:
        """Compare baseline and risk-aware policies."""
        # Create schedulers
        baseline_policy = BaselinePolicy(config)
        risk_aware_policy = RiskAwarePolicy(config)
        
        baseline_scheduler = Scheduler(baseline_policy, config)
        risk_aware_scheduler = Scheduler(risk_aware_policy, config)
        
        # Evaluate both
        baseline_result = self.evaluate_policy(baseline_scheduler, tasks, outcomes, today)
        risk_aware_result = self.evaluate_policy(risk_aware_scheduler, tasks, outcomes, today)
        
        return baseline_result, risk_aware_result
    
    def run_evaluation(
        self,
        output_dir: str = "results",
        today: datetime = None,
    ) -> Tuple[EvaluationResult, EvaluationResult]:
        """Run full evaluation suite."""
        if today is None:
            today = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)
        
        # Generate task stream
        tasks, outcomes = self.generator.generate_task_stream(today)
        
        # Compare policies
        baseline_result, risk_aware_result = self.compare_policies(tasks, outcomes, today, self.config)
        
        # Export results
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)
        
        # Save comparison report
        comparison = {
            'baseline': baseline_result.to_dict(),
            'risk_aware': risk_aware_result.to_dict(),
            'improvement': {
                'on_time_rate_delta': risk_aware_result.to_dict()['on_time_rate_percent'] - baseline_result.to_dict()['on_time_rate_percent'],
                'lateness_reduction_minutes': baseline_result.total_lateness_minutes - risk_aware_result.total_lateness_minutes,
                'crunch_days_reduction': baseline_result.crunch_days - risk_aware_result.crunch_days,
            }
        }
        
        with open(output_path / 'evaluation_results.json', 'w') as f:
            json.dump(comparison, f, indent=2, default=str)
        
        # Save traces
        for trace in baseline_result.traces:
            trace_path = output_path / f"trace_{trace.policy_name.lower()}_{trace.run_id}.json"
            with open(trace_path, 'w') as f:
                json.dump(trace.to_dict(), f, indent=2, default=str)
        
        for trace in risk_aware_result.traces:
            trace_path = output_path / f"trace_{trace.policy_name.lower()}_{trace.run_id}.json"
            with open(trace_path, 'w') as f:
                json.dump(trace.to_dict(), f, indent=2, default=str)
        
        # Print summary
        self._print_comparison(baseline_result, risk_aware_result)
        
        return baseline_result, risk_aware_result
    
    def _print_comparison(self, baseline: EvaluationResult, risk_aware: EvaluationResult):
        """Print comparison report."""
        print("\n" + "=" * 70)
        print("EVALUATION RESULTS COMPARISON")
        print("=" * 70)
        print(f"\n{'Metric':<40} {'Baseline':<15} {'Risk-Aware':<15}")
        print("-" * 70)
        
        baseline_dict = baseline.to_dict()
        risk_aware_dict = risk_aware.to_dict()
        
        print(f"{'On-time rate (%)':<40} {baseline_dict['on_time_rate_percent']:<15.2f} {risk_aware_dict['on_time_rate_percent']:<15.2f}")
        print(f"{'Total lateness (minutes)':<40} {baseline.total_lateness_minutes:<15.0f} {risk_aware.total_lateness_minutes:<15.0f}")
        print(f"{'Crunch days':<40} {baseline.crunch_days:<15} {risk_aware.crunch_days:<15}")
        print(f"{'Task splits':<40} {baseline.task_splits:<15} {risk_aware.task_splits:<15}")
        print(f"{'Average slack (days)':<40} {baseline.average_slack:<15.2f} {risk_aware.average_slack:<15.2f}")
        
        print("\n" + "=" * 70)

