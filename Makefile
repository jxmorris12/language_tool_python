.PHONY: default check test doc publish

default:
	@echo "Usage: make [check|test|doc|publish]"
	@exit 1

check:
	uvx ruff@0.14.5 check .
	uvx ruff@0.14.5 format --check .
	uvx mypy@1.18.2

test:
	pytest
	uvx --with defusedxml genbadge coverage --input-file coverage.xml --silent
doc:
	source ./.venv/bin/activate && uv run sphinx-apidoc -o docs/source/references language_tool_python
	source ./.venv/bin/activate && cd ./docs && make html

publish:
	rm -rf dist/ language_tool_python.egg-info/
	uv build
	uvx twine check dist/*
	uv publish
