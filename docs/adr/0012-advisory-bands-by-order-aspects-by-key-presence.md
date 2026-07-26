# Elevation bands come from array order; aspects from key presence

`avalanche.net.nz` has no documented API. These two rules were established by
reading every advisory the endpoint returns, and both look wrong at a glance —
expect a future reader to try "fixing" them.

**Bands are identified by array order, never by their altitude fields.** The
payload's lowest band reports `altitudeFrom: 1200` where it plainly means
*below* 1200m, and the top and bottom bands omit `altitudeTo` entirely. Order is
consistent — index 0 is High Alpine, 1 is Alpine, 2 is Sub-Alpine — so the
parser reads positionally and raises if the count is ever not three. Trusting
the altitude numbers would silently mislabel the sub-alpine rating as alpine.

**A problem's aspects are the keys of the aspect object; the values mean
nothing.** Aspects arrive as `{"n": 0, "ne": 0, "e": 0}` — every value across
every problem is `0`, so presence of the key is the entire signal. Reading the
values would render an empty rose on every advisory. Aspects are banded under
abbreviated elevation keys `ha`, `a` and `sa`, which map to the same three bands
as the danger ratings.

Ratings are 1-5 (Low..Extreme). Negatives are non-ratings, of which only
`-2` "Insufficient snow" has been observed; anything else negative renders as
"No rating" rather than being mistaken for a danger level.
