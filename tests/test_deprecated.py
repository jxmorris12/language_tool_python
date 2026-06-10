"""Tests for the deprecated decorator."""

from __future__ import annotations

import warnings

from language_tool_python._compat import deprecated

EXPECTED_CUSTOM_WARNING_RESULT = 42
EXPECTED_FUNCTION_SUM = 5
EXPECTED_WARNING_COUNT = 3


def test_deprecated_emits_warning() -> None:
    """Test that the deprecated decorator emits a DeprecationWarning."""

    @deprecated("This function is deprecated")
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

    @deprecated("This is a user warning", category=UserWarning)
    def old_function() -> int:
        return 42

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        result = old_function()

        assert len(w) == 1
        assert issubclass(w[0].category, UserWarning)
        assert "This is a user warning" in str(w[0].message)
        assert result == EXPECTED_CUSTOM_WARNING_RESULT


def test_deprecated_preserves_function_signature() -> None:
    """Test that the deprecated decorator preserves function metadata."""

    @deprecated("Old function")
    def my_function(x: int, y: int) -> int:
        """Add two numbers."""
        return x + y

    with warnings.catch_warnings(record=True):
        assert my_function.__name__ == "my_function"
        assert my_function.__doc__ is not None
        assert "Add two numbers" in my_function.__doc__
        assert my_function(2, 3) == EXPECTED_FUNCTION_SUM


def test_deprecated_with_multiple_calls() -> None:
    """Test that warning is emitted on each call."""

    @deprecated("Deprecated function")
    def func() -> str:
        return "value"

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        func()
        func()
        func()

        assert len(w) == EXPECTED_WARNING_COUNT
        assert all(issubclass(warning.category, DeprecationWarning) for warning in w)


def test_deprecated_with_args_and_kwargs() -> None:
    """Test that deprecated decorator works with functions that have args and kwargs."""

    @deprecated("This function is obsolete")
    def complex_function(
        a: int,
        b: int,
        *args: int,
        c: int | None = None,
        **kwargs: int,
    ) -> tuple[int, int, tuple[int, ...], int | None, dict[str, int]]:
        return (a, b, args, c, kwargs)

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        result = complex_function(1, 2, 3, 4, c=5, d=6, e=7)

        assert len(w) == 1
        assert result == (1, 2, (3, 4), 5, {"d": 6, "e": 7})
