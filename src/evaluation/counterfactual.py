"""Counterfactual analysis for evaluation."""

from datetime import datetime
from typing import Dict, List

from ..models.task import Task, TaskOutcome
from .evaluator import EvaluationResult


class CounterfactualCase:
    """Represents a counterfactual analysis case."""
    
    def __init__(self, task_id: str, case_type: str, description: str):
        self.task_id = task_id
        self.case_type = case_type  # 'prevented_miss', 'unnecessary_early', 'both_failed'
        self.description = description
        self.baseline_completed = False
        self.risk_aware_completed = False
        self.baseline_lateness = 0.0
        self.risk_aware_lateness = 0.0


class CounterfactualAnalyzer:
    """Analyzes counterfactual scenarios between policies."""
    
    def analyze(
        self,
        baseline_result: EvaluationResult,
        risk_aware_result: EvaluationResult,
        tasks: List[Task],
        outcomes: Dict[str, TaskOutcome],
    ) -> List[CounterfactualCase]:
        """Perform counterfactual analysis."""
        cases = []
        
        # Build completion status for each task
        baseline_completed = set()
        risk_aware_completed = set()
        
        # This is simplified - in a real implementation, we'd track actual completion
        # from the scheduled tasks and outcomes
        for task in tasks:
            baseline_on_time = task.task_id in baseline_completed or baseline_result.tasks_completed_on_time > 0
            risk_aware_on_time = task.task_id in risk_aware_completed or risk_aware_result.tasks_completed_on_time > 0
            
            # Determine case type
            if not baseline_on_time and risk_aware_on_time:
                # Risk-aware prevented a miss
                cases.append(CounterfactualCase(
                    task_id=task.task_id,
                    case_type='prevented_miss',
                    description=f"Risk-aware scheduling prevented missed deadline for {task.task_id}"
                ))
            elif baseline_on_time and not risk_aware_on_time:
                # Risk-aware caused unnecessary early scheduling (but actually failed)
                cases.append(CounterfactualCase(
                    task_id=task.task_id,
                    case_type='unnecessary_early',
                    description=f"Risk-aware scheduling failed where baseline succeeded for {task.task_id}"
                ))
            elif not baseline_on_time and not risk_aware_on_time:
                # Both failed
                cases.append(CounterfactualCase(
                    task_id=task.task_id,
                    case_type='both_failed',
                    description=f"Both policies failed to schedule {task.task_id} on time"
                ))
        
        return cases
    
    def generate_report(
        self,
        cases: List[CounterfactualCase],
        output_path: str = "results/counterfactual_analysis.json",
    ) -> Dict:
        """Generate counterfactual analysis report."""
        prevented_misses = [c for c in cases if c.case_type == 'prevented_miss']
        unnecessary_early = [c for c in cases if c.case_type == 'unnecessary_early']
        both_failed = [c for c in cases if c.case_type == 'both_failed']
        
        report = {
            'summary': {
                'total_cases': len(cases),
                'prevented_misses': len(prevented_misses),
                'unnecessary_early_scheduling': len(unnecessary_early),
                'both_failed': len(both_failed),
            },
            'prevented_misses': [
                {'task_id': c.task_id, 'description': c.description}
                for c in prevented_misses
            ],
            'unnecessary_early_scheduling': [
                {'task_id': c.task_id, 'description': c.description}
                for c in unnecessary_early
            ],
            'both_failed': [
                {'task_id': c.task_id, 'description': c.description}
                for c in both_failed
            ],
        }
        
        return report

