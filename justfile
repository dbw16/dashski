default: fmt lint test

run:
    uv run uvicorn dashski.main:app --reload

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
