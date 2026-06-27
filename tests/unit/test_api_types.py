"""Unit tests for _internals/api_types.py TypeGuard helpers."""

from language_tool_python._internals.api_types import (
    is_check_response,
    is_language_info,
)


def test_is_language_info_valid() -> None:
    """Accepts a well-formed LanguageInfo dict."""
    assert is_language_info({"code": "en", "longCode": "en-US", "name": "English"})


def test_is_language_info_not_dict() -> None:
    """Rejects non-dict values."""
    assert not is_language_info("not a dict")
    assert not is_language_info(42)
    assert not is_language_info(None)
    assert not is_language_info(["code", "longCode", "name"])


def test_is_language_info_missing_field() -> None:
    """Rejects dicts with missing required fields."""
    assert not is_language_info({"code": "en", "longCode": "en-US"})
    assert not is_language_info({"code": "en", "name": "English"})
    assert not is_language_info({})


def test_is_language_info_wrong_type() -> None:
    """Rejects dicts with non-string field values."""
    assert not is_language_info({"code": 1, "longCode": "en-US", "name": "English"})
    assert not is_language_info({"code": "en", "longCode": None, "name": "English"})


def test_is_check_response_valid() -> None:
    """Accepts a well-formed CheckResponse dict."""
    assert is_check_response(
        {
            "matches": [],
            "language": {"code": "en"},
            "warnings": {"incompleteResults": False},
        }
    )


def test_is_check_response_not_dict() -> None:
    """Rejects non-dict values."""
    assert not is_check_response("not a dict")
    assert not is_check_response(None)
    assert not is_check_response(123)


def test_is_check_response_missing_field() -> None:
    """Rejects dicts with missing required fields."""
    assert not is_check_response({"matches": [], "language": {}})
    assert not is_check_response({"matches": [], "warnings": {}})
    assert not is_check_response({})


def test_is_check_response_wrong_type() -> None:
    """Rejects dicts with wrong field types."""
    assert not is_check_response({"matches": "[]", "language": {}, "warnings": {}})
    assert not is_check_response({"matches": [], "language": "en", "warnings": {}})
    assert not is_check_response({"matches": [], "language": {}, "warnings": "none"})
