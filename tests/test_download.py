"""Tests for the download/language functionality of LanguageTool."""

import io
from unittest.mock import MagicMock, patch

import pytest

from language_tool_python.download_lt import http_get
from language_tool_python.exceptions import LanguageToolError, PathError


def test_install_inexistent_version() -> None:
    """
    Test that attempting to download a non-existent LanguageTool version raises an error.
    This test verifies that the tool correctly handles invalid version numbers by raising
    a LanguageToolError when trying to initialize with a version that does not exist.

    :raises AssertionError: If LanguageToolError is not raised for an invalid version.
    """
    import language_tool_python

    with pytest.raises(LanguageToolError):
        language_tool_python.LanguageTool(language_tool_download_version="0.0")


def test_inexistent_language() -> None:
    """
    Test that creating a LanguageTag with an invalid language code raises an error.
    This test verifies that the LanguageTag constructor correctly validates language codes
    and raises a ValueError when given a language code that is not supported.

    :raises AssertionError: If ValueError is not raised for an invalid language code.
    """
    import language_tool_python

    with language_tool_python.LanguageTool("en-US") as tool, pytest.raises(ValueError):
        language_tool_python.LanguageTag("xx-XX", tool._get_languages())


def test_http_get_403_forbidden() -> None:
    """
    Test that http_get raises PathError when receiving a 403 Forbidden status code.
    This test verifies that the function correctly handles forbidden access errors
    when attempting to download files.

    :raises AssertionError: If PathError is not raised for a 403 status code.
    """
    mock_response = MagicMock()
    mock_response.status_code = 403
    mock_response.headers = {}

    with (
        patch(
            "language_tool_python.download_lt.requests.get", return_value=mock_response
        ),
        pytest.raises(PathError, match="Access forbidden to URL"),
    ):
        out_file = io.BytesIO()
        http_get("https://example.com/test.zip", out_file)


def test_http_get_other_error_codes() -> None:
    """
    Test that http_get raises PathError for various HTTP error codes (other than 404 and 403).
    This test verifies that the function correctly handles different HTTP error codes
    like 500 (Internal Server Error), 503 (Service Unavailable), etc.

    :raises AssertionError: If PathError is not raised for error status codes.
    """
    error_codes = [500, 502, 503, 504]

    for error_code in error_codes:
        mock_response = MagicMock()
        mock_response.status_code = error_code
        mock_response.headers = {}

        with (
            patch(
                "language_tool_python.download_lt.requests.get",
                return_value=mock_response,
            ),
            pytest.raises(PathError, match=f"Failed to download.*{error_code}"),
        ):
            out_file = io.BytesIO()
            http_get("https://example.com/test.zip", out_file)
