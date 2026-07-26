# Widgets show one row per (source, field), not raw history

Reading tables are append-only (ADR 0004), so a polled field/region accumulates
one row per fetch. Widget queries used to take the latest N rows overall with
no grouping, so a field polled more than once showed up repeatedly — worst on
Snow Report, where the same ski field flooded the whole table. Widgets now
collapse history to the most recently *fetched* row per `(source_id, domain
field)` before rendering, applied uniformly to Snow Report (ski field) and
Avalanche Advisory (region).

The identity key is `(source_id, field)`, not the field alone. Today it's a
1:1 clone-per-field pattern, so they're equivalent — but if two sources ever
report on the same field, keying by field alone would silently drop one
source's row. Keying by source keeps both visible, at the cost of not
strictly guaranteeing one row per field on screen in that (currently
nonexistent) case.
