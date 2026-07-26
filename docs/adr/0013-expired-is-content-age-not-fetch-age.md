# Expired is content age; Stale is fetch age

`Stale` (CONTEXT.md) means the *source* is unhealthy — its last fetch failed, or
its data is older than its interval allows. That is not sufficient for an
advisory.

The NZAA only forecasts from roughly late June to early October. Out of season
the API keeps returning last season's advisories to a perfectly healthy fetch,
so `_freshness` would report "updated 2m ago" beside a nine-month-old danger
rating. For a safety-critical figure that is the worst possible failure mode:
confidently wrong.

So an advisory carries a second, independent age — `Expired`, measured from
`issued_at` rather than the fetch:

- past its 24h `validPeriod`, the widget greys the ratings and says so;
- past a week, it withholds the ratings entirely and says "No current advisory
  (out of season)", leaving only the link to the official page.

Both are measured against the As Of position, not wall clock. An advisory that
was already a week old at the snapshot being viewed was just as absent then as
it looks now, so scrubbing back never resurrects ratings that were not current.

An advisory can be Expired while its source is fresh, and Stale while its
content is current. The widget shows both, because they answer different
questions: "is dashski working?" and "is this advisory still true?".
