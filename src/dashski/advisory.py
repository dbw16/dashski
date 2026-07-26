"""View layer for the avalanche advisory widget: danger labels, expiry, aspect roses.

Kept out of main.py because an advisory carries considerably more presentation
logic than the table-shaped widgets do.
"""

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta, tzinfo

from dashski.models import AvalancheAdvisory, AvalancheProblem
from dashski.sources.nzaa_advisory import ASPECT_ORDER, REGIONS, advisory_url

EXPIRES_AFTER = timedelta(hours=24)
"""Advisories carry validPeriod "24hrs", so past that the ratings are history."""

ABSENT_AFTER = timedelta(days=7)
"""Beyond a week there is no season on — showing danger ratings would mislead."""

HISTORY_DAYS = 30
HISTORY_WINDOW = timedelta(days=HISTORY_DAYS)
"""How far back the per-region danger strip reaches. Also bounds the query that
feeds it, so the two cannot drift apart."""

DANGER_LABELS = {1: "Low", 2: "Moderate", 3: "Considerable", 4: "High", 5: "Extreme"}
NON_RATING_LABELS = {-2: "Insufficient snow"}

BAND_LABELS = ("High Alpine", "Alpine", "Sub-Alpine")
BAND_SHORT = ("HA", "AL", "SA")
"""Abbreviations for the collapsed one-line summary, where the full labels don't fit."""

_ASPECT_FIELDS = ("aspects_high_alpine", "aspects_alpine", "aspects_sub_alpine")

_ROSE_CENTRE, _ROSE_OUTER, _ROSE_INNER = 16.0, 15.0, 6.5


def _rose_wedge(index: int) -> str:
    """SVG path for one 45° segment of the aspect rose, in a 32x32 viewBox."""

    def point(radius: float, degrees: float) -> str:
        angle = math.radians(degrees - 90)  # 0° points up, not right
        x = _ROSE_CENTRE + radius * math.cos(angle)
        y = _ROSE_CENTRE + radius * math.sin(angle)
        return f"{x:.2f} {y:.2f}"

    start, end = index * 45 - 22.5, index * 45 + 22.5
    return (
        f"M {point(_ROSE_INNER, start)} L {point(_ROSE_OUTER, start)} "
        f"A {_ROSE_OUTER} {_ROSE_OUTER} 0 0 1 {point(_ROSE_OUTER, end)} "
        f"L {point(_ROSE_INNER, end)} "
        f"A {_ROSE_INNER} {_ROSE_INNER} 0 0 0 {point(_ROSE_INNER, start)} Z"
    )


ASPECT_WEDGES = {aspect: _rose_wedge(i) for i, aspect in enumerate(ASPECT_ORDER)}
"""Aspect rose geometry, keyed by compass aspect and drawn clockwise from north."""


@dataclass(frozen=True)
class DangerBand:
    """One elevation band's danger rating, ready to render."""

    label: str
    short: str
    rating: int | None
    name: str
    tone: str
    """CSS token: "1".."5" for real ratings, "none" for insufficient snow / unrated."""


@dataclass(frozen=True)
class ProblemRow:
    """An avalanche problem plus the aspect set its rose should shade."""

    problem: AvalancheProblem
    aspects: frozenset[str]
    aspect_detail: str
    size_label: str | None


@dataclass(frozen=True)
class BandReading:
    """The three band ratings one advisory published, and when it was issued.

    All the danger strip needs from an advisory. Kept separate from
    `AvalancheAdvisory` so the strip's query can skip the prose columns.
    """

    issued_at: datetime
    ratings: tuple[int | None, int | None, int | None]


@dataclass(frozen=True)
class HistoryCell:
    """One elevation band's rating on one day of the strip."""

    label: str
    """The day, e.g. "Tue 14 Jul" — the cell's tooltip and accessible name."""
    rating: int | None
    name: str
    tone: str
    """CSS token: "1".."5", "none" for a non-rating, "empty" for no advisory."""


@dataclass(frozen=True)
class HistoryRow:
    """One elevation band's run of daily cells, oldest first."""

    label: str
    short: str
    cells: tuple[HistoryCell, ...]


@dataclass(frozen=True)
class History:
    """A region's last 30 days of danger ratings, as three aligned day strips."""

    rows: tuple[HistoryRow, ...]
    ticks: tuple[str, ...]
    """Three date labels — start, middle, end — under the strip."""
    days: int


@dataclass(frozen=True)
class AdvisoryRow:
    """One region's advisory as the widget presents it."""

    advisory: AvalancheAdvisory
    bands: tuple[DangerBand, ...]
    problems: tuple[ProblemRow, ...]
    url: str
    expired: bool
    absent: bool
    """True when the newest advisory predates the viewing time by more than a
    week — out of season, so the widget withholds ratings entirely."""
    history: History | None
    """None when no advisory in the window — an all-blank strip says nothing."""


def _band(index: int, rating: int | None) -> DangerBand:
    label, short = BAND_LABELS[index], BAND_SHORT[index]
    if rating in DANGER_LABELS:
        assert rating is not None
        return DangerBand(label, short, rating, DANGER_LABELS[rating], str(rating))
    name = NON_RATING_LABELS.get(rating, "No rating") if rating is not None else "No rating"
    return DangerBand(label, short, rating, name, "none")


def _problem_row(problem: AvalancheProblem) -> ProblemRow:
    aspects: set[str] = set()
    detail: list[str] = []
    for label, field in zip(BAND_LABELS, _ASPECT_FIELDS, strict=True):
        value = getattr(problem, field)
        if value:
            band_aspects = value.split(",")
            aspects.update(band_aspects)
            detail.append(f"{label}: {', '.join(band_aspects)}")
    size = f"D{problem.size:g}" if problem.size else None
    return ProblemRow(problem, frozenset(aspects), " · ".join(detail), size)


def _local_day(moment: datetime, tz: tzinfo) -> date:
    """The calendar day a stored (naive UTC) moment falls on, locally."""
    return moment.replace(tzinfo=UTC).astimezone(tz).date()


def _history_cell(day: date, reading: BandReading | None, index: int) -> HistoryCell:
    label = day.strftime("%a %d %b")
    if reading is None:
        return HistoryCell(label, None, "No advisory", "empty")
    band = _band(index, reading.ratings[index])
    return HistoryCell(label, band.rating, band.name, band.tone)


def build_history(readings: Sequence[BandReading], now: datetime, tz: tzinfo) -> History | None:
    """The 30 days up to `now` as one cell per local day per elevation band.

    Days are local days: an advisory issued at 19:00 NZ belongs to that evening,
    not to the UTC day it rolls into. Where a day carries more than one advisory
    the latest issued wins — that is what a reader that day saw last. Returns
    None when the window holds nothing, so an off-season region renders no strip
    rather than 90 blank cells.
    """
    end = _local_day(now, tz)
    days = [end - timedelta(days=offset) for offset in reversed(range(HISTORY_DAYS))]

    by_day: dict[date, BandReading] = {}
    for reading in sorted(readings, key=lambda r: r.issued_at):
        by_day[_local_day(reading.issued_at, tz)] = reading
    if not by_day.keys() & set(days):
        return None

    return History(
        rows=tuple(
            HistoryRow(
                label=BAND_LABELS[index],
                short=BAND_SHORT[index],
                cells=tuple(_history_cell(day, by_day.get(day), index) for day in days),
            )
            for index in range(len(BAND_LABELS))
        ),
        # No "today" on the right: with the As Of slider the strip's end is
        # wherever the reader is standing, which is not always today.
        ticks=tuple(days[i].strftime("%d %b") for i in (0, len(days) // 2, -1)),
        days=len(days),
    )


def build_rows(
    advisories: Sequence[AvalancheAdvisory],
    now: datetime,
    *,
    history: Mapping[str, Sequence[BandReading]],
    tz: tzinfo,
) -> list[AdvisoryRow]:
    """Order advisories by our region list and classify each against `now`.

    `now` is the As Of position, not wall clock — an advisory that was already a
    week stale at the snapshot being viewed was just as absent then as it looks
    now (ADR 0013).
    """
    by_region = {advisory.region: advisory for advisory in advisories}
    rows = []
    for region in REGIONS:
        advisory = by_region.get(region.name)
        if advisory is None:
            continue
        age = now - advisory.issued_at
        rows.append(
            AdvisoryRow(
                advisory=advisory,
                bands=(
                    _band(0, advisory.danger_high_alpine),
                    _band(1, advisory.danger_alpine),
                    _band(2, advisory.danger_sub_alpine),
                ),
                problems=tuple(_problem_row(p) for p in advisory.problems),
                url=advisory_url(region),
                expired=age > EXPIRES_AFTER,
                absent=age > ABSENT_AFTER,
                history=build_history(history.get(region.name, ()), now, tz),
            )
        )
    return rows
