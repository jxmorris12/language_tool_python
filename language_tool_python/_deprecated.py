"""Provide a deprecated decorator for marking functions or classes as deprecated.

It first attempts to import the deprecated decorator from the warnings module, available
in Python 3.13 and later. If the import fails (indicating an earlier Python version), it
defines a custom deprecated decorator. The decorator from warnings issues a
DeprecationWarning when the decorated object is used during runtime, and triggers static
linters to flag the usage as deprecated. The custom decorator also issues a
DeprecationWarning when the decorated object is used, but does not trigger static
linters.
"""

from __future__ import annotations

try:
    from warnings import deprecated  # type: ignore [attr-defined, unused-ignore]
except ImportError:
    import functools
    from collections.abc import Callable
    from typing import TypeVar, cast
    from warnings import warn

    F = TypeVar("F", bound=Callable[..., object])

    def deprecated(  # type: ignore [no-redef, unused-ignore]
        message: str,
        /,
        *,
        category: type[Warning] | None = DeprecationWarning,
        stacklevel: int = 1,
    ) -> Callable[[F], F]:
        """Indicate that a function is deprecated."""

        def decorator(func: F) -> F:
            @functools.wraps(func)
            def wrapper(*args: object, **kwargs: object) -> object:
                warn(message, category=category, stacklevel=stacklevel)
                return func(*args, **kwargs)

            return cast("F", wrapper)

        return decorator


__all__ = ["deprecated"]
