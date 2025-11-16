.PHONY: default check test doc

default:
	@echo "Usage: make [check|test|doc]"
	@exit 1

check:
	uvx ruff@0.14.5 check .
	uvx ruff@0.14.5 format --check .
	uvx mypy@1.18.2

test:
	pytest

doc:
	source ./.venv/bin/activate && uv run sphinx-apidoc -o docs/source/references language_tool_python
	source ./.venv/bin/activate && cd ./docs && make html