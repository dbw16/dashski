# Dashski

A single-page dashboard for backcountry ski touring on New Zealand's South Island:
what was forecast, what actually happened, and what the ski fields are reporting.
Snow conditions (depth, snowfall) are in scope; ski field operations (lift status,
trail grooming) are not — this is a touring tool, not a resort trail-map app.

## Language

**Source**:
An external provider of one kind of snow data, registered with a fetch interval.
Each source fetches a raw payload and parses it into readings.
_Avoid_: feed, provider, scraper

**Source Kind**:
The category of data a source produces: forecast, observation, or snow report.

**Forecast**:
Predicted future weather for a location — what the models say will happen.
_Avoid_: prediction, outlook

**Observation**:
Measured weather from a station — what actually happened.
_Avoid_: actuals, actual weather, results

**Snow Report**:
A ski field's self-reported snow conditions: base depth (by elevation), new
snowfall, season snowfall. Lift/trail operations are deliberately out of scope.
_Avoid_: conditions report

**Calculated Figure**:
A number the dashboard derives itself rather than reads directly from a
source — e.g. 24h snowfall estimated from the change in a field's 7-day
total when the field doesn't publish 24h snowfall directly. Always marked
distinctly from a direct source figure so the user knows which they're
trusting.
_Avoid_: estimate, derived value (when the distinction from a direct figure matters, say "calculated")

**Reading**:
One parsed, typed data point stored from a source. Each source kind has its own
reading shape (forecast reading, observation reading, snow report).
_Avoid_: record, data point, entry

**Fetch Run**:
One scheduled attempt to fetch, parse, and store a source's data; each run
records success or the error that stopped it.
_Avoid_: sync, poll, job run

**Raw Fetch**:
The unparsed payload (HTML/JSON text) from a source's most recent fetch. Only
the latest is kept, for debugging broken parsers.

**Widget**:
A self-refreshing dashboard fragment showing the latest readings for one source
kind, including its freshness.
_Avoid_: panel, tile, card

**Stale**:
A source whose latest fetch run failed, or whose data is older than its fetch
interval should allow. Widgets surface staleness rather than silently showing
old data.

**Ski Field**:
A ski area on the South Island (Coronet Peak, Cardrona, Mt Hutt, …). The NZ term.
_Avoid_: resort, ski area, mountain
