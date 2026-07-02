.PHONY: default install format fix ruff-check mypy-check check benchmark-test integration-test property-test unit-test test doc publish clean

UV := $(shell command -v uv 2>/dev/null || true)
ifeq ($(UV),)
$(warning uv not found. Install uv (curl -LsSf https://astral.sh/uv/install.sh | sh) to use Makefile targets)
endif

default:
	@echo "Usage: make [install|format|fix|ruff-check|mypy-check|check|benchmark-test|integration-test|property-test|unit-test|test|doc|publish|clean]"
	@exit 1

install:
	uv sync --all-groups --locked

format:
	uv run --group quality --locked ruff format

fix:
	uv run --group quality --locked ruff check --fix

ruff-check:
	uv run --group quality --locked ruff check
	uv run --group quality --locked ruff format --check

mypy-check:
	uv run --group tests --group types --group quality --locked mypy

check:
	make ruff-check
	make mypy-check

benchmark-test:
	uv run --group tests --locked pytest -m perf

integration-test:
	uv run --group tests --locked pytest -m integration

property-test:
	uv run --group tests --locked pytest -m property

unit-test:
	uv run --group tests --locked pytest -m unit

test:
	uv run --group tests --locked pytest

doc:
	uv run --group docs --locked sphinx-build -M html docs/source docs/build

publish:
	make clean
	uv build
	uvx twine check dist/*
	uv publish

clean:
	git clean -xfd --exclude .venv
