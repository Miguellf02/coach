"""Pure functions. All arithmetic lives here, never in the LLM.

No I/O, no globals: everything is a function of its inputs, so it is trivial to test.
"""

import datetime as dt
import re

from coach.models import (
    Activity,
    BlockedActivity,
    Flag,
    LoadPolicy,
    WeeklyLoadResult,
    WeekSummary,
)
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


def load_flags(
    change_pct: float | None,
    zero_weeks_streak: int,
    data_complete: bool,
    target_missing_hr: bool,
    policy: LoadPolicy,
) -> list[Flag]:
    """Deterministic flags for the target week, in a fixed order."""
    flags: list[Flag] = []
    if change_pct is not None and change_pct > policy.spike_threshold_pct:
        flags.append("load_spike")
    if zero_weeks_streak >= policy.layoff_min_zero_weeks:
        flags.append("layoff")
    if not data_complete:
        flags.append("incomplete_data")
    if target_missing_hr:
        flags.append("missing_hr")
    return flags


def next_week_ceiling_km(
    weeks: list[WeekSummary], flags: list[Flag], policy: LoadPolicy
) -> float | None:
    """Ceiling for next week's distance.

    Recent average = mean distance of the trend window (target included).
    - Incomplete data: None (the totals undercount, so any ceiling would be wrong).
    - After a load_spike or a layoff: the recent average, no increase.
    - Otherwise: max(recent average, target week) x (1 + max_weekly_increase_pct / 100).
      The max() keeps a week that follows empty weeks from getting a ceiling below itself.
    """
    if "incomplete_data" in flags:
        return None
    recent_avg = sum(w.distance_km for w in weeks) / len(weeks)
    if "load_spike" in flags or "layoff" in flags:
        return round(recent_avg, 1)
    base = max(recent_avg, weeks[-1].distance_km)
    return round(base * (1 + policy.max_weekly_increase_pct / 100), 1)


def weekly_load(
    activities: list[Activity],
    blocked: list[BlockedActivity],
    target_monday: dt.date,
    n_weeks: int,
    policy: LoadPolicy,
) -> WeeklyLoadResult:
    """Summaries for the target week and the (n_weeks - 1) weeks before it, oldest first,
    plus deterministic flags and a ceiling for next week.

    The trend (% change, data_complete, flags, ceiling) always uses a fixed window of
    policy.trend_window_weeks ending at the target, so it does not depend on n_weeks:
    asking for more or fewer weeks only changes how many are listed.

    Blocked activities exist but are unreadable, so a week containing one is never treated
    as a 0 km week, and the % change is withheld while any week undercounts.
    """
    span = max(n_weeks, policy.trend_window_weeks)
    mondays = [target_monday - dt.timedelta(weeks=i) for i in reversed(range(span))]
    all_weeks = [summarise_week(m, activities, blocked) for m in mondays]
    window = all_weeks[-policy.trend_window_weeks :]
    data_complete = all(w.blocked_activities == 0 for w in window)

    target, prior = window[-1], window[:-1]
    prior_avg = sum(w.distance_km for w in prior) / len(prior)
    change = (
        round((target.distance_km - prior_avg) / prior_avg * 100, 1)
        if data_complete and prior_avg > 0
        else None
    )

    streak = 0
    for w in reversed(all_weeks):
        if w.distance_km > 0 or w.blocked_activities > 0:
            break
        streak += 1

    target_sunday = target_monday + dt.timedelta(days=6)
    target_missing_hr = any(
        a.avg_heart_rate_bpm is None for a in activities if target_monday <= a.date <= target_sunday
    )
    flags = load_flags(change, streak, data_complete, target_missing_hr, policy)

    return WeeklyLoadResult(
        weeks=all_weeks[-n_weeks:],
        target_week=target.week,
        change_vs_prior_avg_pct=change,
        zero_weeks_streak=streak,
        data_complete=data_complete,
        flags=flags,
        suggested_max_next_week_km=next_week_ceiling_km(window, flags, policy),
        next_week_start=target_monday + dt.timedelta(weeks=1),
    )
