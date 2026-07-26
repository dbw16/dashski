"""SQLModel tables: one reading table per source kind (ADR 0004), plus fetch bookkeeping."""

from datetime import UTC, datetime
from enum import StrEnum

from sqlmodel import Field, Relationship, SQLModel


def utcnow() -> datetime:
    """Naive UTC now — all datetimes in the DB are naive UTC."""
    return datetime.now(UTC).replace(tzinfo=None)


class SourceKind(StrEnum):
    ADVISORY = "advisory"


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


_BOOKKEEPING_FIELDS = frozenset({"id", "fetched_at", "advisory_id"})
"""Columns recording when and where we stored a row, not what the source said."""


def _field_key(row: SQLModel) -> tuple[object, ...]:
    return tuple(
        (name, getattr(row, name))
        for name in sorted(type(row).model_fields)
        if name not in _BOOKKEEPING_FIELDS
    )


class AvalancheAdvisory(SQLModel, table=True):
    """One region's avalanche advisory for one 24h period, as published by the NZAA.

    Danger ratings are 1-5 (Low..Extreme); negatives are non-ratings, of which
    only -2 "Insufficient snow" has been observed. Elevation bands are fixed at
    three and identified by the payload's array order, never its altitude
    numbers (ADR 0012). Prose fields hold plain text — the source publishes HTML
    and the parser strips it (ADR 0011).
    """

    id: int | None = Field(default=None, primary_key=True)
    source_id: str = Field(foreign_key="sourcestatus.source_id", index=True)
    fetched_at: datetime
    region: str
    issued_at: datetime
    valid_period: str | None = None
    forecaster: str | None = None
    danger_high_alpine: int | None = None
    danger_alpine: int | None = None
    danger_sub_alpine: int | None = None
    confidence_level: str | None = None
    confidence_reasons: str | None = None
    important_info: str | None = None
    recent_activity: str | None = None
    snowpack: str | None = None
    mountain_weather: str | None = None
    sliding_danger: str | None = None

    problems: list[AvalancheProblem] = Relationship(
        back_populates="advisory",
        sa_relationship_kwargs={"order_by": "AvalancheProblem.priority_level"},
    )

    def content_key(self) -> object:
        """Everything the advisory says, minus when we fetched it (ADR 0016).

        Two advisories with equal keys are the same publication refetched, so
        storing the second one would add a Snapshot showing nothing new.
        """
        return (_field_key(self), tuple(sorted(map(_field_key, self.problems), key=repr)))


class AvalancheProblem(SQLModel, table=True):
    """One avalanche problem within an advisory — the "what and where" of the danger.

    Aspect columns hold the compass aspects the problem applies to at that
    elevation band, comma-joined (e.g. "N,NE,E"). The source encodes them as
    object keys whose values are always 0, so presence is the signal (ADR 0012).
    """

    id: int | None = Field(default=None, primary_key=True)
    advisory_id: int | None = Field(default=None, foreign_key="avalancheadvisory.id", index=True)
    priority: str | None = None
    priority_level: int | None = None
    character: str
    likelihood: int | None = None
    size: float | None = None  # destructive size, reported in half steps (D1, D1.5, …)
    trend: str | None = None
    aspects_high_alpine: str | None = None
    aspects_alpine: str | None = None
    aspects_sub_alpine: str | None = None
    description: str | None = None

    advisory: AvalancheAdvisory | None = Relationship(back_populates="problems")


type Reading = AvalancheAdvisory
"""What a source's parse() yields. A union again if a second kind is ever added (ADR 0015)."""
