"""Provide a deprecated decorator for marking functions or classes as deprecated.

If the Python version is 3.13 or higher, it uses the
built-in ``warnings.deprecated`` decorator.
If the Python version is lower than 3.13, it falls back to using the
``typing_extensions.deprecated`` decorator.
"""

import sys

if sys.version_info >= (3, 13):
    from warnings import deprecated
else:
    from typing_extensions import deprecated

__all__ = ["deprecated"]
