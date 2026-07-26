# An identical refetch stores nothing and creates no Snapshot

A Snapshot is meant to be a moment the dashboard's known state changed, but
every fetch was writing a full set of advisory rows whether or not the source
had published anything new. Off-season that is the normal case: the NZAA API
keeps returning last season's advisories, so a half-hourly fetch added 48
slider positions a day, all showing the same screen. The slider became mostly
noise to drag through.

So `run_source` now compares each parsed reading against what is already
stored and skips the insert when it is identical. "Identical" is every column
the source populated plus the advisory's problems, ignoring `id` and
`fetched_at` — the bookkeeping of when we stored it, which is exactly what
would otherwise differ. Problems are compared as an unordered set so a
reordering by the CMS doesn't read as a change.

Dedupe is per reading, not per fetch: if Queenstown changes and Wanaka
doesn't, only Queenstown gets a row at the new `fetched_at`. Widgets already
resolve As Of as "the latest reading at or before this point, per source and
region" (ADR 0007), so Wanaka keeps rendering from its older row and the new
Snapshot correctly shows one region moving.

The comparison is scoped to rows with the same `(source_id, region,
issued_at)` rather than scanning history — that is the same publication, of
which dedupe leaves at most a handful of edited versions.

Rows stored before this existed are cleaned up by `dashski.dedupe`, a one-off
that applies the same comparison to history and keeps the earliest of each
identical set, so the Snapshot that first showed an advisory is the one that
survives. It reports by default and takes a backup of the SQLite file before
deleting: there are no migrations to roll back here (ADR 0015), so the copy is
the only undo. Run on production 2026-07-26: 209 advisories over 14 Snapshots
became 21 over 4, with all 8 regions intact.
