.PHONY: setup run test lint format warm evaluate
setup:
	uv sync --locked
run:
	uv run uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000
test:
	uv run pytest -q
lint:
	uv run ruff check app tests scripts
	uv run ruff format --check app tests scripts
format:
	uv run ruff format app tests scripts
warm:
	uv run python scripts/preflight.py --warm-embeddings --check-provider
evaluate:
	uv run python scripts/evaluate.py
