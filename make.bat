@echo off

if "%1"=="check" goto check
if "%1"=="test" goto test
if "%1"=="doc" goto doc

echo Usage: make.bat [check^|test^|doc]
exit /b 1

:check
uvx ruff@0.14.5 check .
if errorlevel 1 exit /b %errorlevel%

uvx ruff@0.14.5 format --check .
if errorlevel 1 exit /b %errorlevel%

uvx mypy@1.18.2
exit /b %errorlevel%

:test
pytest
uvx --with defusedxml genbadge coverage --input-file coverage.xml --silent
exit /b %errorlevel%

:doc
uv sync --group tests --group docs --group types
call .venv\Scripts\activate && uv run sphinx-apidoc -o docs\source\references language_tool_python
call .venv\Scripts\activate && call docs\make.bat html
