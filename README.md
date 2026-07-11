# dashski

A hello-world dashboard built with FastAPI and HTMX. The server renders the page
and a couple of small HTML fragments; buttons swap those fragments in over HTMX
with no client-side JavaScript framework.

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

Then open http://127.0.0.1:8000.

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
