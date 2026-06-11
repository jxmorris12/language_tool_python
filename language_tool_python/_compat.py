"""Compatibility helpers for Python-version-dependent imports.

This module centralizes the fallback imports used across the package:

- ``deprecated``: built-in ``warnings.deprecated`` on Python 3.13+, otherwise
  ``typing_extensions.deprecated``.
- ``toml_loads``: built-in ``tomllib.loads`` on Python 3.11+, otherwise
  ``tomli.loads``.
- ``TypeGuard``: built-in ``typing.TypeGuard`` on Python 3.10+, otherwise
  ``typing_extensions.TypeGuard``.
"""

import sys

if sys.version_info >= (3, 10):
    from typing import TypeGuard
else:
    from typing_extensions import TypeGuard

if sys.version_info >= (3, 11):
    from tomllib import loads as toml_loads
else:
    from tomli import loads as toml_loads

if sys.version_info >= (3, 13):
    from warnings import deprecated
else:
    from typing_extensions import deprecated

__all__ = ["TypeGuard", "deprecated", "toml_loads"]
