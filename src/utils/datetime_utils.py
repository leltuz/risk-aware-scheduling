"""Date and time utilities."""

from datetime import datetime, timedelta
from typing import List


def get_working_days(start_date: datetime, end_date: datetime, working_days: List[int]) -> List[datetime]:
    """Get list of working days between start and end dates."""
    days = []
    current = start_date.date()
    end = end_date.date()
    
    while current <= end:
        if current.weekday() in working_days:
            days.append(datetime.combine(current, datetime.min.time()))
        current += timedelta(days=1)
    
    return days


def is_working_day(date: datetime, working_days: List[int]) -> bool:
    """Check if a date is a working day."""
    return date.weekday() in working_days

