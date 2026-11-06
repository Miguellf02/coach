"""The MCP server: two read-only tools and one resource. Nothing else.

- get_activities   (tool)     -> individual runs in a date range
- get_weekly_load  (tool)     -> weekly totals + trend, computed in code
- coach://goal     (resource) -> the target race; static data, so a resource, not a tool
"""

import datetime as dt
import json
from typing import Annotated

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field

from coach.analytics import normalise, parse_iso_week, weekly_load
from coach.config import Settings
from coach.models import ActivitiesResult, Goal, WeeklyLoadResult
from coach.sources import ActivitySource, FixtureSource, IntervalsSource, SourceError

READ_ONLY = ToolAnnotations(read_only_hint=True, destructive_hint=False, idempotent_hint=True)

INSTRUCTIONS = """\
Read-only access to one runner's training data (running only).
All numbers are pre-computed: never re-add distances or recompute loads yourself.
Heart rate may be missing; say so instead of estimating it.
Use get_weekly_load for "how was my week"; use get_activities only to inspect specific runs.
Some activities may be blocked (exist but unreadable): report them, never treat them as rest.
"""


def build_server(settings: Settings, source: ActivitySource, today: dt.date) -> MCPServer:
    mcp = MCPServer(name="coach", instructions=INSTRUCTIONS)
    threshold = settings.threshold_pace_sec_per_km

    @mcp.tool(annotations=READ_ONLY)
    def get_activities(
        start: Annotated[dt.date, Field(description="First day, inclusive (YYYY-MM-DD).")],
        end: Annotated[dt.date, Field(description="Last day, inclusive (YYYY-MM-DD).")],
    ) -> ActivitiesResult:
        """List individual runs between two dates: distance (km), time (min), pace (m:ss/km),
        heart rate (often null) and estimated load. Use it to inspect specific sessions;
        for weekly totals or trends use get_weekly_load instead. Max range: 31 days."""
        if end < start:
            raise ToolError(f"'end' ({end}) is before 'start' ({start}). Swap them.")
        span = (end - start).days + 1
        if span > settings.max_range_days:
            raise ToolError(
                f"Range is {span} days; max is {settings.max_range_days}. "
                "Narrow it, or use get_weekly_load for longer trends."
            )
        try:
            fetched = source.fetch(start, end)
        except SourceError as exc:
            raise ToolError(str(exc)) from exc
        runs = sorted((normalise(r, threshold) for r in fetched.runs), key=lambda a: a.date)
        return ActivitiesResult(
            start=start,
            end=end,
            count=len(runs),
            activities=runs,
            missing_heart_rate=sum(a.avg_heart_rate_bpm is None for a in runs),
            blocked=sorted(fetched.blocked, key=lambda b: b.date),
        )

    @mcp.tool(annotations=READ_ONLY)
    def get_weekly_load(
        week: Annotated[
            str, Field(description="Target ISO week, e.g. '2026-W42' (weeks run Mon-Sun).")
        ],
        n_weeks: Annotated[
            int,
            Field(ge=1, le=12, description="How many weeks to return, ending at the target."),
        ] = 4,
    ) -> WeeklyLoadResult:
        """Weekly running totals (km, hours, runs, longest run, estimated load) for the target
        week and the weeks before it, oldest first. Also returns the % change vs the previous
        weeks' average and how many consecutive 0 km weeks end at the target week.
        Weeks with blocked (unreadable) activities undercount and set data_complete=false.
        This is the main tool for 'how was my week' and for planning the next one."""
        try:
            target_monday = parse_iso_week(week)
        except ValueError as exc:
            raise ToolError(str(exc)) from exc
        first_monday = target_monday - dt.timedelta(weeks=n_weeks - 1)
        try:
            fetched = source.fetch(first_monday, target_monday + dt.timedelta(days=6))
        except SourceError as exc:
            raise ToolError(str(exc)) from exc
        runs = [normalise(r, threshold) for r in fetched.runs]
        return weekly_load(runs, fetched.blocked, target_monday, n_weeks)

    @mcp.resource("coach://goal", mime_type="application/json")
    def goal() -> str:
        """The target race (name, date, distance, target time) and days left until it."""
        data = json.loads(settings.goal_path.read_text(encoding="utf-8"))
        race_date = dt.date.fromisoformat(data["race_date"])
        return Goal(**data, days_to_race=(race_date - today).days).model_dump_json()

    return mcp


def make_source(settings: Settings) -> ActivitySource:
    if settings.fixtures_path is not None:
        return FixtureSource(settings.fixtures_path)
    if settings.intervals_api_key is None:
        raise SystemExit(
            "Set COACH_INTERVALS_API_KEY for live data, or COACH_FIXTURES_PATH for offline mode."
        )
    return IntervalsSource(
        settings.intervals_api_key.get_secret_value(), settings.intervals_athlete_id
    )


def main() -> None:
    settings = Settings()
    build_server(settings, make_source(settings), dt.date.today()).run("stdio")


if __name__ == "__main__":
    main()
