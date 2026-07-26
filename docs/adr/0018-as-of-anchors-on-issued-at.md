# As Of anchors on issued_at, not fetched_at

Supersedes ADR 0009. Snapshots, the As Of filter, and latest-per-region
resolution anchor on `issued_at` — the forecaster's publish/last-edit time —
instead of `fetched_at`. ADR 0009 preferred replaying what the dashboard
displayed, but ADR 0017 already anchored all backfilled history on issue time,
leaving the slider mixing two meanings in one column; and since identical
refetches store nothing (ADR 0016), a live row's `fetched_at` was only ever
`issued_at` plus up to a poll interval of lag. Anchoring on issue time makes
the whole timeline mean one thing: when the forecaster said it.

## Consequences

- ADR 0009's trade-off flips: an advisory scraped late (fetch outage, parser
  fix) now slots into history at its issue time instead of appearing when we
  caught up. History answers "what was published by T", not "what did the
  dashboard display at T".
- ADR 0017's `fetched_at = issued_at` hack is retired: backfill stamps its
  real fetch time, and `fetched_at` is honest bookkeeping everywhere. Rows
  backfilled before this keep `fetched_at = issued_at`, which nothing reads
  for display.
- The same publication stored twice — live and backfilled rows differ on the
  confidence fields (ADR 0017) — collapses to one Snapshot; the `fetched_at`
  tiebreak in latest-per-region resolution picks the live row, which carries
  more data.
- A fetch that stores several regions no longer makes one shared Snapshot;
  each publication is its own slider position at its own time.
