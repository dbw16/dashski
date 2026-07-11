import os
from collections.abc import AsyncGenerator, Sequence
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

SessionDep = Annotated[Session, Depends(db.get_session)]

ping_count = 0


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


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request, "index.html", {"server_time": _now(), "ping_count": ping_count}
    )


@app.get("/api/widget/forecast", response_class=HTMLResponse)
def widget_forecast(request: Request, session: SessionDep) -> HTMLResponse:
    readings = session.exec(
        select(ForecastReading).order_by(col(ForecastReading.fetched_at).desc()).limit(20)
    ).all()
    return templates.TemplateResponse(
        request,
        "_widget_forecast.html",
        {"readings": readings, "freshness": _freshness(_statuses(session, SourceKind.FORECAST))},
    )


@app.get("/api/widget/observation", response_class=HTMLResponse)
def widget_observation(request: Request, session: SessionDep) -> HTMLResponse:
    readings = session.exec(
        select(ObservationReading).order_by(col(ObservationReading.observed_at).desc()).limit(20)
    ).all()
    return templates.TemplateResponse(
        request,
        "_widget_observation.html",
        {"readings": readings, "freshness": _freshness(_statuses(session, SourceKind.OBSERVATION))},
    )


@app.get("/api/widget/snow-report", response_class=HTMLResponse)
def widget_snow_report(request: Request, session: SessionDep) -> HTMLResponse:
    readings = session.exec(
        select(SnowReport).order_by(col(SnowReport.reported_at).desc()).limit(20)
    ).all()
    return templates.TemplateResponse(
        request,
        "_widget_snow_report.html",
        {"readings": readings, "freshness": _freshness(_statuses(session, SourceKind.SNOW_REPORT))},
    )


@app.get("/api/time", response_class=HTMLResponse)
def server_time(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "_time.html", {"server_time": _now()})


@app.post("/api/ping", response_class=HTMLResponse)
def ping(request: Request) -> HTMLResponse:
    global ping_count
    ping_count += 1
    return templates.TemplateResponse(request, "_ping.html", {"ping_count": ping_count})
