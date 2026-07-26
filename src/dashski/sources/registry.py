"""Production source registry. Config lives in code; secrets go in env vars only."""

from dashski.sources.base import Source
from dashski.sources.nzaa_advisory import NzaaAdvisorySource

SOURCES: list[Source] = [
    NzaaAdvisorySource(),
]
