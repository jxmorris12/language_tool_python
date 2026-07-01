"""Compatibility helpers for Python-version-dependent imports.

This module centralizes the fallback imports used across the package:

- ``deprecated``: built-in ``warnings.deprecated`` on Python 3.13+, otherwise
  ``typing_extensions.deprecated``.
- ``toml_loads``: built-in ``tomllib.loads`` on Python 3.11+, otherwise
  ``tomli.loads``.
"""

import sys

if sys.version_info >= (3, 11):
    from tomllib import loads as toml_loads
else:
    # Python < 3.11 fallback, cov CI runs on 3.11+, so this branch is never executed.
    from tomli import loads as toml_loads  # pragma: no cover

if sys.version_info >= (3, 13):
    from warnings import deprecated
else:
    # Python < 3.13 fallback, cov CI runs on 3.13+, so this branch is never executed.
    from typing_extensions import deprecated  # pragma: no cover

__all__ = ["deprecated", "toml_loads"]
