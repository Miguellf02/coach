"""Pure functions. All arithmetic lives here, never in the LLM.

No I/O, no globals: everything is a function of its inputs, so it is trivial to test.
"""

import datetime as dt
import re

from coach.models import Activity, BlockedActivity, WeeklyLoadResult, WeekSummary
from coach.sources import RawActivity

_ISO_WEEK = re.compile(r"^(\d{4})-W(\d{2})$")


def parse_iso_week(week: str) -> dt.date:
    """'2026-W42' -> Monday of that week. Raises ValueError on bad input."""
    match = _ISO_WEEK.match(week)
    if not match:
        raise ValueError(f"Invalid ISO week {week!r}; expected format like '2026-W42'.")
    year, num = int(match.group(1)), int(match.group(2))
    return dt.date.fromisocalendar(year, num, 1)  # also raises ValueError for W54 etc.


def iso_week_label(day: dt.date) -> str:
    year, week, _ = day.isocalendar()
    return f"{year}-W{week:02d}"


def format_pace(sec_per_km: float) -> str:
    total = round(sec_per_km)
    return f"{total // 60}:{total % 60:02d}"


def estimate_load(distance_km: float, moving_time_s: float, threshold_pace_s: float) -> float:
    """rTSS-like load from pace alone (no HR needed): hours x intensity^2 x 100.

    intensity = threshold pace / actual pace, so one hour at threshold pace = 100.
    """
    if distance_km <= 0 or moving_time_s <= 0:
        return 0.0
    pace_s = moving_time_s / distance_km
    intensity = threshold_pace_s / pace_s
    return round((moving_time_s / 3600) * intensity**2 * 100, 1)


def normalise(raw: RawActivity, threshold_pace_s: float) -> Activity:
    distance_km = raw.distance_m / 1000
    pace_s = raw.moving_time_s / distance_km if distance_km > 0 else 0.0
    return Activity(
        id=raw.id,
        date=raw.date,
        name=raw.name,
        distance_km=round(distance_km, 2),
        moving_time_min=round(raw.moving_time_s / 60, 1),
        pace_min_per_km=format_pace(pace_s) if pace_s else "n/a",
        avg_heart_rate_bpm=round(raw.average_heartrate) if raw.average_heartrate else None,
        est_load=estimate_load(distance_km, raw.moving_time_s, threshold_pace_s),
    )


def summarise_week(
    monday: dt.date, activities: list[Activity], blocked: list[BlockedActivity]
) -> WeekSummary:
    sunday = monday + dt.timedelta(days=6)
    in_week = [a for a in activities if monday <= a.date <= sunday]
    return WeekSummary(
        week=iso_week_label(monday),
        start=monday,
        end=sunday,
        runs=len(in_week),
        distance_km=round(sum(a.distance_km for a in in_week), 2),
        moving_time_h=round(sum(a.moving_time_min for a in in_week) / 60, 2),
        longest_run_km=max((a.distance_km for a in in_week), default=0.0),
        est_load=round(sum(a.est_load for a in in_week), 1),
        blocked_activities=sum(monday <= b.date <= sunday for b in blocked),
    )


def weekly_load(
    activities: list[Activity],
    blocked: list[BlockedActivity],
    target_monday: dt.date,
    n_weeks: int,
) -> WeeklyLoadResult:
    """Summaries for the target week and the (n_weeks - 1) weeks before it, oldest first.

    Blocked activities exist but are unreadable, so a week containing one is never treated
    as a 0 km week, and the % change is withheld while any week undercounts.
    """
    mondays = [target_monday - dt.timedelta(weeks=i) for i in reversed(range(n_weeks))]
    weeks = [summarise_week(m, activities, blocked) for m in mondays]
    data_complete = all(w.blocked_activities == 0 for w in weeks)

    target, prior = weeks[-1], weeks[:-1]
    prior_avg = sum(w.distance_km for w in prior) / len(prior) if prior else 0.0
    change = (
        round((target.distance_km - prior_avg) / prior_avg * 100, 1)
        if data_complete and prior_avg > 0
        else None
    )

    streak = 0
    for w in reversed(weeks):
        if w.distance_km > 0 or w.blocked_activities > 0:
            break
        streak += 1

    return WeeklyLoadResult(
        weeks=weeks,
        target_week=target.week,
        change_vs_prior_avg_pct=change,
        zero_weeks_streak=streak,
        data_complete=data_complete,
    )
