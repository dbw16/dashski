import json
import os
from collections.abc import AsyncGenerator, Callable, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, col, select

from dashski import db
from dashski.models import (
    ForecastReading,
    ObservationReading,
    SnowReport,
    SourceKind,
    SourceStatus,
    utcnow,
)
from dashski.scheduler import create_scheduler, run_source
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

SessionDep = Annotated[Session, Depends(db.get_session)]


def _now() -> str:
    return datetime.now(UTC).strftime("%H:%M:%S UTC")


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


@app.get("/api/widget/forecast", response_class=HTMLResponse)
def widget_forecast(request: Request, session: SessionDep) -> HTMLResponse:
    recent = session.exec(
        select(ForecastReading)
        .order_by(col(ForecastReading.fetched_at).desc())
        .limit(_HISTORY_SCAN_LIMIT)
    ).all()
    readings = _latest_by_identity(recent, lambda r: (r.source_id, r.location))[:20]
    return templates.TemplateResponse(
        request,
        "_widget_forecast.html",
        {"readings": readings, "freshness": _freshness(_statuses(session, SourceKind.FORECAST))},
    )


def _parse_as_of(as_of: str | None) -> datetime | None:
    """Empty string (an unset hx-include field) and missing both mean Live."""
    return datetime.fromisoformat(as_of) if as_of else None


@app.get("/api/widget/observation", response_class=HTMLResponse)
def widget_observation(
    request: Request, session: SessionDep, as_of: str | None = None
) -> HTMLResponse:
    as_of_dt = _parse_as_of(as_of)
    query = select(ObservationReading).order_by(col(ObservationReading.fetched_at).desc())
    if as_of_dt is not None:
        query = query.where(col(ObservationReading.fetched_at) <= as_of_dt)
    recent = session.exec(query.limit(_HISTORY_SCAN_LIMIT)).all()
    readings = _latest_by_identity(recent, lambda r: (r.source_id, r.station))[:20]
    context: dict[str, object] = {"readings": readings, "as_of": as_of_dt}
    if as_of_dt is None:
        context["freshness"] = _freshness(_statuses(session, SourceKind.OBSERVATION))
    return templates.TemplateResponse(request, "_widget_observation.html", context)


_CALC_24H_MIN_GAP = timedelta(hours=18)
_CALC_24H_MAX_GAP = timedelta(hours=30)


@dataclass(frozen=True)
class SnowReportRow:
    """A snow report plus its 24h-snowfall figure and where that figure came from."""

    report: SnowReport
    new_snow_24h_cm: float | None
    new_snow_24h_calculated: bool


def _prior_snow_report(
    session: Session, report: SnowReport, as_of: datetime | None
) -> SnowReport | None:
    """The same field's most recent report strictly before this one — the "yesterday" baseline.

    Bound by the same `as_of` cutoff as the report itself (ADR 0009) — otherwise a frozen
    snapshot could compute its 24h figure from a report that, as of that snapshot, hadn't
    been fetched yet.
    """
    query = (
        select(SnowReport)
        .where(col(SnowReport.source_id) == report.source_id)
        .where(col(SnowReport.ski_field) == report.ski_field)
        .where(col(SnowReport.reported_at) < report.reported_at)
    )
    if as_of is not None:
        query = query.where(col(SnowReport.fetched_at) <= as_of)
    return session.exec(query.order_by(col(SnowReport.reported_at).desc()).limit(1)).first()


def _snow_24h(report: SnowReport, prior: SnowReport | None) -> tuple[float | None, bool]:
    """Direct source figure if present; otherwise a same-field trend estimate (ADR 0008).

    Estimate = today's 7-day total minus the prior report's 7-day total, which
    approximates the newest day's snowfall as it rolls into the 7-day window.
    Only trusted when the prior report is roughly a day old — a stale prior
    report (missed updates) would silently mislabel a multi-day delta as 24h.
    """
    if report.new_snow_24h_cm is not None:
        return report.new_snow_24h_cm, False
    if prior is None or report.new_snow_7d_cm is None or prior.new_snow_7d_cm is None:
        return None, False
    gap = report.reported_at - prior.reported_at
    if not (_CALC_24H_MIN_GAP <= gap <= _CALC_24H_MAX_GAP):
        return None, False
    return max(0.0, report.new_snow_7d_cm - prior.new_snow_7d_cm), True


@app.get("/api/widget/snow-report", response_class=HTMLResponse)
def widget_snow_report(
    request: Request, session: SessionDep, as_of: str | None = None
) -> HTMLResponse:
    as_of_dt = _parse_as_of(as_of)
    query = select(SnowReport).order_by(col(SnowReport.fetched_at).desc())
    if as_of_dt is not None:
        query = query.where(col(SnowReport.fetched_at) <= as_of_dt)
    recent = session.exec(query.limit(_HISTORY_SCAN_LIMIT)).all()
    latest = _latest_by_identity(recent, lambda r: (r.source_id, r.ski_field))[:20]
    rows = []
    for report in latest:
        snow_24h, calculated = _snow_24h(report, _prior_snow_report(session, report, as_of_dt))
        rows.append(
            SnowReportRow(
                report=report, new_snow_24h_cm=snow_24h, new_snow_24h_calculated=calculated
            )
        )
    context: dict[str, object] = {"rows": rows, "as_of": as_of_dt}
    if as_of_dt is None:
        context["freshness"] = _freshness(_statuses(session, SourceKind.SNOW_REPORT))
    return templates.TemplateResponse(request, "_widget_snow_report.html", context)


def _snapshot_times(session: Session) -> list[datetime]:
    """Every distinct moment an As-Of-eligible widget's known state changed (ADR 0010)."""
    snow_times = session.exec(select(SnowReport.fetched_at)).all()
    obs_times = session.exec(select(ObservationReading.fetched_at)).all()
    return sorted({*snow_times, *obs_times})


@app.get("/api/snapshots", response_class=HTMLResponse)
def snapshots(request: Request, session: SessionDep) -> HTMLResponse:
    times = _snapshot_times(session)
    return templates.TemplateResponse(
        request,
        "_asof_slider.html",
        {"snapshots": times, "snapshots_json": json.dumps([t.isoformat() for t in times])},
    )


@app.post("/api/refresh", response_class=HTMLResponse)
def refresh(request: Request) -> HTMLResponse:
    engine = db.get_engine()
    ok = sum(run_source(source, engine) for source in SOURCES)
    response = templates.TemplateResponse(
        request,
        "_refresh_status.html",
        {"ok": ok, "total": len(SOURCES), "server_time": _now()},
    )
    response.headers["HX-Trigger"] = "refresh-done"
    return response
