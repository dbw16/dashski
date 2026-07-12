from datetime import datetime
from pathlib import Path

from dashski.sources.base import RawPayload
from dashski.sources.the_remarkables_snow_report import TheRemarkablesSnowReportSource

FIXTURE = Path(__file__).parent / "fixtures" / "the_remarkables_weather_report.html"


def test_parses_saved_weather_report_page() -> None:
    raw = RawPayload(text=FIXTURE.read_text(encoding="utf-8"), http_status=200)

    readings = TheRemarkablesSnowReportSource().parse(raw)

    assert len(readings) == 1
    report = readings[0]
    assert report.ski_field == "The Remarkables"
    assert report.base_depth_lower_cm == 15.0
    assert report.base_depth_upper_cm == 60.0
    assert report.new_snow_7d_cm == 10.0
    assert report.season_snowfall_cm == 45.0
    assert report.summary == "Another Perfect Day at Remarks!"
    assert report.reported_at.month == 7
    assert report.reported_at.day == 12
    assert report.reported_at.hour == 10
    assert report.reported_at.minute == 10


def test_reported_at_rolls_back_a_year_when_date_would_be_in_the_future() -> None:
    from unittest.mock import patch

    raw = RawPayload(text=FIXTURE.read_text(encoding="utf-8"), http_status=200)

    with patch("dashski.sources.the_remarkables_snow_report.datetime") as mock_datetime:
        mock_datetime.now.return_value = datetime(2027, 1, 2, 6, 0, 0)
        mock_datetime.strptime = datetime.strptime
        report = TheRemarkablesSnowReportSource().parse(raw)[0]

    assert report.reported_at.year == 2026
