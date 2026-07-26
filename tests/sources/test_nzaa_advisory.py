import json
from datetime import datetime
from pathlib import Path

import pytest

from dashski.sources.base import RawPayload
from dashski.sources.nzaa_advisory import REGIONS, NzaaAdvisorySource, parse_history

FIXTURE = Path(__file__).parent / "fixtures" / "nzaa_forecast.json"


def _raw(payload: object | None = None) -> RawPayload:
    text = json.dumps(payload) if payload is not None else FIXTURE.read_text(encoding="utf-8")
    return RawPayload(text=text, http_status=200)


def _fixture_forecasts() -> list[dict[str, object]]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))["forecasts"]


def test_parses_both_advisories_for_both_regions() -> None:
    advisories = NzaaAdvisorySource().parse(_raw())

    assert [a.region for a in advisories] == ["Queenstown"] * 2 + ["Wanaka"] * 2


def test_parses_newest_queenstown_advisory() -> None:
    advisories = NzaaAdvisorySource().parse(_raw())

    advisory = max((a for a in advisories if a.region == "Queenstown"), key=lambda a: a.issued_at)
    assert advisory.forecaster == "Will Rowntree"
    assert advisory.valid_period == "24hrs"
    assert advisory.confidence_level == "High"
    assert advisory.important_info is not None
    assert advisory.important_info.startswith("A nice day to be in the mountains.")
    assert advisory.mountain_weather is not None
    assert "1000m FAFL" in advisory.mountain_weather
    assert advisory.snowpack is not None and advisory.recent_activity is not None
    assert advisory.sliding_danger is not None


def test_bands_come_from_array_order_not_altitude_fields() -> None:
    """The lowest band reports altitudeFrom: 1200 where it means below 1200m."""
    advisory = max(
        (a for a in NzaaAdvisorySource().parse(_raw()) if a.region == "Queenstown"),
        key=lambda a: a.issued_at,
    )

    assert (advisory.danger_high_alpine, advisory.danger_alpine, advisory.danger_sub_alpine) == (
        1,
        1,
        -2,
    )


def test_issued_at_converts_nz_local_to_naive_utc() -> None:
    """Fixture's newest Queenstown lastEdited is 2026-07-25 20:50:09 NZST (UTC+12)."""
    advisory = max(
        (a for a in NzaaAdvisorySource().parse(_raw()) if a.region == "Queenstown"),
        key=lambda a: a.issued_at,
    )

    assert advisory.issued_at.isoformat() == "2026-07-25T08:50:09"


def test_problem_aspects_come_from_key_presence() -> None:
    """Every aspect value in the payload is 0, so only the keys carry meaning."""
    advisory = max(
        (a for a in NzaaAdvisorySource().parse(_raw()) if a.region == "Queenstown"),
        key=lambda a: a.issued_at,
    )

    problem = advisory.problems[0]
    assert problem.character == "Wind Slab"
    assert problem.priority == "Primary"
    assert problem.trend == "Decreasing"
    assert problem.aspects_high_alpine == "N,NE,E,SE,NW"
    assert problem.aspects_alpine == "N,NE,E,SE,NW"
    assert problem.aspects_sub_alpine is None


def test_keeps_half_step_problem_sizes() -> None:
    advisory = max(
        (a for a in NzaaAdvisorySource().parse(_raw()) if a.region == "Wanaka"),
        key=lambda a: a.issued_at,
    )

    assert advisory.problems[0].size == 1.5


def test_prose_is_stripped_to_text_with_paragraph_breaks() -> None:
    advisory = max(
        (a for a in NzaaAdvisorySource().parse(_raw()) if a.region == "Queenstown"),
        key=lambda a: a.issued_at,
    )

    assert advisory.important_info is not None
    assert "<" not in advisory.important_info
    assert "\xa0" not in advisory.important_info
    assert "\n\n" in advisory.important_info


def test_ignores_regions_we_do_not_track() -> None:
    forecasts = _fixture_forecasts()
    for forecast in forecasts[:2]:
        forecast["regionId"] = 5  # Craigieburn Range

    advisories = NzaaAdvisorySource().parse(_raw({"forecasts": forecasts}))

    assert {a.region for a in advisories} == {"Wanaka"}


def test_raises_when_payload_has_none_of_our_regions() -> None:
    forecasts = _fixture_forecasts()
    for forecast in forecasts:
        forecast["regionId"] = 5

    with pytest.raises(ValueError, match="No advisories for regions"):
        NzaaAdvisorySource().parse(_raw({"forecasts": forecasts}))


def test_raises_when_band_count_changes() -> None:
    """A shape change in the undocumented API must fail the run, not half-render."""
    forecasts = _fixture_forecasts()
    for forecast in forecasts:
        bands = forecast["altitudeDanger"]
        assert isinstance(bands, list)
        del bands[0]

    with pytest.raises(ValueError, match="elevation bands, expected 3"):
        NzaaAdvisorySource().parse(_raw({"forecasts": forecasts}))


HISTORY_FIXTURE = Path(__file__).parent / "fixtures" / "nzaa_forecastsearch.json"


def _history_payload() -> str:
    return HISTORY_FIXTURE.read_text(encoding="utf-8")


def test_parses_a_historical_advisory() -> None:
    advisory = parse_history(_history_payload(), REGIONS[0])

    assert advisory is not None
    assert advisory.region == "Queenstown"
    assert advisory.forecaster == "Will Rowntree"
    assert (advisory.danger_high_alpine, advisory.danger_alpine, advisory.danger_sub_alpine) == (
        1,
        1,
        -2,
    )
    assert [p.character for p in advisory.problems] == ["Wind Slab", "Loose Wet"]


def test_historical_advisory_is_snapshotted_at_its_issue_time() -> None:
    """Backfilled rows were never fetched live, so fetched_at is when it was published."""
    advisory = parse_history(_history_payload(), REGIONS[0])

    assert advisory is not None
    assert advisory.fetched_at == advisory.issued_at
    assert advisory.issued_at == datetime(2025, 8, 14, 17, 29, 45)  # 05:29 NZ -> UTC


def test_historical_advisory_has_no_confidence() -> None:
    """forecastsearch omits the confidence fields that live fetches carry."""
    advisory = parse_history(_history_payload(), REGIONS[0])

    assert advisory is not None
    assert advisory.confidence_level is None
    assert advisory.confidence_reasons is None


def test_parses_missing_history_as_none() -> None:
    """Dates before records begin answer with a null forecast, not an error."""
    assert parse_history('{"forecast": null}', REGIONS[0]) is None
