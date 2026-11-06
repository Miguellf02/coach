"""Where activities come from. Two interchangeable sources behind one Protocol:

- IntervalsSource: the live Intervals.icu REST API.
- FixtureSource:   a frozen JSON file, so tests and evals run offline and reproducibly.
"""

import datetime as dt
import json
from pathlib import Path
from typing import Protocol

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from coach.models import BlockedActivity

INTERVALS_BASE_URL = "https://intervals.icu/api/v1"
RUN_TYPES = frozenset({"Run", "TrailRun", "VirtualRun"})


class SourceError(Exception):
    """A data-source failure whose message is safe and useful to show the agent."""


class RawActivity(BaseModel):
    """The subset of an Intervals.icu activity we use. Unknown fields are ignored."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    id: str
    date: dt.date = Field(validation_alias="start_date_local")
    type: str
    name: str = ""
    distance_m: float = Field(default=0.0, ge=0, validation_alias="distance")
    moving_time_s: float = Field(default=0.0, ge=0, validation_alias="moving_time")
    average_heartrate: float | None = None

    @field_validator("id", mode="before")
    @classmethod
    def _id_to_str(cls, v: object) -> str:
        return str(v)

    @field_validator("date", mode="before")
    @classmethod
    def _datetime_to_date(cls, v: object) -> object:
        # Intervals returns "2026-10-17T21:03:12"; we only need the day.
        return v[:10] if isinstance(v, str) else v


STRAVA_BLOCKED_REASON = (
    "Synced from Strava: Intervals.icu does not expose Strava data through its API, so its "
    "distance and time are unknown. Fix: import the Strava archive into Intervals.icu "
    "instead of syncing from Strava."
)


class FetchResult(BaseModel):
    """Readable runs plus the activities that exist but could not be read."""

    model_config = ConfigDict(frozen=True)

    runs: list[RawActivity]
    blocked: list[BlockedActivity]

    def between(self, start: dt.date, end: dt.date) -> "FetchResult":
        """Only the runs and blocked activities dated within [start, end]."""
        return FetchResult(
            runs=[r for r in self.runs if start <= r.date <= end],
            blocked=[b for b in self.blocked if start <= b.date <= end],
        )


class ActivitySource(Protocol):
    def fetch(self, start: dt.date, end: dt.date) -> FetchResult: ...


def _blocked(rec: dict[str, object]) -> BlockedActivity:
    start_local = rec.get("start_date_local")
    if not isinstance(start_local, str):
        raise SourceError(
            f"Blocked activity {rec.get('id')} has no start_date_local, so it cannot be placed "
            "in a week. Import the Strava archive into Intervals.icu instead of syncing."
        )
    try:
        day = dt.date.fromisoformat(start_local[:10])
    except ValueError as exc:
        raise SourceError(
            f"Blocked activity {rec.get('id')} has an invalid start_date_local {start_local!r}."
        ) from exc
    return BlockedActivity(id=str(rec.get("id")), date=day, reason=STRAVA_BLOCKED_REASON)


def _parse(records: object) -> FetchResult:
    if not isinstance(records, list):
        raise SourceError("Unexpected response: expected a JSON list of activities.")
    runs: list[RawActivity] = []
    blocked: list[BlockedActivity] = []
    for rec in records:
        if not isinstance(rec, dict):
            continue
        rec_type = rec.get("type")
        if "_note" in rec:
            # Intervals blocks activities synced from Strava (Strava API terms). Record it
            # instead of failing, unless the stub says it is not a run (e.g. a ride).
            if rec_type is None or rec_type in RUN_TYPES:
                blocked.append(_blocked(rec))
            continue
        if rec_type not in RUN_TYPES:
            continue
        try:
            runs.append(RawActivity.model_validate(rec))
        except ValidationError as exc:
            raise SourceError(
                f"Malformed activity {rec.get('id')}: {exc.errors()[0]['msg']}"
            ) from exc
    return FetchResult(runs=runs, blocked=blocked)


class FixtureSource:
    def __init__(self, path: Path) -> None:
        self._path = path

    def fetch(self, start: dt.date, end: dt.date) -> FetchResult:
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise SourceError(f"Fixtures file not found: {self._path}") from exc
        records = data["activities"] if isinstance(data, dict) else data
        return _parse(records).between(start, end)


class IntervalsSource:
    def __init__(self, api_key: str, athlete_id: str = "0", timeout_s: float = 15.0) -> None:
        self._client = httpx.Client(
            base_url=INTERVALS_BASE_URL, auth=("API_KEY", api_key), timeout=timeout_s
        )
        self._athlete_id = athlete_id

    def fetch(self, start: dt.date, end: dt.date) -> FetchResult:
        try:
            resp = self._client.get(
                f"/athlete/{self._athlete_id}/activities",
                params={"oldest": start.isoformat(), "newest": end.isoformat()},
            )
        except httpx.HTTPError as exc:
            raise SourceError(f"Could not reach Intervals.icu: {type(exc).__name__}") from exc
        if resp.status_code in (401, 403):
            raise SourceError("Intervals.icu rejected the API key (check COACH_INTERVALS_API_KEY).")
        if resp.is_error:
            raise SourceError(f"Intervals.icu returned HTTP {resp.status_code}.")
        return _parse(resp.json()).between(start, end)
