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
A dashboard fragment showing one source kind's readings as of the current As
Of position (Live by default), including freshness or, when viewing a past
Snapshot, which one.
_Avoid_: panel, tile, card

**Stale**:
A source whose latest fetch run failed, or whose data is older than its fetch
interval should allow, while Live. Not shown when viewing a past Snapshot —
a frozen historical view isn't "stale," it's just old on purpose.

**Snapshot**:
One point in time — a `fetched_at` value shared by readings stored in the
same fetch — at which the dashboard's known state changed. The unit the
history slider steps through.
_Avoid_: fetch time, timestamp, revision

**As Of**:
The point in time the dashboard is being viewed at. Defaults to Live; set to
a past Snapshot, each widget shows the latest reading at or before it, per
(source, field).
_Avoid_: point in time, viewing date, cutoff

**Live**:
The As Of state that follows newest data automatically: the slider tracks
the newest Snapshot as it arrives, and auto-refresh polling runs. Any other
As Of is frozen — polling stops until returning to Live.
_Avoid_: current, latest, real-time

**Ski Field**:
A ski area on the South Island (Coronet Peak, Cardrona, Mt Hutt, …). The NZ term.
_Avoid_: resort, ski area, mountain
