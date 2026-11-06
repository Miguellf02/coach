"""Domain models: the only shapes the agent ever sees.

Every unit is in the field name or description, so the model never has to guess
whether a number is metres or kilometres, seconds or minutes.
"""

import datetime as dt

from pydantic import BaseModel, ConfigDict, Field


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Activity(_Frozen):
    """One run, normalised from the data source."""

    id: str
    date: dt.date
    name: str
    distance_km: float = Field(ge=0)
    moving_time_min: float = Field(ge=0)
    pace_min_per_km: str = Field(description="Average pace formatted as m:ss, e.g. '5:18'.")
    avg_heart_rate_bpm: int | None = Field(
        default=None, description="Null when the run was recorded without a HR sensor."
    )
    est_load: float = Field(
        ge=0, description="Pace-based training load (rTSS-like): 100 = one hour at threshold."
    )


class BlockedActivity(_Frozen):
    """An activity that exists in the source but whose data cannot be read."""

    id: str
    date: dt.date
    reason: str = Field(description="Why it is unreadable and how the runner can fix it.")


class ActivitiesResult(_Frozen):
    """Output of get_activities."""

    start: dt.date
    end: dt.date
    count: int
    activities: list[Activity]
    missing_heart_rate: int = Field(description="How many activities have no heart-rate data.")
    blocked: list[BlockedActivity] = Field(
        description="Activities that exist but could not be read. Never treat them as rest days."
    )


class WeekSummary(_Frozen):
    """Aggregated load for one ISO week (Monday to Sunday)."""

    week: str = Field(description="ISO week, e.g. '2026-W42'.")
    start: dt.date
    end: dt.date
    runs: int
    distance_km: float
    moving_time_h: float
    longest_run_km: float
    est_load: float
    blocked_activities: int = Field(
        description=(
            "Activities this week that exist but could not be read. If > 0, the totals "
            "undercount: the week is not a rest week."
        )
    )


class WeeklyLoadResult(_Frozen):
    """Output of get_weekly_load: the target week plus the weeks before it, oldest first."""

    weeks: list[WeekSummary]
    target_week: str
    change_vs_prior_avg_pct: float | None = Field(
        description=(
            "Distance change of the target week vs the average of the previous weeks, in %. "
            "Null when the previous weeks have zero distance (change is undefined) or when "
            "data_complete is false (the totals undercount)."
        )
    )
    zero_weeks_streak: int = Field(
        description=(
            "Consecutive weeks with 0 km and no blocked activities, ending at the target week "
            "(0 if it had runs or blocked activities)."
        )
    )
    data_complete: bool = Field(
        description=(
            "False if any returned week has blocked activities: its totals undercount, so do "
            "not read low numbers there as rest."
        )
    )


class Goal(_Frozen):
    """The race the plan is built towards."""

    race: str
    race_date: dt.date
    distance_km: float
    target_time: str | None = None
    days_to_race: int
