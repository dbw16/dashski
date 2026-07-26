# Per-kind reading tables; RawFetch keeps latest only

Each source kind gets its own strongly-typed table (`SnowReport`,
`AvalancheAdvisory`) instead of one generic table with a JSON payload column —
a field's base depth and a region's danger ratings are different shapes, and
column-level typing/queryability beats schema flexibility here.

Raw payloads are kept for debugging broken parsers, but `RawFetch` holds only
the most recent payload per source (overwritten each run, deliberately not an
append-only log) to stop scraped HTML from bloating the SQLite file. Don't
"fix" this by making it a history table.
