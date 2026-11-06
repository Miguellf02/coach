"""Settings, read once from environment variables (or a local .env file)."""

from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="COACH_", env_file=".env", extra="ignore")

    intervals_api_key: SecretStr | None = Field(
        default=None, description="Intervals.icu API key. Not needed in fixtures mode."
    )
    intervals_athlete_id: str = Field(default="0", description="'0' means the key's owner.")
    fixtures_path: Path | None = Field(
        default=None, description="If set, read activities from this JSON file instead of the API."
    )
    goal_path: Path = Field(default=Path("data/goal.json"))
    threshold_pace_sec_per_km: float = Field(
        default=310.0, gt=0, description="Threshold pace used for the load estimate (5:10/km)."
    )
    max_range_days: int = Field(default=31, gt=0)
