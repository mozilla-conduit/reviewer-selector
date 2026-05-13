.PHONY: build
build:
	docker build -f docker/Dockerfile -t reviewer-selector .

.PHONY: format
format:
	uv run ruff format
	uv run ruff check --fix
