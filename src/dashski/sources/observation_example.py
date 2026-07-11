"""Example observation source. Clone this module per real station/provider."""

from collections.abc import Sequence

from dashski.models import ObservationReading, SourceKind
from dashski.sources.base import RawPayload


class ExampleObservationSource:
    """Stub: measured weather from a station, e.g. a NIWA/MetService AWS."""

    source_id = "example-observation"
    kind = SourceKind.OBSERVATION
    interval_seconds = 1800

    def fetch(self) -> RawPayload:
        raise NotImplementedError("TODO: fetch the station observations with httpx2")

    def parse(self, raw: RawPayload) -> Sequence[ObservationReading]:
        raise NotImplementedError("TODO: parse the payload into ObservationReading rows")
