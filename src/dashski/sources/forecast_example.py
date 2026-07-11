"""Example forecast source. Clone this module per real provider (e.g. MetService)."""

from collections.abc import Sequence

from dashski.models import ForecastReading, SourceKind
from dashski.sources.base import RawPayload


class ExampleForecastSource:
    """Stub: a mountain forecast, e.g. MetService for the Queenstown ranges."""

    source_id = "example-forecast"
    kind = SourceKind.FORECAST
    interval_seconds = 3600

    def fetch(self) -> RawPayload:
        raise NotImplementedError("TODO: fetch the forecast API/page with httpx2")

    def parse(self, raw: RawPayload) -> Sequence[ForecastReading]:
        raise NotImplementedError("TODO: parse the payload into ForecastReading rows")
