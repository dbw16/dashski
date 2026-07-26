"""Advisory widget: band ratings render, expiry is content-age not fetch-age (ADR 0013)."""

from datetime import datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlmodel import Session

from dashski.models import (
    AvalancheAdvisory,
    AvalancheProblem,
    SourceKind,
    SourceStatus,
    utcnow,
)

SOURCE_ID = "seed-advisory"


def _seed_status(engine: Engine) -> None:
    with Session(engine) as session:
        session.add(
            SourceStatus(
                source_id=SOURCE_ID,
                kind=SourceKind.ADVISORY,
                last_attempt_at=utcnow(),
                last_success_at=utcnow(),
            )
        )
        session.commit()


def _seed_advisory(
    engine: Engine,
    region: str,
    *,
    issued_at: datetime,
    fetched_at: datetime | None = None,
    bands: tuple[int | None, int | None, int | None] = (2, 2, -2),
    problems: list[AvalancheProblem] | None = None,
) -> None:
    with Session(engine) as session:
        advisory = AvalancheAdvisory(
            source_id=SOURCE_ID,
            fetched_at=fetched_at or utcnow(),
            region=region,
            issued_at=issued_at,
            valid_period="24hrs",
            forecaster="Test Forecaster",
            danger_high_alpine=bands[0],
            danger_alpine=bands[1],
            danger_sub_alpine=bands[2],
            confidence_level="High",
        )
        advisory.problems = problems or []
        session.add(advisory)
        session.commit()


def test_renders_both_regions_with_band_ratings(client: TestClient, engine: Engine) -> None:
    _seed_status(engine)
    _seed_advisory(engine, "Queenstown", issued_at=utcnow(), bands=(3, 2, -2))
    _seed_advisory(engine, "Wanaka", issued_at=utcnow(), bands=(1, 1, 1))

    response = client.get("/api/widget/advisory")

    assert response.status_code == 200
    assert "Queenstown" in response.text
    assert "Wanaka" in response.text
    assert "Considerable" in response.text
    assert "Insufficient snow" in response.text
    assert "Low" in response.text


def test_renders_problem_with_aspect_rose(client: TestClient, engine: Engine) -> None:
    _seed_status(engine)
    _seed_advisory(
        engine,
        "Queenstown",
        issued_at=utcnow(),
        problems=[
            AvalancheProblem(
                priority="Primary",
                priority_level=1,
                character="Wind Slab",
                likelihood=2,
                size=1.5,
                trend="Decreasing",
                aspects_high_alpine="N,NE,E",
                aspects_alpine="N,NE",
            )
        ],
    )

    response = client.get("/api/widget/advisory")

    assert "Wind Slab" in response.text
    assert "Size D1.5" in response.text
    assert "Likelihood 2" in response.text
    assert "High Alpine: N, NE, E" in response.text
    assert response.text.count("rose-on") == 3


def test_regions_render_in_configured_order(client: TestClient, engine: Engine) -> None:
    _seed_status(engine)
    _seed_advisory(engine, "Wanaka", issued_at=utcnow())
    _seed_advisory(engine, "Queenstown", issued_at=utcnow())

    response = client.get("/api/widget/advisory")

    assert response.text.index("Queenstown") < response.text.index("Wanaka")


def test_picks_newest_issued_advisory_within_one_fetch(client: TestClient, engine: Engine) -> None:
    """One fetch stores both published advisories under a single fetched_at."""
    _seed_status(engine)
    fetched_at = utcnow()
    _seed_advisory(
        engine,
        "Queenstown",
        issued_at=utcnow() - timedelta(hours=26),
        fetched_at=fetched_at,
        bands=(4, 4, 4),
    )
    _seed_advisory(engine, "Queenstown", issued_at=utcnow(), fetched_at=fetched_at, bands=(1, 1, 1))

    response = client.get("/api/widget/advisory")

    # Asserting on the tone class, not the label — "High" also matches "High Alpine".
    assert "band-1" in response.text
    assert "band-4" not in response.text


def test_advisory_past_validity_is_flagged_expired(client: TestClient, engine: Engine) -> None:
    _seed_status(engine)
    _seed_advisory(engine, "Queenstown", issued_at=utcnow() - timedelta(hours=30))

    response = client.get("/api/widget/advisory")

    assert "Expired" in response.text
    assert "advisory-expired" in response.text
    assert "Moderate" in response.text


def test_advisory_older_than_a_week_withholds_ratings(client: TestClient, engine: Engine) -> None:
    _seed_status(engine)
    _seed_advisory(engine, "Queenstown", issued_at=utcnow() - timedelta(days=9))

    response = client.get("/api/widget/advisory")

    assert "No current advisory" in response.text
    assert "Moderate" not in response.text
    assert "avalanche.net.nz/region/queenstown" in response.text


def test_fresh_fetch_of_a_stale_advisory_still_reads_expired(
    client: TestClient, engine: Engine
) -> None:
    """Off-season the API keeps returning last season's advisory to a healthy fetch."""
    _seed_status(engine)
    _seed_advisory(engine, "Queenstown", issued_at=utcnow() - timedelta(days=200))

    response = client.get("/api/widget/advisory")

    assert "updated just now" in response.text
    assert "No current advisory" in response.text


def test_as_of_shows_advisory_known_at_that_snapshot(client: TestClient, engine: Engine) -> None:
    _seed_status(engine)
    older, newer = utcnow() - timedelta(hours=2), utcnow()
    _seed_advisory(engine, "Queenstown", issued_at=older, fetched_at=older, bands=(4, 4, 4))
    _seed_advisory(engine, "Queenstown", issued_at=newer, fetched_at=newer, bands=(1, 1, 1))

    response = client.get("/api/widget/advisory", params={"as_of": older.isoformat()})

    assert "band-4" in response.text
    assert "band-1" not in response.text
    assert "Snapshot from" in response.text


def test_expiry_is_measured_against_the_as_of_position(client: TestClient, engine: Engine) -> None:
    """Viewed from its own snapshot, a then-current advisory must not read expired."""
    _seed_status(engine)
    issued = utcnow() - timedelta(days=5)
    _seed_advisory(engine, "Queenstown", issued_at=issued, fetched_at=issued)

    response = client.get("/api/widget/advisory", params={"as_of": issued.isoformat()})

    assert "Expired" not in response.text
    assert "Moderate" in response.text


def test_advisory_fetch_times_appear_in_snapshots(client: TestClient, engine: Engine) -> None:
    _seed_status(engine)
    fetched_at = utcnow() - timedelta(hours=3)
    _seed_advisory(engine, "Queenstown", issued_at=fetched_at, fetched_at=fetched_at)

    response = client.get("/api/snapshots")

    assert fetched_at.isoformat() in response.text


def test_empty_state(client: TestClient) -> None:
    response = client.get("/api/widget/advisory")

    assert response.status_code == 200
    assert "No advisory data yet" in response.text
