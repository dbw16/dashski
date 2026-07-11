import pytest


@pytest.mark.skip(reason="TODO: implement once ExampleSnowReportSource.fetch/parse are written")
def test_parses_saved_snow_report_page() -> None:
    """Feed a saved real page into parse() and assert on the SnowReport rows."""
