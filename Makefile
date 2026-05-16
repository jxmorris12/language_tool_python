.PHONY: default install format fix ruff-check mypy-check check test doc publish

UV := $(shell command -v uv 2>/dev/null || true)
ifeq ($(UV),)
$(warning uv not found. Install uv (curl -LsSf https://astral.sh/uv/install.sh | sh) to use Makefile targets)
endif

default:
	@echo "Usage: make [install|format|fix|ruff-check|mypy-check|check|test|doc|publish]"
	@exit 1

install:
	uv sync --all-groups --locked

format:
	uv run --group quality --locked ruff format language_tool_python tests

fix:
	uv run --group quality --locked ruff check --fix language_tool_python tests

ruff-check:
	uv run --group quality --locked ruff check language_tool_python tests
	uv run --group quality --locked ruff format --check language_tool_python tests

mypy-check:
	@if uv run --locked python -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)'; then \
		uv run --group tests --group types --group quality --locked mypy; \
	else \
		echo "Skipping mypy: Python 3.10 or newer is required."; \
	fi

check:
	make ruff-check
	make mypy-check

test:
	uv run --group tests --locked pytest
	uvx --with defusedxml genbadge coverage --input-file coverage.xml --silent

doc:
	uv run --group docs --locked sphinx-apidoc -o docs/source/references language_tool_python
	uv run --group docs --locked sphinx-build -M html docs/source docs/build

publish:
	rm -rf dist/
	uv build
	uvx twine check dist/*
	uv publish
