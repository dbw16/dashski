# Per-kind reading tables; RawFetch keeps latest only

Each source kind gets its own strongly-typed table (`ForecastReading`,
`ObservationReading`, `SnowReport`) instead of one generic table with a JSON
payload column — snow depth and precipitation probability are different shapes,
and column-level typing/queryability beats schema flexibility here.

Raw payloads are kept for debugging broken parsers, but `RawFetch` holds only
the most recent payload per source (overwritten each run, deliberately not an
append-only log) to stop scraped HTML from bloating the SQLite file. Don't
"fix" this by making it a history table.
