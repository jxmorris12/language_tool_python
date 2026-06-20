"""Tests for the command-line interface (CLI) functionality."""

import io
import sys
from collections.abc import Generator

import pytest

import language_tool_python
from language_tool_python.__main__ import main


@pytest.mark.parametrize(
    ("argv", "stdin", "should_succeed"),
    [
        (["-l", "en-US", "-"], "This is okay.\n", True),
        (["-l", "en-US", "-"], "This is noot okay.\n", False),
        (
            ["-l", "en-US", "--enabled-only", "--enable=MORFOLOGIK_RULE_EN_US", "-"],
            "This is okay.\n",
            True,
        ),
        (
            ["-l", "en-US", "--enabled-only", "--enable=MORFOLOGIK_RULE_EN_US", "-"],
            "This is noot okay.\n",
            False,
        ),
        (["-l", "en-US", "-"], "These are “smart” quotes.\n", True),
        (["-l", "en-US", "-"], 'These are "dumb" quotes.\n', True),
        (
            ["-l", "en-US", "--enabled-only", "--enable=EN_QUOTES", "-"],
            'These are "dumb" quotes.\n',
            True,
        ),
        (
            ["-l", "en-US", "--enabled-only", "--enable=EN_UNPAIRED_BRACKETS", "-"],
            'These are "dumb" quotes.\n',
            True,
        ),
        (["-l", "en-US", "--ignore-lines=^#", "-"], '# These are "dumb".\n', True),
    ],
)
def test_cli_exit_codes(
    argv: list[str],
    stdin: str,
    should_succeed: bool,
) -> None:
    """Test the CLI exit codes with various command-line arguments and inputs.

    This test verifies that the command-line interface returns the correct exit codes (0
    for success, non-zero for errors) based on different configurations and input texts.

    :param argv: Command-line arguments to pass to the CLI.
    :param stdin: Input text to be checked for errors.
    :param should_succeed: Expected outcome (True if no errors expected, False
        otherwise).
    :raises AssertionError: If the exit code does not match the expected outcome.
    """
    code = main_with_stdin(argv, stdin)

    if should_succeed:
        assert code == 0
    else:
        assert code != 0


@pytest.fixture(scope="module")
def remote_server() -> Generator[tuple[str, int], None, None]:
    """Fixture that provides a remote LanguageTool server for testing.

    This fixture initializes a LanguageTool instance and yields its host and port,
    ensuring proper cleanup after all tests in the module complete.

    :return: A tuple containing the server host and port (host, port).
    :rtype: Generator[Tuple[str, int], None, None]
    """
    with language_tool_python.LanguageTool("en-US") as tool:
        host = tool._host
        port = tool._port
        yield host, port


def test_cli_remote_ok(remote_server: tuple[str, int]) -> None:
    """Test the CLI with a remote server using valid input text.

    This test verifies that the CLI correctly communicates with a remote LanguageTool
    server and returns a success exit code when the input text contains no errors.

    :param remote_server: Tuple containing the remote server host and port.
    :raises AssertionError: If the exit code is not 0 (success).
    """
    host, port = remote_server

    code = main_with_stdin(
        [
            "-l",
            "en-US",
            "--remote-host",
            host,
            "--remote-port",
            str(port),
            "-",
        ],
        "This is okay.\n",
    )
    assert code == 0


def test_cli_remote_error(remote_server: tuple[str, int]) -> None:
    """Test the CLI with a remote server using text containing errors.

    This test verifies that the CLI correctly communicates with a remote LanguageTool
    server and returns a non-zero exit code when the input text contains errors.

    :param remote_server: Tuple containing the remote server host and port.
    :raises AssertionError: If the exit code is 0 (should be non-zero for errors).
    """
    host, port = remote_server

    code = main_with_stdin(
        [
            "-l",
            "en-US",
            "--remote-host",
            host,
            "--remote-port",
            str(port),
            "-",
        ],
        "This is noot okay.\n",
    )
    assert code != 0


def main_with_stdin(argv: list[str], stdin: str) -> int:
    """Execute the main CLI with simulated stdin input.

    This utility function temporarily replaces sys.stdin with a StringIO object
    containing the provided input, executes the main CLI function, and then restores the
    original stdin.

    :param argv: Command-line arguments to pass to the main function.
    :param stdin: Input text to simulate as stdin.
    :return: Exit code returned by the main function.
    :rtype: int
    """
    old_stdin = sys.stdin
    sys.stdin = io.StringIO(stdin)
    try:
        return main(argv)
    finally:
        sys.stdin = old_stdin
