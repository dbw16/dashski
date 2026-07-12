"""Production source registry. Config lives in code; secrets go in env vars only."""

from dashski.sources.base import Source
from dashski.sources.forecast_example import ExampleForecastSource
from dashski.sources.observation_example import ExampleObservationSource
from dashski.sources.the_remarkables_snow_report import TheRemarkablesSnowReportSource

SOURCES: list[Source] = [
    ExampleForecastSource(),
    ExampleObservationSource(),
    TheRemarkablesSnowReportSource(),
]
