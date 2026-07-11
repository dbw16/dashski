from datetime import UTC, datetime
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="Dashski")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")

ping_count = 0


def _now() -> str:
    return datetime.now(UTC).strftime("%H:%M:%S UTC")


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request, "index.html", {"server_time": _now(), "ping_count": ping_count}
    )


@app.get("/api/time", response_class=HTMLResponse)
def server_time(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "_time.html", {"server_time": _now()})


@app.post("/api/ping", response_class=HTMLResponse)
def ping(request: Request) -> HTMLResponse:
    global ping_count
    ping_count += 1
    return templates.TemplateResponse(request, "_ping.html", {"ping_count": ping_count})
