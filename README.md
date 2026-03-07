# `language_tool_python`: Python wrapper for LanguageTool

[![language tool python on pypi](https://badge.fury.io/py/language-tool-python.svg)](https://pypi.org/project/language-tool-python/)
[![Documentation Status](https://readthedocs.org/projects/language-tool-python/badge/?version=latest)](https://language-tool-python.readthedocs.io/en/latest/)
[![Test with PyTest](https://github.com/jxmorris12/language_tool_python/workflows/Test%20with%20PyTest/badge.svg)](https://github.com/jxmorris12/language_tool_python/actions)
[![Coverage Status](https://raw.githubusercontent.com/jxmorris12/language_tool_python/master/coverage-badge.svg)](https://github.com/jxmorris12/language_tool_python/actions)
[![Downloads](https://static.pepy.tech/badge/language-tool-python)](https://pepy.tech/project/language-tool-python)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
[![Contributions Welcome](https://img.shields.io/badge/contributions-welcome-brightgreen.svg?style=flat)](https://github.com/jxmorris12/language_tool_python/pulls)

`language_tool_python` is a Python interface/wrapper to [LanguageTool](https://languagetool.org), an open-source grammar, style, and spell checker.

It can:
- run a local LanguageTool Java server,
- call LanguageTool public API,
- call your own remote LanguageTool server,
- be used from Python code and from a CLI.

Default local download target: `latest` snapshot (currently `6.8-SNAPSHOT`).

## Documentation

- Docs: <https://language-tool-python.readthedocs.io/en/latest/>
- Changelog: [CHANGELOG.md](CHANGELOG.md)
- Contributing: [CONTRIBUTING.md](CONTRIBUTING.md)

## Requirements

- Python `>=3.9` (tested up to 3.14)
- Java (to run local LanguageTool server):
  - LanguageTool `< 6.6`: Java `>=9`
  - LanguageTool `>= 6.6` (default): Java `>=17`

## Installation

```bash
pip install --upgrade language_tool_python
```

## Quick Start

### Local server

```python
import language_tool_python

with language_tool_python.LanguageTool("en-US") as tool:
    text = "A sentence with a error in the Hitchhiker's Guide tot he Galaxy"
    matches = tool.check(text)
    print(matches)
    print(tool.correct(text))
```

### Public LanguageTool API

```python
import language_tool_python

with language_tool_python.LanguageToolPublicAPI("es") as tool:
    matches = tool.check("Se a hecho un esfuerzo.")
    print(matches)
```

### Your own remote LanguageTool server

```python
import language_tool_python

with language_tool_python.LanguageTool(
    "en-US",
    remote_server="https://your-lt-server.example.com",
) as tool:
    print(tool.check("This are bad."))
```

## Constructor Parameters Worth Knowing

### `language_tool_download_version` (local server only)

Use this parameter to force which LanguageTool package is used when running a local server.

```python
import language_tool_python

with language_tool_python.LanguageTool(
    "en-US",
    language_tool_download_version="6.7",
) as tool:
    print(tool.check("This are bad."))
```

Accepted formats:
- `latest` (default): latest snapshot configured by this package (`6.8-SNAPSHOT` at the moment)
- `YYYYMMDD`: snapshot by date (example: `20260201`)
- `X.Y`: release version (example: `6.7`, `4.0`)

Notes:
- Only relevant when using a local server (no `remote_server`).
- Versions below `4.0` are not supported.

### `proxies` (remote server only)

Use this parameter to pass proxy settings to `requests` when calling a remote LanguageTool server.

```python
import language_tool_python

with language_tool_python.LanguageTool(
    "en-US",
    remote_server="https://your-lt-server.example.com",
    proxies={
        "http": "http://proxy.example.com:8080",
        "https": "http://proxy.example.com:8080",
    },
) as tool:
    print(tool.check("This are bad."))
```

Notes:
- `proxies` works only with `remote_server`.
- Passing `proxies` without `remote_server` raises `ValueError`.

## Core Python API

### Check text

```python
matches = tool.check("This is noot okay.")
```

Each item is a `Match` object with these fields:
- `rule_id`
- `message`
- `replacements`
- `offset_in_context`, `context`, `offset`, `error_length`
- `category`, `rule_issue_type`
- `sentence`

### Auto-correct

```python
corrected = tool.correct("This is noot okay.")
# Uses first suggestion for each match
```

### Apply only selected matches

```python
text = "There is a bok on the table."
matches = tool.check(text)

# Keep a specific suggestion for first match
matches[0].select_replacement(2)

patched = language_tool_python.utils.correct(text, matches)
```

### Check only parts matching a regex

```python
matches = tool.check_matching_regions(
    'He said "I has a problem" but she replied "It are fine".',
    r'"[^"]*"',
)
```

### Classify result quality

```python
from language_tool_python.utils import classify_matches

status = classify_matches(tool.check("This is a cats."))
# TextStatus.CORRECT / TextStatus.FAULTY / TextStatus.GARBAGE
```

## Rule and Language Controls

You can tune checks per instance:

```python
tool.language = "en" # Can also be set from constructor (`LanguageTool("en")`)
tool.mother_tongue = "fr" # Can also be set from constructor (`LanguageTool("en", mother_tongue="fr")`)

tool.disabled_rules.update({"MORFOLOGIK_RULE_EN_US"})
tool.enabled_rules.update({"EN_A_VS_AN"})
tool.enabled_rules_only = False

tool.disabled_categories.update({"CASING"})
tool.enabled_categories.update({"GRAMMAR"})

tool.preferred_variants.update({"en-GB"})
tool.picky = True
```

Spellchecking control:

```python
tool.disable_spellchecking()
tool.enable_spellchecking()

# Equivalent to:
tool.disabled_categories.update({"TYPOS"})
tool.disabled_categories.difference_update({"TYPOS"})
```

## Custom Spellings

You can register domain-specific words:

```python
with language_tool_python.LanguageTool(
    "en-US",
    new_spellings=["my_product_name", "my_team_term"],
    new_spellings_persist=False,
) as tool:
    print(tool.check("my_product_name is released"))
```

- `new_spellings_persist=True` (default): keeps words in the local LT spelling file.
- `new_spellings_persist=False`: session-only, words are removed on `close()`.

## Local Server Configuration (`config=`)

For local servers only, pass a config dictionary. Example:

```python
with language_tool_python.LanguageTool(
    "en-US",
    config={
        "cacheSize": 1000,
        "pipelineCaching": True,
        "maxTextLength": 50000,
    },
) as tool:
    print(tool.check("Text to inspect"))
```

Supported keys:
- `maxTextLength`, `maxTextHardLength`, `maxCheckTimeMillis`
- `maxErrorsPerWordRate`, `maxSpellingSuggestions`, `maxCheckThreads`
- `cacheSize`, `cacheTTLSeconds`
- `requestLimit`, `requestLimitInBytes`, `timeoutRequestLimit`, `requestLimitPeriodInSeconds`
- `languageModel`, `fasttextModel`, `fasttextBinary`
- `maxWorkQueueSize`, `rulesFile`, `blockedReferrers`
- `premiumOnly`, `disabledRuleIds`
- `pipelineCaching`, `maxPipelinePoolSize`, `pipelineExpireTimeInSeconds`, `pipelinePrewarming`
- `trustXForwardForHeader`, `suggestionsEnabled`
- spellcheck-only language keys:
  - `lang-<code>`
  - `lang-<code>-dictPath`

Notes:
- `remote_server` and `config` cannot be used together.
- `proxies` can only be used with `remote_server`.

## CLI

Entry point:

```bash
language_tool_python [OPTIONS] FILE [FILE ...]
```

Use `-` as file to read from stdin.

Examples:

```bash
# Check a file
language_tool_python -l en-US README.md

# Check stdin
echo "This are bad." | language_tool_python -l en-US -

# Auto-apply suggestions
language_tool_python -l en-US --apply input.txt

# Use only selected rules
language_tool_python -l en-US --enabled-only --enable MORFOLOGIK_RULE_EN_US input.txt

# Use remote LT server
language_tool_python -l en-US --remote-host 127.0.0.1 --remote-port 8081 input.txt
```

Main options:
- `-l, --language CODE`
- `-m, --mother-tongue CODE`
- `-d, --disable RULES`
- `-e, --enable RULES`
- `--enabled-only`
- `-p, --picky`
- `-a, --apply`
- `-s, --spell-check-off`
- `--ignore-lines REGEX`
- `--remote-host HOST`, `--remote-port PORT`
- `-c, --encoding`
- `--verbose`
- `--version`

Exit codes:
- `0`: no issues
- `2`: issues found

## Environment Variables

- `LTP_PATH`: directory used to store downloaded LanguageTool packages.
    - default: `~/.cache/language_tool_python/`
- `LTP_JAR_DIR_PATH`: use an existing local LanguageTool directory (skip download).
- `LTP_DOWNLOAD_HOST_SNAPSHOT`: override snapshot download host.
    - default: `https://internal1.languagetool.org/snapshots/`
- `LTP_DOWNLOAD_HOST_RELEASE`: override release download host.
    - default: `https://languagetool.org/download/`
- `LTP_DOWNLOAD_HOST_ARCHIVE`: override archive download host.
    - default: `https://languagetool.org/download/archive/`

Example:

```bash
export LTP_PATH=/path/to/cache
export LTP_JAR_DIR_PATH=/path/to/LanguageTool-6.8-SNAPSHOT
```

## Resource Management

When using a local server, prefer a context manager or explicit `close()`:

```python
with language_tool_python.LanguageTool("en-US") as tool:
    ...

# or
tool = language_tool_python.LanguageTool("en-US")
...
tool.close()
```

## Client/Server Pattern

You can run LT on one process/host and connect from another client:

```python
# Server side
server_tool = language_tool_python.LanguageTool("en-US")

# Client side
client_tool = language_tool_python.LanguageTool(
    "en-US",
    remote_server=f"http://127.0.0.1:{server_tool.port}",
)
```

## Error Types

Main exceptions in `language_tool_python.exceptions`:
- `LanguageToolError`
    - `ServerError`
    - `JavaError`
    - `PathError`
    - `RateLimitError`

## Development

```bash
# Install dev dependencies
uv sync --group tests --group docs --group types

# Lint / format / types
uvx ruff@0.14.5 check .
uvx ruff@0.14.5 format .
uvx mypy@1.18.2

# Tests
pytest
```

## License

GPL-3.0-only. See [LICENSE](LICENSE).

## Acknowledgements

This project is based on the original `language-check` project:
<https://github.com/myint/language-check/>
