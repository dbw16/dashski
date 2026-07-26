import json
import os
from collections.abc import AsyncGenerator, Callable, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select as sa_select
from sqlmodel import Session, col, select

from dashski import advisory as advisory_view
from dashski import db
from dashski.models import (
    AvalancheAdvisory,
    SourceKind,
    SourceStatus,
    utcnow,
)
from dashski.scheduler import create_scheduler
from dashski.sources.registry import SOURCES

BASE_DIR = Path(__file__).resolve().parent


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
    engine = db.get_engine()
    db.init_db(engine)
    scheduler = None
    if os.environ.get("DASHSKI_SCHEDULER", "1") != "0":
        scheduler = create_scheduler(SOURCES, engine)
        scheduler.start()
    yield
    if scheduler is not None:
        scheduler.shutdown(wait=False)


app = FastAPI(title="Dashski", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")

NZ = ZoneInfo("Pacific/Auckland")
"""Everything is stored as naive UTC and displayed in NZ local time — this is a
South Island dashboard, and mixing zones on one screen invites misreading."""


def _nz(value: datetime, fmt: str = "%a %d %b, %H:%M %Z") -> str:
    return value.replace(tzinfo=UTC).astimezone(NZ).strftime(fmt)


templates.env.filters["nz"] = _nz

SessionDep = Annotated[Session, Depends(db.get_session)]


@dataclass(frozen=True)
class Freshness:
    """What a widget shows about its data's age; stale means don't trust it."""

    label: str
    stale: bool


def _age_label(delta: timedelta) -> str:
    minutes = int(delta.total_seconds() // 60)
    if minutes < 1:
        return "just now"
    if minutes < 60:
        return f"{minutes}m ago"
    hours = minutes // 60
    if hours < 48:
        return f"{hours}h ago"
    return f"{hours // 24}d ago"


def _freshness(statuses: Sequence[SourceStatus]) -> Freshness:
    failed = [s for s in statuses if s.last_error]
    successes = [s.last_success_at for s in statuses if s.last_success_at is not None]
    if not successes:
        if failed:
            return Freshness(f"no data — last fetch failed ({failed[0].last_error})", stale=True)
        return Freshness("no data yet", stale=True)
    label = f"updated {_age_label(utcnow() - max(successes))}"
    if failed:
        return Freshness(f"{label} — stale, last fetch failed", stale=True)
    return Freshness(label, stale=False)


def _statuses(session: Session, kind: SourceKind) -> Sequence[SourceStatus]:
    return session.exec(select(SourceStatus).where(col(SourceStatus.kind) == kind)).all()


_HISTORY_SCAN_LIMIT = 500
"""Rows scanned per widget before dedup. Readings are append-only (ADR 0004),
so a long-polled field accumulates history; this bounds the scan without
needing a window-function query for so few distinct fields/stations."""


def _latest_by_identity[T](
    readings: Sequence[T], identity: Callable[[T], tuple[str, str]]
) -> list[T]:
    """Collapse append-only history to one row per (source_id, domain field).

    `readings` must already be ordered newest-fetched-first, so the first row
    seen per identity is the one kept (see ADR 0007).
    """
    latest: dict[tuple[str, str], T] = {}
    for reading in readings:
        latest.setdefault(identity(reading), reading)
    return list(latest.values())


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "index.html", {})


def _parse_as_of(as_of: str | None) -> datetime | None:
    """Empty string (an unset hx-include field) and missing both mean Live."""
    return datetime.fromisoformat(as_of) if as_of else None


def _band_history(
    session: Session, as_of: datetime | None, now: datetime
) -> dict[str, list[advisory_view.BandReading]]:
    """Band ratings issued within the history window, grouped by region.

    Five columns rather than whole advisories: the strip spans 30 days across
    every region, and the prose fields average ~1.7KB a row, so loading them to
    render 1440 integers would make each poll megabytes. That is also why this
    goes through SQLAlchemy's `select` — SQLModel's is typed only to four
    columns. Bounded by `issued_at`, which the strip buckets on; a local day
    starts up to 13h before the UTC cutoff, so the window is wide enough.
    """
    query = sa_select(
        col(AvalancheAdvisory.region),
        col(AvalancheAdvisory.issued_at),
        col(AvalancheAdvisory.danger_high_alpine),
        col(AvalancheAdvisory.danger_alpine),
        col(AvalancheAdvisory.danger_sub_alpine),
    ).where(col(AvalancheAdvisory.issued_at) >= now - advisory_view.HISTORY_WINDOW)
    if as_of is not None:
        query = query.where(col(AvalancheAdvisory.issued_at) <= as_of)

    history: dict[str, list[advisory_view.BandReading]] = {}
    for region, issued_at, high_alpine, alpine, sub_alpine in session.execute(query).all():
        reading = advisory_view.BandReading(issued_at, (high_alpine, alpine, sub_alpine))
        history.setdefault(region, []).append(reading)
    return history


@app.get("/api/widget/advisory", response_class=HTMLResponse)
def widget_advisory(
    request: Request, session: SessionDep, as_of: str | None = None
) -> HTMLResponse:
    as_of_dt = _parse_as_of(as_of)
    query = select(AvalancheAdvisory).order_by(
        col(AvalancheAdvisory.issued_at).desc(), col(AvalancheAdvisory.fetched_at).desc()
    )
    if as_of_dt is not None:
        query = query.where(col(AvalancheAdvisory.issued_at) <= as_of_dt)
    recent = session.exec(query.limit(_HISTORY_SCAN_LIMIT)).all()

    # The same publication can be stored twice — live and backfilled rows differ on
    # the confidence fields (ADR 0017) — so the fetched_at tiebreak above picks the
    # live row, which carries more data.
    latest = _latest_by_identity(recent, lambda a: (a.source_id, a.region))
    now = as_of_dt or utcnow()
    rows = advisory_view.build_rows(
        latest, now, history=_band_history(session, as_of_dt, now), tz=NZ
    )

    context: dict[str, object] = {
        "rows": rows,
        "as_of": as_of_dt,
        "aspect_wedges": advisory_view.ASPECT_WEDGES,
    }
    if as_of_dt is None:
        context["freshness"] = _freshness(_statuses(session, SourceKind.ADVISORY))
    return templates.TemplateResponse(request, "_widget_advisory.html", context)


def _snapshot_times(session: Session) -> list[datetime]:
    """Every distinct moment a forecaster published or edited an advisory (ADR 0018)."""
    return sorted(set(session.exec(select(AvalancheAdvisory.issued_at)).all()))


@app.get("/api/snapshots", response_class=HTMLResponse)
def snapshots(request: Request, session: SessionDep) -> HTMLResponse:
    times = _snapshot_times(session)
    return templates.TemplateResponse(
        request,
        "_asof_slider.html",
        {"snapshots": times, "snapshots_json": json.dumps([t.isoformat() for t in times])},
    )
