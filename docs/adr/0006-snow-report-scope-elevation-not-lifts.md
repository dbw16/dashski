# SnowReport tracks elevation-dependent snow depth, not lift status

Dashski is a touring dashboard, not a resort trail-map app, so `SnowReport`
does not track lift status (`lifts_open`/`lifts_total` removed) even though
ski fields report it — it's out of scope app-wide, not just for one source.

Base depth is reported by ski fields as a range across the mountain's
elevation (e.g. "15-60cm" lower to upper), which matters for touring
(snowpack varies by elevation) more than a single averaged figure would.
`base_depth_cm` was replaced with `base_depth_lower_cm`/`base_depth_upper_cm`.
A `season_snowfall_cm` field was also added, since season-to-date
accumulation is a snow figure worth surfacing that the schema didn't
previously capture.
