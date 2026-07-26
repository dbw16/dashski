# Dashski

A single-page dashboard of published avalanche danger for backcountry ski
touring on New Zealand's South Island. Avalanche advisories are the whole
scope: ski field snow reports were removed (ADR 0015), and ski field
operations (lift status, trail grooming) were never in — this is a touring
tool, not a resort trail-map app.

## Language

**Source**:
An external provider of avalanche advisories, registered with a fetch interval.
Each source fetches a raw payload and parses it into readings.
_Avoid_: feed, provider, scraper

**Source Kind**:
The category of data a source produces. Avalanche advisory is the only kind;
the distinction is kept because a second kind is plausible (ADR 0015).

**Avalanche Advisory**:
A forecast region's published avalanche danger for one 24h period: a danger
rating per elevation band, the avalanche problems behind it, and the
forecaster's commentary. It predicts snowpack behaviour, not weather.
_Avoid_: avalanche forecast, avy report, bulletin

**Danger Rating**:
The 1-5 international avalanche danger scale (Low, Moderate, Considerable,
High, Extreme) for one elevation band. Negative values are non-ratings, not
low danger — only "Insufficient snow" (-2) has been seen.
_Avoid_: danger level, risk, avalanche risk

**Elevation Band**:
One of the three altitude tiers an advisory rates separately: High Alpine,
Alpine, Sub-Alpine. Identified by the source's array order, never its
altitude numbers (ADR 0012).
_Avoid_: altitude band, zone, elevation zone

**Avalanche Problem**:
One named pattern of instability within an advisory — Wind Slab, Loose Dry,
Storm Slab, Cornice Fall and so on — with the aspects and elevation bands it
applies to, its likelihood, its destructive size, and its trend. The part of
an advisory that says which slopes to avoid.
_Avoid_: hazard, danger character, avalanche type

**Forecast Region**:
The area one advisory covers — Queenstown, Wanaka. The unit an advisory is
published and displayed per, and the geographic unit of the whole dashboard.
_Avoid_: area, zone, district

**Reading**:
One parsed, typed data point stored from a source — today always an avalanche
advisory. Each source kind has its own reading shape.
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

**Expired**:
An Avalanche Advisory past its 24h validity, measured from when it was issued
rather than when it was fetched. Distinct from Stale: off-season a healthy
fetch keeps returning last season's advisory, so the source is fresh while its
content is long dead (ADR 0013). Beyond a week the advisory is treated as
absent and its ratings are withheld entirely.
_Avoid_: out of date, stale advisory

**Snapshot**:
One point in time the history slider steps through — an `issued_at` value,
the moment a forecaster published or last edited an advisory (ADR 0018). A
fetch that returns what is already stored writes nothing, so every slider
position differs from its neighbours (ADR 0016).
_Avoid_: fetch time, timestamp, revision

**As Of**:
The point in time the dashboard is being viewed at. Defaults to Live; set to
a past Snapshot, each widget shows the latest reading at or before it, per
(source, region).
_Avoid_: point in time, viewing date, cutoff

**Live**:
The As Of state that follows newest data automatically: the slider tracks
the newest Snapshot as it arrives, and auto-refresh polling runs. Any other
As Of is frozen — polling stops until returning to Live.
_Avoid_: current, latest, real-time
