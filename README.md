# dashski

A single-page dashboard for South Island (NZ) snow: forecasts, observed weather,
and ski field snow reports, all at a glance.

Sources are fetched periodically by APScheduler (in-process, started with the app),
stored in SQLite via SQLModel, and rendered as self-refreshing HTMX widgets — each
with a freshness/staleness indicator. See `CONTEXT.md` for the domain language and
`docs/adr/` for the key decisions.

**Status: scaffold.** The framework (scheduler → fetch → raw payload → parse →
store → widgets) runs end-to-end; the per-source `fetch()`/`parse()` implementations
in `src/dashski/sources/*_example.py` are `NotImplementedError` stubs. To add a real
source: clone an example module, implement its two methods, register it in
`sources/registry.py`, and replace the skipped test in `tests/sources/`.

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
