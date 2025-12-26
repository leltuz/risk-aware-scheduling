"""Main entry point for Risk-Aware Task Scheduling Engine."""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from src.engine.scheduler import Scheduler
from src.evaluation.evaluator import Evaluator
from src.evaluation.counterfactual import CounterfactualAnalyzer
from src.evaluation.generator import TaskGenerator
from src.policies.baseline import BaselinePolicy
from src.policies.risk_aware import RiskAwarePolicy
from src.utils.config import load_config, get_default_config


def run_scheduling(config_path: str, policy_name: str = "risk-aware"):
    """Run scheduling with given policy."""
    config = load_config(config_path) if config_path else get_default_config()
    
    # Create policy
    if policy_name.lower() == "baseline":
        policy = BaselinePolicy(config)
    elif policy_name.lower() == "risk-aware":
        policy = RiskAwarePolicy(config)
    else:
        raise ValueError(f"Unknown policy: {policy_name}")
    
    # Create scheduler
    scheduler = Scheduler(policy, config)
    
    # Generate tasks
    generator = TaskGenerator(seed=42, config=config)
    today = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)
    tasks, outcomes = generator.generate_task_stream(today)
    
    # Schedule
    scheduled, trace = scheduler.schedule(tasks, today, outcomes)
    
    # Output results
    print(f"\nScheduling completed using {policy_name.upper()} policy")
    print(f"Scheduled {len(scheduled)} task assignments")
    print(f"\nTrace saved to: results/trace_{trace.run_id}.json")
    
    # Save trace
    results_dir = Path("results")
    results_dir.mkdir(exist_ok=True)
    
    trace_path = results_dir / f"trace_{trace.run_id}.json"
    with open(trace_path, 'w') as f:
        json.dump(trace.to_dict(), f, indent=2, default=str)
    
    # Save human-readable log
    log_path = results_dir / f"trace_{trace.run_id}.log"
    with open(log_path, 'w') as f:
        f.write(trace.to_human_readable())
    
    print(f"Human-readable log saved to: {log_path}")
    
    return scheduled, trace


def run_evaluation(config_path: str):
    """Run full evaluation suite."""
    config = load_config(config_path) if config_path else get_default_config()
    
    evaluator = Evaluator(config)
    baseline_result, risk_aware_result = evaluator.run_evaluation()
    
    # Run counterfactual analysis
    generator = TaskGenerator(seed=42, config=config)
    today = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)
    tasks, outcomes = generator.generate_task_stream(today)
    
    analyzer = CounterfactualAnalyzer()
    cases = analyzer.analyze(baseline_result, risk_aware_result, tasks, outcomes)
    report = analyzer.generate_report(cases)
    
    # Save counterfactual report
    results_dir = Path("results")
    with open(results_dir / "counterfactual_analysis.json", 'w') as f:
        json.dump(report, f, indent=2, default=str)
    
    print(f"\nCounterfactual analysis saved to: results/counterfactual_analysis.json")
    
    return baseline_result, risk_aware_result, report


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Risk-Aware Task Scheduling Engine"
    )
    parser.add_argument(
        'command',
        choices=['schedule', 'evaluate', 'generate-tasks'],
        help='Command to run'
    )
    parser.add_argument(
        '--config',
        type=str,
        default='config.yaml',
        help='Path to configuration file (default: config.yaml)'
    )
    parser.add_argument(
        '--policy',
        type=str,
        choices=['baseline', 'risk-aware'],
        default='risk-aware',
        help='Scheduling policy to use (default: risk-aware)'
    )
    
    args = parser.parse_args()
    
    # Create results directory
    Path("results").mkdir(exist_ok=True)
    
    if args.command == 'schedule':
        run_scheduling(args.config, args.policy)
    elif args.command == 'evaluate':
        run_evaluation(args.config)
    elif args.command == 'generate-tasks':
        config = load_config(args.config) if Path(args.config).exists() else get_default_config()
        generator = TaskGenerator(seed=42, config=config)
        today = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)
        tasks, outcomes = generator.generate_task_stream(today)
        
        print(f"Generated {len(tasks)} tasks")
        print(f"Generated {len(outcomes)} outcomes")
        
        # Save to JSON for inspection
        results_dir = Path("results")
        tasks_data = [
            {
                'task_id': t.task_id,
                'title': t.title,
                'due_date': t.due_date.isoformat(),
                'estimated_minutes': t.estimated_minutes,
                'priority': t.priority,
                'depends_on': t.depends_on,
            }
            for t in tasks
        ]
        
        with open(results_dir / "generated_tasks.json", 'w') as f:
            json.dump(tasks_data, f, indent=2)
        
        print(f"Tasks saved to: results/generated_tasks.json")


if __name__ == "__main__":
    main()

