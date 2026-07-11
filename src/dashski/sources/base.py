"""Generic Source protocol (ADR 0001): every source kind shares one fetch/parse shape."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from dashski.models import Reading, SourceKind


@dataclass(frozen=True)
class RawPayload:
    """Unparsed response from a source, exactly as fetched."""

    text: str
    http_status: int | None = None


class Source(Protocol):
    """One external data provider. Implementations register in registry.py.

    fetch() and parse() are split so the framework can persist the raw payload
    before parsing — a parse failure still leaves the payload in RawFetch for
    debugging.
    """

    source_id: str
    kind: SourceKind
    interval_seconds: int

    def fetch(self) -> RawPayload:
        """Fetch the raw payload from the provider. Blocking; runs off the event loop."""
        ...

    def parse(self, raw: RawPayload) -> Sequence[Reading]:
        """Parse a raw payload into typed readings for this source's kind."""
        ...
