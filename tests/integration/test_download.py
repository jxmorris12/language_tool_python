"""Integration tests for LanguageTool download and version management (real network)."""

from datetime import datetime, timedelta, timezone

import pytest

import language_tool_python
from language_tool_python.exceptions import LanguageToolError, PathError


def test_install_inexistent_version() -> None:
    """Test errors when downloading a non-existent LanguageTool version.

    This test verifies that the tool correctly handles invalid version numbers by
    raising a LanguageToolError when trying to initialize with a version that does not
    exist.

    :raises AssertionError: If LanguageToolError is not raised for an invalid version.
    """
    with pytest.raises(LanguageToolError):
        language_tool_python.LanguageTool(language_tool_download_version="0.0")


def test_install_too_old_version() -> None:
    """Test that attempting to download a too-old LanguageTool version raises an error.

    This test verifies that the tool correctly handles versions that are no longer
    supported by raising a PathError when trying to initialize with an outdated version.

    :raises AssertionError: If PathError is not raised for a too-old version.
    """
    with pytest.raises(PathError):
        language_tool_python.LanguageTool(language_tool_download_version="3.9")


def test_install_oldest_supported_version() -> None:
    """Test that downloading the oldest supported LanguageTool version works correctly.

    This test verifies that the tool can successfully download and initialize with the
    oldest version that is still supported.

    :raises AssertionError: If the tool fails to initialize with the oldest supported
        version.
    """
    try:
        with language_tool_python.LanguageTool(
            "en-US",
            language_tool_download_version="4.0",
        ) as tool:
            assert tool.language_tool_download_version == "4.0"
    except LanguageToolError:
        pytest.fail("Failed to download or initialize the oldest supported version.")


def test_install_snapshot_version() -> None:
    """Test that downloading the snapshot version of LanguageTool works correctly.

    This test verifies that the tool can successfully download and initialize with the
    snapshot of yesterday.

    :raises AssertionError: If the tool fails to initialize with the snapshot version.
    """
    try:
        with language_tool_python.LanguageTool(
            "en-US",
            language_tool_download_version=(
                (datetime.now(timezone.utc) - timedelta(days=3)).strftime("%Y%m%d")
            ),
        ) as tool:
            assert tool.language_tool_download_version == (
                datetime.now(timezone.utc) - timedelta(days=3)
            ).strftime("%Y%m%d")
    except LanguageToolError:
        pytest.skip(
            (
                "Failed to download or initialize the snapshot version. This may be "
                "due to a missing snapshot for the expected date."
            ),
        )
