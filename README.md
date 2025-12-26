# Risk-Aware Task Scheduling Engine

## TL;DR
A deterministic, risk-aware task scheduling system that explicitly accounts for estimation uncertainty by prioritizing tasks using historical overrun risk, slack, dependencies, and effort—rather than relying solely on deadlines.

**Why it matters:**
- Demonstrates scheduling under uncertainty, not idealized estimates
- Makes risk explicit and observable through transparent scoring
- Enables offline, reproducible comparison between baseline and risk-aware policies
- Focuses on policy design and trade-offs, not optimization or learning

## How to Read this README
This README is written as a scheduling policy and evaluation document, not a workflow tool or production scheduler guide.
- **For the motivation and failure mode:** Start with _Problem Statement_ and _Why Naive Deadline Scheduling Fails_ to understand why deadline-first scheduling breaks down under estimation uncertainty.
- **For the core system design:** Read _Architecture Overview_ and _Risk Score Components_ to understand how tasks are modeled, how risk is quantified, and how policies influence scheduling decisions.
- **For evaluation and evidence:** Focus on _Evaluation Methodology_ and _Example Output_ to see how the risk-aware policy is compared against the baseline and what metrics are used to judge improvement.
- **For design intent and constraints:** Read _Limitations and Extensions_ to understand what the system intentionally does not do (learning, rescheduling, calendar integration) and why.
- **For implementation details:** Sections on _Usage_ and _Project Structure_ are secondary and included for completeness rather than as the main contribution.

## Problem Statement

Traditional task scheduling systems prioritize tasks by deadline and priority, ignoring the inherent uncertainty in effort estimation. When tasks consistently overrun their estimates, deadline-driven scheduling leads to cascading failures: tasks scheduled late in the sequence miss their deadlines, creating stress days with over-capacity allocation, and poor overall on-time completion rates.

This system addresses scheduling under **estimation uncertainty** by incorporating:
- **Historical deviation patterns**: Tasks with higher historical overrun factors are treated as riskier
- **Risk-weighted prioritization**: Tasks are ordered by a composite risk score that considers due date proximity, effort magnitude, historical overrun, available slack, and dependency readiness
- **Slack-aware allocation**: The scheduler considers remaining buffer time when making placement decisions

The core value proposition is deterministic, reproducible scheduling logic that can be evaluated offline and provides full observability into decision-making.

## Why Naive Deadline Scheduling Fails

Deadline-first scheduling assumes perfect estimation accuracy. In practice:
1. **Estimation errors compound**: A task estimated at 4 hours that takes 6 hours pushes all subsequent tasks
2. **No risk differentiation**: A 1-hour task due tomorrow with 50% overrun risk is treated the same as a 1-hour task due tomorrow with 10% overrun risk
3. **Slack is ignored**: A task with 10 days of slack is scheduled before a task with 1 day of slack, even if the latter has higher overrun risk
4. **Dependency chains create bottlenecks**: Tasks blocked by dependencies are scheduled late, creating cascading delays

## Architecture Overview

The system consists of four main components:

### 1. Scheduling Engine (`src/engine/`)
The core `Scheduler` class takes a set of tasks, historical outcomes, and a policy, and produces a daily schedule. It:
- Respects daily capacity constraints
- Splits tasks across days when needed
- Enforces dependency ordering
- Generates deterministic, reproducible schedules

### 2. Policy Abstraction (`src/policies/`)
Policies implement the `SchedulingPolicy` interface:
- **BaselinePolicy**: Deadline-first, then priority, then creation time
- **RiskAwarePolicy**: Risk-score-weighted ordering with configurable component weights

New policies can be added by implementing the interface without modifying the engine.

### 3. Observability (`src/models/trace.py`)
Every scheduling run produces a `DecisionTrace` that records:
- Input configuration
- Per-task computed features (due date proximity, effort, overrun factor, slack, dependency readiness)
- Risk score components and final scores (for risk-aware policy)
- All scheduling decisions with reasoning
- Summary statistics (tasks scheduled, splits, crunch days, utilization)

Traces are exported as both human-readable logs and JSON for programmatic analysis.

### 4. Offline Evaluation (`src/evaluation/`)
The evaluation suite:
- Generates deterministic task streams with realistic properties (size distribution, due dates, dependencies, overrun patterns)
- Runs both policies on the same inputs
- Compares metrics: on-time rate, total lateness, crunch days, task splits, schedule churn, average slack
- Performs counterfactual analysis to identify cases where risk-aware scheduling prevented misses or caused unnecessary early scheduling

## Risk Score Components

The risk-aware policy computes a composite risk score from five normalized components (0-1 scale, higher = riskier):

1. **Due Proximity** (weight: 0.3): `1.0 - (days_until_due / 30.0)`, clamped to [0, 1]
   - Tasks closer to their deadline have higher risk

2. **Effort** (weight: 0.2): `min(1.0, estimated_minutes / 480)`
   - Larger tasks have higher risk of overrun

3. **Overrun** (weight: 0.3): `max(0.0, min(1.0, (historical_overrun_factor - 1.0)))`
   - Tasks with higher historical overrun factors are riskier

4. **Slack** (weight: 0.1): `max(0.0, min(1.0, (7.0 - slack_days) / 14.0))`
   - Negative or low slack indicates higher risk

5. **Dependencies** (weight: 0.1): `1.0` if dependencies not ready, `0.0` otherwise
   - Unready dependencies block scheduling and increase risk

The final risk score is the weighted sum. Tasks are ordered by risk score (highest first), then by deadline, then by priority.

## Evaluation Methodology

The evaluation suite uses deterministic simulation:

1. **Task Generation**: Creates a configurable number of tasks with:
   - Varied sizes (small: 30-120 min, medium: 120-480 min, large: 480-1440 min)
   - Due dates distributed across a configurable range
   - Some dependency chains (20% of tasks depend on previous tasks)
   - Realistic priority distribution

2. **Outcome Generation**: For each task, generates a historical outcome with:
   - Overrun factor sampled from a normal distribution (configurable mean and std)
   - Completion date that may be after due date if overrun is high

3. **Policy Comparison**: Both policies schedule the same task set, and metrics are computed:
   - **On-time rate**: Percentage of tasks completed by due date
   - **Total lateness**: Sum of minutes past due across all tasks
   - **Crunch days**: Days scheduled above stress threshold (default: 90% capacity)
   - **Task splits**: Number of tasks fragmented across multiple days
   - **Schedule churn**: Day-to-day plan changes (simplified in current implementation)
   - **Average slack**: Mean remaining slack time across tasks

4. **Counterfactual Analysis**: Identifies:
   - Cases where risk-aware prevented a missed deadline (baseline failed, risk-aware succeeded)
   - Cases where risk-aware caused unnecessary early scheduling (baseline succeeded, risk-aware failed)
   - Cases where both policies failed (insufficient capacity, unrealistic estimates, dependency blockage)

## Limitations and Extensions

### Current Limitations
- **Static estimates**: Task estimates are fixed; no learning from outcomes during scheduling
- **No calendar integration**: Working days are simple weekday lists; no holiday or personal calendar support
- **Simplified churn metric**: Multi-day simulation for churn measurement is not fully implemented
- **Deterministic outcomes**: Historical outcomes are generated, not learned from real data
- **No re-scheduling**: The scheduler produces a one-time plan; no dynamic re-planning as tasks complete

### Realistic Extensions (Not Implemented)
1. **Learned estimates**: Update task estimates using Bayesian inference or online learning as outcomes are observed
2. **Calendar integration**: Import working hours from external calendars, respect holidays and time-off
3. **Multi-day simulation**: Full churn measurement by simulating day-by-day execution and re-planning
4. **Real historical data**: Import task outcomes from external systems (Jira, GitHub, etc.)
5. **Adaptive risk weights**: Tune risk component weights using optimization or reinforcement learning
6. **Uncertainty quantification**: Use probabilistic estimates (e.g., PERT-style min/mode/max) instead of point estimates
7. **Constraint relaxation**: When no feasible schedule exists, suggest which constraints to relax (extend deadline, reduce scope, increase capacity)

## Usage

### Prerequisites
```bash
pip install -r requirements.txt
```

### Configuration
Edit `config.yaml` to adjust:
- Planning horizon (default: 14 days)
- Daily capacity (default: 480 minutes = 8 hours)
- Working days (default: Monday-Friday)
- Risk score weights
- Evaluation parameters (task count, overrun distribution, etc.)

### Generate Tasks
```bash
python main.py generate-tasks --config config.yaml
```
Generates a task set and saves to `results/generated_tasks.json`.

### Run Scheduling
```bash
# Risk-aware policy (default)
python main.py schedule --config config.yaml --policy risk-aware

# Baseline policy
python main.py schedule --config config.yaml --policy baseline
```
Produces a schedule and saves:
- `results/trace_<run_id>.json`: Machine-readable trace
- `results/trace_<run_id>.log`: Human-readable log

### Run Evaluation
```bash
python main.py evaluate --config config.yaml
```
Runs both policies on the same task set and produces:
- `results/evaluation_results.json`: Comparison metrics
- `results/trace_baseline_<run_id>.json`: Baseline trace
- `results/trace_risk-aware_<run_id>.json`: Risk-aware trace
- `results/counterfactual_analysis.json`: Counterfactual analysis

The evaluation results are also printed to stdout.

## Project Structure

```
.
├── src/
│   ├── models/
│   │   ├── __init__.py
│   │   ├── task.py          # Task and TaskOutcome models
│   │   └── trace.py         # DecisionTrace models
│   ├── policies/
│   │   ├── __init__.py
│   │   ├── base.py          # SchedulingPolicy interface
│   │   ├── baseline.py      # Baseline deadline-first policy
│   │   └── risk_aware.py    # Risk-aware policy
│   ├── engine/
│   │   ├── __init__.py
│   │   └── scheduler.py     # Core scheduling engine
│   ├── evaluation/
│   │   ├── __init__.py
│   │   ├── generator.py     # Task and outcome generator
│   │   ├── evaluator.py     # Evaluation suite
│   │   └── counterfactual.py # Counterfactual analysis
│   └── utils/
│       ├── __init__.py
│       ├── config.py        # Configuration loading
│       └── datetime_utils.py # Date utilities
├── results/                 # Generated outputs (created at runtime)
├── config.yaml              # Configuration file
├── requirements.txt         # Python dependencies
├── main.py                  # Entry point
└── README.md                # This file
```

## Example Output

After running evaluation, you'll see output like:

```
======================================================================
EVALUATION RESULTS COMPARISON
======================================================================

Metric                                    Baseline        Risk-Aware    
----------------------------------------------------------------------
On-time rate (%)                          65.00           78.00        
Total lateness (minutes)                  1250            680           
Crunch days                               8               4             
Task splits                               12              15            
Average slack (days)                      2.50            1.80          

======================================================================
```

This shows that risk-aware scheduling improved on-time rate by 13 percentage points and reduced total lateness by 570 minutes, at the cost of slightly more task splits (due to earlier scheduling of risky tasks).

## License
This project is released under the MIT License. See the LICENSE file for details.
Provided for research, educational, and demonstration purposes, without warranty of any kind.
