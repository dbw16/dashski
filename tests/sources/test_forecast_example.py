import pytest


@pytest.mark.skip(reason="TODO: implement once ExampleForecastSource.fetch/parse are written")
def test_parses_saved_forecast_payload() -> None:
    """Feed a saved real payload into parse() and assert on the ForecastReading rows."""
