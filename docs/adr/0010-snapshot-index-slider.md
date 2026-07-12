# History slider is index-based over discrete Snapshots

The slider's positions are the sorted distinct `fetched_at` values
(Snapshots) across Snow Report and Observation readings, not an arbitrary
point picked from a continuous date range. Native `<input type=range>` only
supports evenly-spaced steps, so the slider holds an index (0..N-1) into a
server-rendered snapshot list; the page maps index → real timestamp for
display and for the `as_of` query param sent to the widgets.

This was chosen over a continuous date/time input so every slider position
corresponds to a real, distinct dashboard state — no position is identical
to its neighbor or falls between two fetches. Trade-off: with an hourly
fetch interval, months of history means thousands of steps, imprecise to
hit by touch-dragging alone — prev/next buttons sit alongside the slider for
single-snapshot precision on mobile.
