"""The Remarkables (NZSki) snow report source."""

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

import httpx2
from bs4 import BeautifulSoup

from dashski.models import SnowReport, SourceKind
from dashski.sources.base import RawPayload

URL = "https://www.theremarkables.co.nz/weather-report/"
USER_AGENT = "dashski/0.1 (+personal snow-conditions dashboard)"


class TheRemarkablesSnowReportSource:
    """The Remarkables' self-reported snow conditions (NZSki)."""

    source_id = "nzski-remarkables-snow-report"
    kind = SourceKind.SNOW_REPORT
    interval_seconds = 3600

    def fetch(self) -> RawPayload:
        response = httpx2.get(URL, headers={"User-Agent": USER_AGENT}, timeout=10.0)
        response.raise_for_status()
        return RawPayload(text=response.text, http_status=response.status_code)

    def parse(self, raw: RawPayload) -> Sequence[SnowReport]:
        soup = BeautifulSoup(raw.text, "html.parser")
        values = _status_values(soup)
        base_lower, base_upper = _parse_range_cm(values.get("Snow Base"))

        return [
            SnowReport(
                source_id=self.source_id,
                fetched_at=datetime.now(UTC).replace(tzinfo=None),
                ski_field="The Remarkables",
                reported_at=_parse_reported_at(soup),
                base_depth_lower_cm=base_lower,
                base_depth_upper_cm=base_upper,
                new_snow_7d_cm=_parse_cm(values.get("Last 7 Days")),
                season_snowfall_cm=_parse_cm(values.get("Season Snowfall")),
                summary=_parse_summary(soup),
            )
        ]


def _status_values(soup: BeautifulSoup) -> dict[str, str]:
    """Map each weather-status block's description label to its data text.

    The page repeats this component for mobile/desktop breakpoints, so the same
    label appears multiple times with identical values; first-seen wins.
    """
    values: dict[str, str] = {}
    for item in soup.find_all("div", class_="w_weather-status"):
        description = item.find("p", class_="w_weather-status__description")
        data = item.find("p", class_="w_weather-status__data")
        if description and data:
            values.setdefault(description.get_text(strip=True), data.get_text(strip=True))
    return values


def _parse_cm(text: str | None) -> float | None:
    if text is None:
        return None
    digits = "".join(ch for ch in text if ch.isdigit() or ch == ".")
    return float(digits) if digits else None


def _parse_range_cm(text: str | None) -> tuple[float | None, float | None]:
    """Parse "15 - 60cm" into (15.0, 60.0); a bare "45cm" becomes (45.0, 45.0)."""
    if text is None:
        return None, None
    parts = text.split("-")
    if len(parts) == 2:
        return _parse_cm(parts[0]), _parse_cm(parts[1])
    value = _parse_cm(text)
    return value, value


def _parse_summary(soup: BeautifulSoup) -> str | None:
    blurb = soup.find("p", class_="weather-blurb")
    return blurb.get_text(strip=True) if blurb else None


def _parse_reported_at(soup: BeautifulSoup) -> datetime:
    span = soup.find("span", class_="last-updated")
    if span is None:
        raise ValueError("Could not find snow report timestamp (span.last-updated)")
    text = span.get_text(strip=True).removeprefix("Last Updated:").strip()

    # Page gives no year (e.g. "Sun 12 Jul 10:10 AM"); assume current year, but
    # roll back one year if that would place the report in the future - handles
    # a report from late December being fetched just after New Year.
    now = datetime.now(UTC).replace(tzinfo=None)
    candidate = datetime.strptime(f"{text} {now.year}", "%a %d %b %I:%M %p %Y")
    if candidate > now + timedelta(days=1):
        candidate = candidate.replace(year=now.year - 1)
    return candidate
