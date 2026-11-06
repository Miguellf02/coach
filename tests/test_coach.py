"""Tests run fully offline against data/fixtures.json (real runs, frozen)."""

import datetime as dt
import json
from pathlib import Path
from typing import Any

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from coach.analytics import estimate_load, format_pace, parse_iso_week, weekly_load
from coach.config import Settings
from coach.models import Activity, BlockedActivity
from coach.server import build_server
from coach.sources import FixtureSource, _parse

ROOT = Path(__file__).resolve().parents[1]
TODAY = dt.date(2026, 11, 6)


@pytest.fixture
def server() -> Any:
    settings = Settings(
        fixtures_path=ROOT / "data/fixtures.json",
        goal_path=ROOT / "data/goal.json",
        _env_file=None,  # type: ignore[call-arg]
    )
    return build_server(settings, FixtureSource(settings.fixtures_path), TODAY)  # type: ignore[arg-type]


async def call(server: Any, tool: str, **args: Any) -> dict[str, Any]:
    result = await server.call_tool(tool, args)
    structured = result.structured_content
    assert structured is not None
    return dict(structured)


# --- pure functions ---------------------------------------------------------


def test_one_hour_at_threshold_is_100() -> None:
    assert estimate_load(distance_km=3600 / 310, moving_time_s=3600, threshold_pace_s=310) == 100.0


def test_format_pace() -> None:
    assert format_pace(318.5) == "5:18"


def test_bad_iso_week_raises() -> None:
    with pytest.raises(ValueError):
        parse_iso_week("2026-42")


def test_strava_stub_is_blocked_not_fatal() -> None:
    records = [
        {
            "id": "1",
            "start_date_local": "2026-10-13T00:00:00",
            "type": "Run",
            "distance": 5000,
            "moving_time": 1500,
        },
        {
            "id": "2",
            "start_date_local": "2026-10-17T21:03:12",
            "source": "STRAVA",
            "_note": "STRAVA activities are not available via the API",
        },
    ]
    result = _parse(records)
    assert [r.id for r in result.runs] == ["1"]
    assert [(b.id, b.date) for b in result.blocked] == [("2", dt.date(2026, 10, 17))]
    assert "import the Strava archive" in result.blocked[0].reason


def test_week_with_only_a_blocked_activity_is_not_rest() -> None:
    # W41 has a readable run; W42 (the target) only has a blocked, unreadable one.
    prior_run = Activity(
        id="1",
        date=dt.date(2026, 10, 7),
        name="Easy",
        distance_km=8.0,
        moving_time_min=44.0,
        pace_min_per_km="5:30",
        est_load=50.0,
    )
    blocked = [BlockedActivity(id="2", date=dt.date(2026, 10, 17), reason="Strava")]
    out = weekly_load([prior_run], blocked, target_monday=dt.date(2026, 10, 12), n_weeks=2)
    assert out.weeks[-1].blocked_activities == 1
    assert out.data_complete is False
    assert out.zero_weeks_streak == 0
    assert out.change_vs_prior_avg_pct is None  # would otherwise be a fake -100 %


# --- the four eval weeks, at tool level ------------------------------------


@pytest.mark.anyio
async def test_race_week_is_a_spike(server: Any) -> None:
    out = await call(server, "get_weekly_load", week="2026-W42", n_weeks=4)
    target = out["weeks"][-1]
    assert target["distance_km"] == 24.8
    assert target["longest_run_km"] == 22.0
    assert out["change_vs_prior_avg_pct"] is not None
    assert out["change_vs_prior_avg_pct"] > 300  # 24.8 km vs ~4.3 km/week before


@pytest.mark.anyio
async def test_layoff_counts_zero_weeks(server: Any) -> None:
    out = await call(server, "get_weekly_load", week="2026-W45", n_weeks=4)
    assert out["zero_weeks_streak"] == 3
    assert out["weeks"][0]["week"] == "2026-W42"


@pytest.mark.anyio
async def test_activities_flag_missing_heart_rate(server: Any) -> None:
    out = await call(server, "get_activities", start="2026-10-12", end="2026-10-18")
    assert out["count"] == 2
    assert out["missing_heart_rate"] == 2
    assert out["activities"][1]["pace_min_per_km"] == "5:05"


@pytest.mark.anyio
async def test_range_too_long_is_rejected(server: Any) -> None:
    # In-process the error is raised; over MCP the protocol returns it as isError=True.
    with pytest.raises(ToolError, match="max is 31"):
        await server.call_tool("get_activities", {"start": "2026-01-01", "end": "2026-06-01"})


@pytest.mark.anyio
async def test_goal_resource_computes_days_to_race(server: Any) -> None:
    contents = await server.read_resource("coach://goal")
    goal = json.loads(contents[0].content)
    assert goal["days_to_race"] == (dt.date(2027, 4, 25) - TODAY).days


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
