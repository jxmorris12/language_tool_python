"""Tests for the deprecated decorator."""

import warnings
from typing import Dict, Optional, Tuple

from language_tool_python._deprecated import deprecated


def test_deprecated_emits_warning() -> None:
    """Test that the deprecated decorator emits a DeprecationWarning."""

    @deprecated("This function is deprecated")  # type: ignore
    def old_function() -> str:
        return "result"

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        result = old_function()

        assert len(w) == 1
        assert issubclass(w[0].category, DeprecationWarning)
        assert "This function is deprecated" in str(w[0].message)
        assert result == "result"


def test_deprecated_with_custom_category() -> None:
    """Test that the deprecated decorator can use a custom warning category."""

    @deprecated("This is a user warning", category=UserWarning)  # type: ignore
    def old_function() -> int:
        return 42

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        result = old_function()

        assert len(w) == 1
        assert issubclass(w[0].category, UserWarning)
        assert "This is a user warning" in str(w[0].message)
        assert result == 42


def test_deprecated_preserves_function_signature() -> None:
    """Test that the deprecated decorator preserves function metadata."""

    @deprecated("Old function")  # type: ignore
    def my_function(x: int, y: int) -> int:
        """Add two numbers."""
        return x + y

    with warnings.catch_warnings(record=True):
        assert my_function.__name__ == "my_function"
        assert my_function.__doc__ is not None
        assert "Add two numbers" in my_function.__doc__
        assert my_function(2, 3) == 5


def test_deprecated_with_multiple_calls() -> None:
    """Test that warning is emitted on each call."""

    @deprecated("Deprecated function")  # type: ignore
    def func() -> str:
        return "value"

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        func()
        func()
        func()

        assert len(w) == 3
        assert all(issubclass(warning.category, DeprecationWarning) for warning in w)


def test_deprecated_with_args_and_kwargs() -> None:
    """Test that deprecated decorator works with functions that have args and kwargs."""

    @deprecated("This function is obsolete")  # type: ignore
    def complex_function(
        a: int, b: int, *args: int, c: Optional[int] = None, **kwargs: int
    ) -> Tuple[int, int, Tuple[int, ...], Optional[int], Dict[str, int]]:
        return (a, b, args, c, kwargs)

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        result = complex_function(1, 2, 3, 4, c=5, d=6, e=7)

        assert len(w) == 1
        assert result == (1, 2, (3, 4), 5, {"d": 6, "e": 7})
