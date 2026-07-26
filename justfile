service_id := "74417c7b-a742-4159-b8df-9f8e966ce040"
project_id := "2dabe0de-e44f-426d-9ef1-abb6afe2b4f6"

default: fmt lint test

run:
    uv run uvicorn dashski.main:app --reload

# one-time: link this dir to the existing Railway project (fresh clone / new machine)
link:
    railway link {{project_id}}

# rebuild image from Dockerfile and upload current code
deploy:
    railway up --service dashski

# deploy, then tail logs for the new deployment
deploy-watch: deploy
    railway logs --service {{service_id}} --deployment

# project/service overview
status:
    railway status

# recent app logs
logs:
    railway logs --service {{service_id}} --deployment

# restart the current image without rebuilding (env var change, volume attach, crash recovery)
redeploy:
    railway redeploy --service {{service_id}} --yes

# extend stored advisory history back N days per region; repeatable, resumes where it stopped
backfill days="30":
    uv run python -m dashski.backfill --days {{days}}

# what a backfill would store, without writing
backfill-dry days="30":
    uv run python -m dashski.backfill --days {{days}} --dry-run

# same, against the deployed db on the Railway volume
backfill-prod days="30" delay=".10":
    railway ssh --service {{service_id}} -- python -m dashski.backfill --days {{days}} --delay {{delay}}

# nuke the on-disk sqlite db (volume) and restart so it's recreated fresh
db-reset:
    railway ssh --service {{service_id}} -- rm -fv /app/data/dashski.db
    railway redeploy --service {{service_id}} --yes

# confirm the data volume is attached
volumes:
    railway volume list --json

# show/create the public domain
domain:
    railway domain --service {{service_id}}

test:
    uv run pytest

lint:
    uv run ruff check
    uv run pyrefly check
    uv run djlint src/dashski/templates

fmt:
    uv run ruff format
    uv run djlint --reformat src/dashski/templates

# concise fmt+lint+test output for AI agents: one line per step, full output only on failure
ci-ai:
    #!/usr/bin/env bash
    set -uo pipefail
    fail=0
    step() {
        local name="$1"; shift
        local out
        if out=$("$@" 2>&1); then
            echo "$name: ok"
        else
            echo "$name: FAIL"
            echo "$out"
            fail=1
        fi
    }
    step fmt        uv run ruff format --quiet
    step fmt-html   uv run djlint --reformat --quiet src/dashski/templates
    step lint       uv run ruff check --quiet
    step types      uv run pyrefly check
    step lint-html  uv run djlint src/dashski/templates
    step test       uv run pytest -q
    exit $fail
