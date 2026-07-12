# As Of anchors on fetched_at, not reported_at/observed_at

Snow Report and Observation readings carry two dates: when we fetched them
(`fetched_at`) and the reading's own claimed date (`reported_at` /
`observed_at`). As Of filters "latest reading per field with `fetched_at` ≤
the selected Snapshot" — replaying what the dashboard actually displayed at
that moment, not what conditions were on a given calendar date.

Trade-off: a report scraped late (fetch outage, parser fix) won't
retroactively appear under an earlier As Of just because its own
`reported_at` falls there. Matching the dashboard's real display history was
judged more useful than a "true conditions on date D" query, and it avoids
history silently reshaping itself after the fact as backfills land.
