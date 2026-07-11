default: lint test

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
