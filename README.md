# dashski

A hello-world dashboard built with FastAPI and HTMX. The server renders the page
and a couple of small HTML fragments; buttons swap those fragments in over HTMX
with no client-side JavaScript framework.

## Requirements

- Python 3.14+
- [uv](https://docs.astral.sh/uv/)

## Setup

```
uv sync
```

## Run

```
uv run uvicorn dashski.main:app --reload
```

Then open http://127.0.0.1:8000.

## Test

```
uv run pytest
```

## Lint & type check

```
uv run ruff check
uv run pyrefly check
```
