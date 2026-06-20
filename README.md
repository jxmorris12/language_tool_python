# `language_tool_python`: Python wrapper for LanguageTool

[![language tool python on pypi](https://img.shields.io/pypi/v/language-tool-python)](https://pypi.org/project/language-tool-python/)
[![Documentation Status](https://readthedocs.org/projects/language-tool-python/badge/?version=latest)](https://language-tool-python.readthedocs.io/en/latest/)
[![Test with PyTest](https://github.com/jxmorris12/language_tool_python/workflows/Test%20with%20PyTest/badge.svg)](https://github.com/jxmorris12/language_tool_python/actions)
[![Coverage Status](https://codecov.io/gh/jxmorris12/language_tool_python/branch/master/graph/badge.svg)](https://codecov.io/gh/jxmorris12/language_tool_python)
[![Downloads](https://img.shields.io/pypi/dw/language-tool-python)](https://pypistats.org/packages/language-tool-python)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
[![Contributions Welcome](https://img.shields.io/badge/contributions-welcome-brightgreen.svg?style=flat)](https://github.com/jxmorris12/language_tool_python/pulls)

`language_tool_python` is a Python wrapper for [LanguageTool](https://github.com/languagetool-org/languagetool),
a free, multilingual, non-AI, open-source grammar, style, and spell checker. This python wrapper lets you detect and fix errors from
a Python script or from the command line, against a local Java server, the public
LanguageTool API, or your own remote server.

<p align="center">
  <img src="https://raw.githubusercontent.com/jxmorris12/language_tool_python/master/docs/assets/video/language_tool_python_demo.gif" alt="Demo" width="1000">
</p>

## Requirements

- Python `>=3.10` (tested up to 3.15)
- Java `>=17` to run a local LanguageTool server (default download: `6.8`). See the
  [installation docs](https://language-tool-python.readthedocs.io/en/latest/references/installation.html)
  for full Java version details.

## Installation

```bash
pip install --upgrade language_tool_python
```

## Quick Start

### Local server

```python
import language_tool_python

with language_tool_python.LanguageTool("en-US") as tool:
    matches = tool.check("A sentence with a error in the Hitchhiker's Guide tot he Galaxy")

print(len(matches))
# → 2
print(matches[0].message)
# → 'Use "an" instead of "a" if the following word starts with a vowel sound'
print(matches[0].replacements)
# → ['an']
print(matches[0].offset)
# → 16
```

### Public LanguageTool API

```python
import language_tool_python

with language_tool_python.LanguageToolPublicAPI("en-US") as tool:
    matches = tool.check("This are wrong.")

print(len(matches))
# → 2
```

### Your own remote LanguageTool server

```python
import language_tool_python

with language_tool_python.LanguageTool(
    "en-US",
    remote_server="http://my-languagetool-server:8081",
) as tool:
    print(tool.correct("I has a problem."))
    # → I have a problem.
```

### CLI

```bash
echo "This are bad." | language_tool_python -l en-US -
language_tool_python -l en-US --apply input.txt
```

For the full API reference, configuration options, CLI usage, and more examples, see the
[documentation](https://language-tool-python.readthedocs.io/en/latest/).

## Documentation

- **Docs**: <https://language-tool-python.readthedocs.io/en/latest/>
- **Changelog**: [CHANGELOG.md](CHANGELOG.md)
- **Contributing**: [CONTRIBUTING.md](CONTRIBUTING.md)
- **Security**: [SECURITY.md](SECURITY.md)

## Versioning

This project follows [Semantic Versioning](https://semver.org/) (`MAJOR.MINOR.PATCH`):

- **PATCH** - backwards-compatible bug fixes.
- **MINOR** - new backwards-compatible features.
- **MAJOR** - breaking changes. Deprecated APIs are removed at the next major version.

Versions are tagged in the git repository and can be found on [PyPI](https://pypi.org/project/language-tool-python/#history).

## Development

```bash
make install  # Install dev dependencies
make format   # Format code
make check    # Lint / format / types
make test     # Tests
```

## License

GPL-3.0-only. See [LICENSE](LICENSE).

## Acknowledgements

This project is based on the original `language-check` project:
<https://github.com/myint/language-check/>
