"""SQLModel tables: one reading table per source kind (ADR 0004), plus fetch bookkeeping."""

from datetime import UTC, datetime
from enum import StrEnum

from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    """Naive UTC now — all datetimes in the DB are naive UTC."""
    return datetime.now(UTC).replace(tzinfo=None)


class SourceKind(StrEnum):
    FORECAST = "forecast"
    OBSERVATION = "observation"
    SNOW_REPORT = "snow_report"


class SourceStatus(SQLModel, table=True):
    """Latest fetch state per source; drives widget freshness/staleness."""

    source_id: str = Field(primary_key=True)
    kind: SourceKind
    last_attempt_at: datetime | None = None
    last_success_at: datetime | None = None
    last_error: str | None = None


class FetchRun(SQLModel, table=True):
    """One scheduled fetch attempt, success or failure. Append-only history."""

    id: int | None = Field(default=None, primary_key=True)
    source_id: str = Field(foreign_key="sourcestatus.source_id", index=True)
    started_at: datetime
    finished_at: datetime
    success: bool
    error: str | None = None


class RawFetch(SQLModel, table=True):
    """Most recent unparsed payload per source. Latest only, by design (ADR 0004)."""

    source_id: str = Field(primary_key=True, foreign_key="sourcestatus.source_id")
    fetched_at: datetime
    http_status: int | None = None
    payload: str


class ForecastReading(SQLModel, table=True):
    """Predicted weather for a location, as fetched from a forecast source."""

    id: int | None = Field(default=None, primary_key=True)
    source_id: str = Field(foreign_key="sourcestatus.source_id", index=True)
    fetched_at: datetime
    location: str
    forecast_for: datetime
    summary: str | None = None
    temp_high_c: float | None = None
    temp_low_c: float | None = None
    wind_kmh: float | None = None
    precip_mm: float | None = None
    snow_level_m: float | None = None


class ObservationReading(SQLModel, table=True):
    """Measured weather from a station — what actually happened."""

    id: int | None = Field(default=None, primary_key=True)
    source_id: str = Field(foreign_key="sourcestatus.source_id", index=True)
    fetched_at: datetime
    station: str
    observed_at: datetime
    temp_c: float | None = None
    wind_kmh: float | None = None
    wind_dir: str | None = None
    precip_mm: float | None = None
    snow_depth_cm: float | None = None


class SnowReport(SQLModel, table=True):
    """A ski field's self-reported conditions."""

    id: int | None = Field(default=None, primary_key=True)
    source_id: str = Field(foreign_key="sourcestatus.source_id", index=True)
    fetched_at: datetime
    ski_field: str
    reported_at: datetime
    base_depth_cm: float | None = None
    new_snow_24h_cm: float | None = None
    new_snow_7d_cm: float | None = None
    lifts_open: int | None = None
    lifts_total: int | None = None
    summary: str | None = None


type Reading = ForecastReading | ObservationReading | SnowReport
