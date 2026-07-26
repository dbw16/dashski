"""NZ Avalanche Advisory source — one fetch covers every region we track.

The site's JSON API is undocumented and ignores query parameters, so `/api/forecast`
always returns every region's two most recent advisories in one ~130KB payload. We
fetch it once and filter to REGIONS here rather than registering a source per region
(ADR 0011).
"""

import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

import httpx2
from bs4 import BeautifulSoup

from dashski.models import AvalancheAdvisory, AvalancheProblem, SourceKind
from dashski.sources.base import RawPayload

API_URL = "https://www.avalanche.net.nz/api/forecast"
SITE_URL = "https://www.avalanche.net.nz"
USER_AGENT = "dashski/0.1 (+personal snow-conditions dashboard)"

NZ = ZoneInfo("Pacific/Auckland")


@dataclass(frozen=True)
class Region:
    """A forecast region we track. `id` keys the API payload, `slug` the public page."""

    id: int
    name: str
    slug: str


REGIONS = (
    Region(10, "Queenstown", "queenstown"),
    Region(11, "Wanaka", "wanaka"),
    Region(15, "Aspiring", "aspiring"),
    Region(12, "Fiordland", "fiordland"),
    Region(8, "Ohau", "ohau"),
    Region(7, "Aoraki/Mt Cook", "aorakimt-cook"),
    Region(9, "Two Thumbs", "two-thumbs"),
    Region(6, "Mt Hutt", "mt-hutt"),
)
"""Ids and slugs come from the site's own /api/region listing. NZAA has no Tekapo
region — the Tekapo ski fields sit under Two Thumbs. Display order is this order."""

ASPECT_ORDER = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")
"""Compass aspects clockwise from north — the order a rose is drawn in."""

# additionalInformation is always these four sections, keyed by title.
_INFO_SECTIONS = {
    "Recent Avalanche Activity": "recent_activity",
    "Current Snowpack Conditions": "snowpack",
    "Mountain Weather": "mountain_weather",
    "Sliding Danger": "sliding_danger",
}


def advisory_url(region: Region) -> str:
    return f"{SITE_URL}/region/{region.slug}"


class NzaaAdvisorySource:
    """Avalanche advisories for the regions in REGIONS, from avalanche.net.nz."""

    source_id = "nzaa-advisory"
    kind = SourceKind.ADVISORY
    interval_seconds = 1800

    def fetch(self) -> RawPayload:
        response = httpx2.get(API_URL, headers={"User-Agent": USER_AGENT}, timeout=15.0)
        response.raise_for_status()
        return RawPayload(text=response.text, http_status=response.status_code)

    def parse(self, raw: RawPayload) -> Sequence[AvalancheAdvisory]:
        forecasts = json.loads(raw.text)["forecasts"]
        by_region = {region.id: region for region in REGIONS}
        fetched_at = datetime.now(UTC).replace(tzinfo=None)

        advisories = [
            _advisory(forecast, by_region[forecast["regionId"]], self.source_id, fetched_at)
            for forecast in forecasts
            if forecast.get("regionId") in by_region
        ]
        if not advisories:
            raise ValueError(f"No advisories for regions {sorted(by_region)} in payload")
        return advisories


def _advisory(
    forecast: dict[str, Any], region: Region, source_id: str, fetched_at: datetime
) -> AvalancheAdvisory:
    bands = _band_ratings(forecast["altitudeDanger"], region)
    sections = _sections(forecast.get("additionalInformation") or [])

    advisory = AvalancheAdvisory(
        source_id=source_id,
        fetched_at=fetched_at,
        region=region.name,
        issued_at=_issued_at(forecast),
        valid_period=forecast.get("validPeriod"),
        forecaster=_squash(forecast.get("forecaster")),
        danger_high_alpine=bands[0],
        danger_alpine=bands[1],
        danger_sub_alpine=bands[2],
        confidence_level=forecast.get("confidenceLevel"),
        confidence_reasons="\n".join(forecast.get("confidenceReasons") or []) or None,
        important_info=_text(forecast.get("importantInformation")),
        recent_activity=sections["recent_activity"],
        snowpack=sections["snowpack"],
        mountain_weather=sections["mountain_weather"],
        sliding_danger=sections["sliding_danger"],
    )
    advisory.problems = [_problem(p) for p in forecast.get("avalancheDangers") or []]
    return advisory


def _issued_at(forecast: dict[str, Any]) -> datetime:
    """Publish time, converted from NZ local to naive UTC for storage.

    Forecasters edit an advisory after publishing it, so `lastEdited` — not
    `created` — is when what we're showing became true.
    """
    stamp = forecast.get("lastEdited") or forecast.get("created")
    if not stamp:
        raise ValueError(f"Advisory {forecast.get('id')} has no lastEdited or created timestamp")
    local = datetime.strptime(stamp, "%Y-%m-%d %H:%M:%S").replace(tzinfo=NZ)
    return local.astimezone(UTC).replace(tzinfo=None)


def _band_ratings(bands: Sequence[dict[str, Any]], region: Region) -> tuple[int | None, ...]:
    """Ratings for (high alpine, alpine, sub-alpine), taken strictly by array order.

    The payload's `altitudeFrom`/`altitudeTo` cannot be trusted — the lowest band
    reports `altitudeFrom: 1200` where it plainly means *below* 1200m. Order is
    consistent and descends from the highest band (ADR 0012).
    """
    if len(bands) != 3:
        raise ValueError(f"{region.name} advisory has {len(bands)} elevation bands, expected 3")
    return tuple(band.get("rating") for band in bands)


def _sections(info: Sequence[dict[str, Any]]) -> dict[str, str | None]:
    """The four fixed additionalInformation sections, as plain text."""
    found = {item.get("title"): item.get("content") for item in info}
    return {field: _text(found.get(title)) for title, field in _INFO_SECTIONS.items()}


def _problem(problem: dict[str, Any]) -> AvalancheProblem:
    aspects = problem.get("aspects") or {}
    return AvalancheProblem(
        priority=problem.get("priority"),
        priority_level=problem.get("priority_level"),
        character=(problem.get("character") or {}).get("title") or "Unspecified",
        likelihood=problem.get("likelihood"),
        size=problem.get("size"),
        trend=problem.get("trend"),
        description=_text(problem.get("description")),
        aspects_high_alpine=_aspects(aspects.get("ha")),
        aspects_alpine=_aspects(aspects.get("a")),
        aspects_sub_alpine=_aspects(aspects.get("sa")),
    )


def _aspects(aspects: dict[str, Any] | None) -> str | None:
    """Compass aspects a problem applies to, in clockwise order from north.

    The API gives an object like {"n": 0, "ne": 0} whose values are always 0, so
    the keys alone carry the meaning (ADR 0012).
    """
    if not aspects:
        return None
    present = {key.upper() for key in aspects}
    return ",".join(a for a in ASPECT_ORDER if a in present) or None


def _text(html: str | None) -> str | None:
    """Flatten the CMS's HTML prose to plain text, keeping paragraph breaks.

    Forecasters write in a rich-text editor, so the payload carries pasted inline
    styles and non-breaking spaces but no links, images, lists or tables. Stripping
    at parse time keeps third-party markup out of the templates entirely (ADR 0011).
    """
    if not html:
        return None
    soup = BeautifulSoup(html, "html.parser")
    for br in soup.find_all("br"):
        br.replace_with("\n")
    blocks = list(soup.find_all("p")) or [soup]
    paragraphs = [text for block in blocks if (text := _squash(block.get_text()))]
    return "\n\n".join(paragraphs) or None


def _squash(text: str | None) -> str | None:
    """Collapse runs of whitespace (incl. &nbsp;) per line, dropping blank lines."""
    if text is None:
        return None
    lines = [" ".join(line.split()) for line in text.replace("\xa0", " ").splitlines()]
    return "\n".join(line for line in lines if line) or None
