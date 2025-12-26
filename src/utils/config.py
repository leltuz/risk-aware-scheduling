"""Configuration management."""

import json
import yaml
from pathlib import Path
from typing import Dict, Any


def load_config(config_path: str) -> Dict[str, Any]:
    """Load configuration from YAML or JSON file."""
    path = Path(config_path)
    
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    
    with open(path, 'r') as f:
        if path.suffix.lower() in ['.yaml', '.yml']:
            return yaml.safe_load(f)
        elif path.suffix.lower() == '.json':
            return json.load(f)
        else:
            raise ValueError(f"Unsupported config file format: {path.suffix}")
    
    return {}


def get_default_config() -> Dict[str, Any]:
    """Get default configuration."""
    return {
        'scheduling': {
            'planning_horizon_days': 14,
            'daily_capacity_minutes': 480,
            'working_hours_start': 9,
            'working_hours_end': 17,
            'working_days': [0, 1, 2, 3, 4],  # Monday to Friday
        },
        'risk_weights': {
            'due_proximity': 0.3,
            'effort': 0.2,
            'overrun': 0.3,
            'slack': 0.1,
            'dependencies': 0.1,
        },
        'evaluation': {
            'stress_threshold_percent': 90,
            'task_count': 50,
            'due_date_range_days': 30,
            'overrun_mean': 1.2,
            'overrun_std': 0.3,
        },
        'tie_break': {
            'primary': 'priority',
            'secondary': 'created_at',
        },
    }

