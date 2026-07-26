# Backfilled advisories are snapshotted at their issue time

The live source only ever sees the two most recent advisories per region, so
the history slider starts wherever the DB does — after a volume loss or a fresh
deploy, that is hours. The NZAA's `/api/forecastsearch` answers for a past date
and reaches back to 2018-03-13, so the history is recoverable; `dashski.backfill`
walks it backwards a region at a time.

Every backfilled row needs a `fetched_at`, and that is the whole decision: it is
what As Of filters on (ADR 0009) and what the slider steps through (ADR 0010).
Backfilled rows get `fetched_at = issued_at`.

The alternative — stamping them with the moment the backfill ran — is what ADR
0009 reads as saying, and it makes the exercise pointless: eight seasons collapse
into a single Snapshot at the present, the slider gains nothing, and the recovered
advisories are indistinguishable from a burst of live fetches.

## Reconciling this with ADR 0009

ADR 0009 chose `fetched_at` over `issued_at` so that As Of replays what the
dashboard actually displayed, and explicitly to avoid "history silently reshaping
itself after the fact as backfills land". This decision does not overturn that.
It is narrower than it looks:

- ADR 0009's concern is a *late scrape* — an advisory we really did fetch, at a
  time that differs from when it was issued. There, two honest timestamps
  compete, and anchoring on `issued_at` would rewrite a display history we have.
- Backfill has no competing timestamp. There is no moment at which we displayed
  these advisories, because we did not have them. `fetched_at = issued_at` is not
  overriding a fetch time; it is supplying the only one that means anything.

The invariant is preserved by construction rather than by good intentions: the
walk is *frontier-exclusive*. Each region resumes from the oldest advisory
already stored and only ever requests strictly earlier days, so a backfill writes
solely into the stretch of time where our display history is empty. It cannot
reshape a Snapshot that already exists, because it never writes at or after one.

That also keeps backfilled and live rows from colliding on the same publication —
worth having, since `forecastsearch` omits `confidenceLevel`/`confidenceReasons`
that live fetches carry, so the same advisory from the two paths would not
compare equal under ADR 0016's content key and would store twice.

## Consequences

The slider mixes two meanings in one column: for live rows `fetched_at` is when
we fetched, for backfilled rows it is when the NZAA published. Nothing in the app
needs to tell them apart today, so no column marks which is which; if the
distinction ever matters, that is the change to make.

Snapshots stay sparse, as ADR 0016 already made them — regions publish at
different times, so each backfilled Snapshot carries the one region that
published then, and widgets resolve the rest from older rows (ADR 0007). The
oldest Snapshot in the DB therefore shows a single region. That is pre-existing
behaviour at the edge of history, not something backfill introduced.

Backfill deliberately leaves `SourceStatus` and `FetchRun` alone. It is not a
Fetch Run and must not move the staleness indicators; it only creates the
`SourceStatus` row if the poller has never run.

Runs are restartable rather than transactional: each advisory commits as it
lands, and the next run re-reads the frontier, so an interrupted backfill costs
only the days it had not reached. Days are walked newest-first so an interruption
leaves the frontier contiguous instead of punching a hole a later run would
step over.
