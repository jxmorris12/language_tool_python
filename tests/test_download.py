"""Tests for the download/language functionality of LanguageTool."""

import pytest

from language_tool_python.exceptions import LanguageToolError


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
