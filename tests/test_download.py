"""Tests for the download/language functionality of LanguageTool."""

import io
from unittest.mock import MagicMock, patch

import pytest

from language_tool_python.download_lt import LocalLanguageTool
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


def test_install_too_old_version() -> None:
    """
    Test that attempting to download a too-old LanguageTool version raises an error.
    This test verifies that the tool correctly handles versions that are no longer supported
    by raising a PathError when trying to initialize with an outdated version.

    :raises AssertionError: If PathError is not raised for a too-old version.
    """
    import language_tool_python

    with pytest.raises(PathError):
        language_tool_python.LanguageTool(language_tool_download_version="3.9")


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
        local_language_tool = LocalLanguageTool.from_version_name()
        local_language_tool._get_remote_zip(out_file)


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
            local_language_tool = LocalLanguageTool.from_version_name()
            local_language_tool._get_remote_zip(out_file)


def test_install_oldest_supported_version() -> None:
    """
    Test that downloading the oldest supported LanguageTool version works correctly.
    This test verifies that the tool can successfully download and initialize
    with the oldest version that is still supported.

    :raises AssertionError: If the tool fails to initialize with the oldest supported version.
    """
    import language_tool_python

    try:
        with language_tool_python.LanguageTool(
            "en-US", language_tool_download_version="4.0"
        ) as tool:
            assert tool is not None
    except LanguageToolError:
        pytest.fail("Failed to download or initialize the oldest supported version.")


def test_install_snapshot_version() -> None:
    """
    Test that downloading the snapshot version of LanguageTool works correctly.
    This test verifies that the tool can successfully download and initialize
    with the snapshot of yesterday.

    :raises AssertionError: If the tool fails to initialize with the snapshot version.
    """
    from datetime import datetime, timedelta

    import language_tool_python

    try:
        with language_tool_python.LanguageTool(
            "en-US",
            language_tool_download_version=(
                (datetime.now() - timedelta(days=3)).strftime("%Y%m%d")
            ),
        ) as tool:
            assert tool is not None
    except LanguageToolError:
        pytest.skip(
            "Failed to download or initialize the snapshot version. This may be due to a missing snapshot for the expected date."
        )
