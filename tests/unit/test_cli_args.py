"""Unit tests for the CLI argument parser."""

import pytest

from language_tool_python.__main__ import parse_args


def test_parse_args_enabled_only_with_enable_categories() -> None:
    """Test that --enabled-only is accepted with only --enable-categories provided."""
    args = parse_args(["-l", "en-US", "--enabled-only", "-E", "TYPOS", "file.txt"])
    assert args.enabled_only is True
    assert args.enable_categories == {"TYPOS"}


def test_parse_args_enabled_only_rejects_disable_categories() -> None:
    """Test that --enabled-only cannot be combined with --disable-categories.

    :raises SystemExit: Expected, as argparse calls sys.exit on error.
    """
    with pytest.raises(SystemExit):
        parse_args(
            ["-l", "en-US", "--enabled-only", "-e", "RULE", "-D", "TYPOS", "file.txt"]
        )


def test_parse_args_enabled_only_requires_enable_or_enable_categories() -> None:
    """Test that --enabled-only requires at least --enable or --enable-categories.

    :raises SystemExit: Expected, as argparse calls sys.exit on error.
    """
    with pytest.raises(SystemExit):
        parse_args(["-l", "en-US", "--enabled-only", "file.txt"])


def test_parse_args_categories() -> None:
    """Test that --disable-categories and --enable-categories are parsed correctly."""
    args = parse_args(
        ["-l", "en-US", "-D", "TYPOS,GRAMMAR", "-E", "PUNCTUATION", "file.txt"]
    )
    assert args.disable_categories == {"TYPOS", "GRAMMAR"}
    assert args.enable_categories == {"PUNCTUATION"}


def test_parse_args_categories_multiple_flags() -> None:
    """Test that repeated -D/-E flags accumulate into the same set."""
    args = parse_args(
        ["-l", "en-US", "-D", "TYPOS", "-D", "GRAMMAR", "-E", "PUNCTUATION", "file.txt"]
    )
    assert args.disable_categories == {"TYPOS", "GRAMMAR"}
    assert args.enable_categories == {"PUNCTUATION"}
