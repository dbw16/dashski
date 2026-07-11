"""Example snow report source. Clone this module per ski field (Coronet Peak, Cardrona, …)."""

from collections.abc import Sequence

from dashski.models import SnowReport, SourceKind
from dashski.sources.base import RawPayload


class ExampleSnowReportSource:
    """Stub: a ski field's snow report page, e.g. Coronet Peak (NZSki)."""

    source_id = "example-snow-report"
    kind = SourceKind.SNOW_REPORT
    interval_seconds = 3600

    def fetch(self) -> RawPayload:
        raise NotImplementedError("TODO: fetch the snow report page with httpx2")

    def parse(self, raw: RawPayload) -> Sequence[SnowReport]:
        raise NotImplementedError("TODO: parse the page into SnowReport rows")
