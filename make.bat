@echo off

if "%1"=="check" goto check
if "%1"=="test" goto test
if "%1"=="doc" goto doc
if "%1"=="publish" goto publish

echo Usage: make.bat [check^|test^|doc^|publish]
exit /b 1

:check
uvx ruff@0.15.12 check language_tool_python tests
if errorlevel 1 exit /b %errorlevel%

uvx ruff@0.15.12 format --check language_tool_python tests
if errorlevel 1 exit /b %errorlevel%

uvx mypy@2.0.0
exit /b %errorlevel%

:test
pytest
if errorlevel 1 exit /b %errorlevel%

uvx --with defusedxml genbadge coverage --input-file coverage.xml --silent
exit /b %errorlevel%

:doc
uv sync --group tests --group docs --group types

call .venv\Scripts\activate && uv run sphinx-apidoc -o docs\source\references language_tool_python
if errorlevel 1 exit /b %errorlevel%

call .venv\Scripts\activate && call docs\make.bat html
exit /b %errorlevel%

:publish
if exist dist\ rmdir /s /q dist\
if exist language_tool_python.egg-info\ rmdir /s /q language_tool_python.egg-info\

uv build
if errorlevel 1 exit /b %errorlevel%

uvx twine check .\dist\*
if errorlevel 1 exit /b %errorlevel%

uv publish
exit /b %errorlevel%
