"""Month grid builder for HRMS calendar."""

from calendar import monthrange
from datetime import date, timedelta


def build_month_weeks(year: int, month: int, today: date, events_by_day: dict):
    """Return weeks list for template; events_by_day maps day int -> list of event dicts."""
    start = date(year, month, 1)
    last = monthrange(year, month)[1]
    end = date(year, month, last)
    first_weekday = start.weekday()
    day = 1
    week = [None] * first_weekday
    weeks = []
    while day <= last:
        cell_date = date(year, month, day)
        week.append(
            {
                'day': day,
                'events': events_by_day.get(day, []),
                'today': cell_date == today,
            }
        )
        if len(week) == 7:
            weeks.append(week)
            week = []
        day += 1
    if week:
        while len(week) < 7:
            week.append(None)
        weeks.append(week)
    prev_month = (start - timedelta(days=1)).replace(day=1)
    next_month = (end + timedelta(days=1))
    return {
        'year': year,
        'month': month,
        'month_label': start.strftime('%B %Y'),
        'weeks': weeks,
        'prev': {'year': prev_month.year, 'month': prev_month.month},
        'next': {'year': next_month.year, 'month': next_month.month},
        'start': start,
        'end': end,
    }
