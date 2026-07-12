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


@app.get("/api/widget/observation", response_class=HTMLResponse)
def widget_observation(request: Request, session: SessionDep) -> HTMLResponse:
    recent = session.exec(
        select(ObservationReading)
        .order_by(col(ObservationReading.fetched_at).desc())
        .limit(_HISTORY_SCAN_LIMIT)
    ).all()
    readings = _latest_by_identity(recent, lambda r: (r.source_id, r.station))[:20]
    return templates.TemplateResponse(
        request,
        "_widget_observation.html",
        {"readings": readings, "freshness": _freshness(_statuses(session, SourceKind.OBSERVATION))},
    )


_CALC_24H_MIN_GAP = timedelta(hours=18)
_CALC_24H_MAX_GAP = timedelta(hours=30)


@dataclass(frozen=True)
class SnowReportRow:
    """A snow report plus its 24h-snowfall figure and where that figure came from."""

    report: SnowReport
    new_snow_24h_cm: float | None
    new_snow_24h_calculated: bool


def _prior_snow_report(session: Session, report: SnowReport) -> SnowReport | None:
    """The same field's most recent report strictly before this one — the "yesterday" baseline."""
    return session.exec(
        select(SnowReport)
        .where(col(SnowReport.source_id) == report.source_id)
        .where(col(SnowReport.ski_field) == report.ski_field)
        .where(col(SnowReport.reported_at) < report.reported_at)
        .order_by(col(SnowReport.reported_at).desc())
        .limit(1)
    ).first()


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
def widget_snow_report(request: Request, session: SessionDep) -> HTMLResponse:
    recent = session.exec(
        select(SnowReport).order_by(col(SnowReport.fetched_at).desc()).limit(_HISTORY_SCAN_LIMIT)
    ).all()
    latest = _latest_by_identity(recent, lambda r: (r.source_id, r.ski_field))[:20]
    rows = []
    for report in latest:
        snow_24h, calculated = _snow_24h(report, _prior_snow_report(session, report))
        rows.append(
            SnowReportRow(
                report=report, new_snow_24h_cm=snow_24h, new_snow_24h_calculated=calculated
            )
        )
    return templates.TemplateResponse(
        request,
        "_widget_snow_report.html",
        {"rows": rows, "freshness": _freshness(_statuses(session, SourceKind.SNOW_REPORT))},
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
