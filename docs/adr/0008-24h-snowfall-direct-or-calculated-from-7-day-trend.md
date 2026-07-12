# 24h snowfall: direct from source, else calculated from the 7-day trend, never persisted

`SnowReport.new_snow_24h_cm` holds a direct source figure when a field
publishes one (none do yet). When it's null, the Snow Report widget estimates
it at render time as `today's new_snow_7d_cm − prior report's new_snow_7d_cm`
— the newest day's snowfall as it rolls into the 7-day window. This is only
an approximation (it also drops whatever fell off the window's oldest day),
so the UI marks calculated figures with `*` and a legend, distinct from a
direct figure.

The estimate is only computed when the prior report is 18–30h old. Outside
that window (a field that missed updates) the gap no longer represents
"yesterday," and showing a number would mislabel a multi-day delta as 24h —
so the widget shows no figure at all rather than a misleading one. A negative
result (an oversized day fell out of the window) is clamped to 0 and still
labelled calculated, since negative snowfall isn't a meaningful thing to show.

The estimate is computed at render time, not persisted onto the row, even
though `scheduler.run_source` could compute and store it right after
parsing. `SnowReport` is documented as a ski field's *self-reported*
conditions; writing our own guess into that row conflates source fact with
derived estimate, and freezes the guess against future formula changes with
no backfill path. Render-time recomputation costs two extra indexed queries
per field per widget load, which is cheap at this scale.
