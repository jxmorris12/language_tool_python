@echo off

where uv >nul 2>nul
if errorlevel 1 (
    echo uv not found. Install uv to use make.bat targets:
    echo powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    exit /b 1
)

if "%1"=="install" goto install
if "%1"=="format" goto format
if "%1"=="fix" goto fix
if "%1"=="ruff-check" goto ruff-check
if "%1"=="mypy-check" goto mypy-check
if "%1"=="check" goto check
if "%1"=="test" goto test
if "%1"=="doc" goto doc
if "%1"=="publish" goto publish

echo Usage: make.bat [install^|format^|fix^|ruff-check^|mypy-check^|check^|test^|doc^|publish]
exit /b 1

:install
uv sync --all-groups --locked
exit /b %errorlevel%

:format
uv run --group quality --locked ruff format
exit /b %errorlevel%

:fix
uv run --group quality --locked ruff check --fix
exit /b %errorlevel%

:ruff-check
uv run --group quality --locked ruff check
if errorlevel 1 exit /b %errorlevel%

uv run --group quality --locked ruff format --check
exit /b %errorlevel%

:mypy-check
uv run --group tests --group types --group quality --locked mypy
exit /b %errorlevel%

:check
call :ruff-check
if errorlevel 1 exit /b %errorlevel%
call :mypy-check
exit /b %errorlevel%

:test
uv run --group tests --locked pytest
if errorlevel 1 exit /b %errorlevel%

uvx --with defusedxml genbadge coverage --input-file coverage.xml --silent
exit /b %errorlevel%

:doc
call uv run --group docs --locked sphinx-apidoc -o docs\source\references language_tool_python
if errorlevel 1 exit /b %errorlevel%

call uv run --group docs --locked sphinx-build -M html docs/source docs/build
exit /b %errorlevel%

:publish
if exist dist\ rmdir /s /q dist\

uv build
if errorlevel 1 exit /b %errorlevel%

uvx twine check .\dist\*
if errorlevel 1 exit /b %errorlevel%

uv publish
exit /b %errorlevel%
