# dashski

A single-page dashboard of South Island (NZ) avalanche advisories — danger
rating per elevation band, the avalanche problems behind it, and the aspects
they apply to — at a glance. Ski field snow reports were part of this and were
removed; it's an avalanche tool now (ADR 0015).

Sources are fetched periodically by APScheduler (in-process, started with the app),
stored in SQLite via SQLModel, and rendered as self-refreshing HTMX widgets — each
with a freshness/staleness indicator. See `CONTEXT.md` for the domain language and
`docs/adr/` for the key decisions.

The one live source is the NZ Avalanche Advisory (`sources/nzaa_advisory.py`).
To add another: implement `fetch()`/`parse()` per the `Source` protocol in
`sources/base.py`, register it in `sources/registry.py`, and add a test in
`tests/sources/` that feeds a saved payload through `parse()`.

## Requirements

- Python 3.14+
- [uv](https://docs.astral.sh/uv/)
- [just](https://github.com/casey/just)

## Setup

```
uv sync
```

## Run

```
just run
```

Then open http://127.0.0.1:8000. The SQLite file lives at `data/dashski.db`
(override with `DASHSKI_DB_URL`; set `DASHSKI_SCHEDULER=0` to disable fetching).

## Test

```
just test
```

## Lint & type check

```
just lint
```

## Format

```
just fmt
```
