import pytest


@pytest.mark.skip(reason="TODO: implement once ExampleObservationSource.fetch/parse are written")
def test_parses_saved_observation_payload() -> None:
    """Feed a saved real payload into parse() and assert on the ObservationReading rows."""
