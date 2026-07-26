# Deploy

Dashski runs on [Railway](https://railway.app), built from the repo's `Dockerfile`.
Everything below is done via the `railway` CLI — no dashboard clicking required.

## Stack

- **Build**: `Dockerfile` (multi-stage `uv sync`, base image
  `ghcr.io/astral-sh/uv:python3.14-bookworm-slim`). Railway builder is pinned to
  `DOCKERFILE` in `railway.toml` (Nixpacks doesn't reliably support Python 3.14 yet).
- **Run**: `uvicorn dashski.main:app --host 0.0.0.0 --port $PORT` (Railway injects `$PORT`).
- **Data**: SQLite at `data/dashski.db`, relative to the container's `/app` working
  directory — persisted via a Railway Volume mounted at `/app/data`.
- **Scheduler**: APScheduler runs in-process with the web server (see
  `src/dashski/main.py`'s `lifespan`). No separate worker service.

## Project reference

| Resource     | Value |
|--------------|-------|
| Project      | `dashski` (`2dabe0de-e44f-426d-9ef1-abb6afe2b4f6`) |
| Environment  | `production` (`62e46be6-af15-4ec5-b0f2-9adc10e4aa4b`) |
| Service      | `dashski` (`74417c7b-a742-4159-b8df-9f8e966ce040`) |
| Volume       | `dashski-volume` → mounted at `/app/data`, 500MB |
| Public URL   | https://dashski-production.up.railway.app |

There's no `.railway/` link file checked into the repo, so a fresh clone isn't
linked automatically — see setup below.

## One-time setup (new machine / new contributor)

```
brew install railway
railway login   # opens browser for auth
just link       # links this dir to the existing project (non-interactive, uses project ID)
```

## Deploying code changes

```
just deploy         # railway up --service dashski
just deploy-watch   # deploy, then tail logs for the new deployment
```

Uploads the current directory and rebuilds from `Dockerfile`. There's no
GitHub-connected auto-deploy — pushing to git does nothing on its own; you have
to run `just deploy`.

Do not deploy without asking first. To deploy and confirm it builds, run
`just deploy-watch`.

## Volume / persistence

`dashski-volume` → `/app/data`, 500MB. Without it the SQLite DB sits on the
container's ephemeral disk and every deploy or restart wipes the history the
snapshot slider steps through — check `just volumes` first when the slider has
only one position.

To recreate from scratch on a new service:

```
railway volume add --mount-path /app/data --json   # attaches to the linked service
railway redeploy --service <service-id> --yes      # volume only takes effect after a redeploy
```

`volume add` in CLI 5.26.0 takes **no `--service` flag** — it uses whatever
`railway status` reports as the linked service, so run `just link` first.
Elsewhere `--service` **must be the service ID, not the name** — passing the
name panics in 5.26.0 (`Option::unwrap() on a None value`). Get the ID with:

```
railway list --json   # → services[].node.id
```

## Deduping stored advisories

`run_source` skips identical refetches (ADR 0016), but rows written before that
existed are one-per-fetch. `dashski.dedupe` collapses them; it reports by
default and writes `data/dashski.db.bak` before deleting:

```
railway ssh --service <service-id> -- '/app/.venv/bin/python -m dashski.dedupe'
railway ssh --service <service-id> -- '/app/.venv/bin/python -m dashski.dedupe --apply'
```

`railway ssh` re-joins its arguments and hands them to a remote shell, so local
quoting is stripped — the quotes have to survive as literals. Wrap the whole
remote command in single quotes as above (or `-- sh -c "'a && b'"` when you need
a compound command), or the words scatter into separate arguments.

No `DASHSKI_DB_URL` override is needed: `db.py`'s default path is the relative
`data/dashski.db`, and the container's cwd is `/app`, so it resolves onto the
volume automatically.

## Environment variables

Set with `railway variable --service <service-id> set KEY=VALUE`. None are
currently set (all defaults apply). Available knobs:

- `DASHSKI_DB_URL` — override the SQLite URL (only needed for a non-default mount path).
- `DASHSKI_SCHEDULER=0` — disable the fetch scheduler (e.g. for a debug deploy).

## Constraints

- **Keep replicas at 1.** APScheduler runs per-instance; scaling horizontally
  would duplicate every source fetch.

## Useful commands

```
just status     # project/service overview
just logs       # recent app logs
just redeploy   # restart without rebuilding image
just volumes    # confirm volume is attached
just domain     # show/create the public domain
```
