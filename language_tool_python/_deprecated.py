"""
This module provides a deprecated decorator for marking functions or classes as deprecated.
It first attempts to import the deprecated decorator from the warnings module, available in Python 3.13 and later.
If the import fails (indicating an earlier Python version), it defines a custom deprecated decorator.
The decorator from warnings issues a DeprecationWarning when the decorated object is used during runtime,
and triggers static linters to flag the usage as deprecated.
The custom decorator also issues a DeprecationWarning when the decorated object is used, but does not trigger static linters.
"""

try:
    from warnings import deprecated  # type: ignore [attr-defined]
except ImportError:
    import functools
    from typing import Any, Callable, Optional, Type, TypeVar, cast
    from warnings import warn

    F = TypeVar("F", bound=Callable[..., Any])

    def deprecated(
        message: str,
        /,
        *,
        category: Optional[Type[Warning]] = DeprecationWarning,
        stacklevel: int = 1,
    ) -> Callable[[F], F]:
        """Indicate that a function is deprecated."""

        def decorator(func: F) -> F:
            @functools.wraps(func)
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                warn(message, category=category, stacklevel=stacklevel)
                return func(*args, **kwargs)

            return cast(F, wrapper)

        return decorator


__all__ = ["deprecated"]
