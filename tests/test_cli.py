"""Tests for the command-line interface (CLI) functionality."""

import io
import sys
from typing import Generator, List, Tuple

import pytest


@pytest.mark.parametrize(  # type: ignore[misc]
    "argv, stdin, should_succeed",
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
    argv: List[str],
    stdin: str,
    should_succeed: bool,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """
    Test the CLI exit codes with various command-line arguments and inputs.
    This test verifies that the command-line interface returns the correct exit codes
    (0 for success, non-zero for errors) based on different configurations and input texts.

    :param argv: Command-line arguments to pass to the CLI.
    :param stdin: Input text to be checked for errors.
    :param should_succeed: Expected outcome (True if no errors expected, False otherwise).
    :param capsys: Pytest fixture for capturing stdout/stderr.
    :raises AssertionError: If the exit code does not match the expected outcome.
    """
    code = main_with_stdin(argv, stdin)

    if should_succeed:
        assert code == 0
    else:
        assert code != 0


@pytest.fixture(scope="module")  # type: ignore[misc]
def remote_server() -> Generator[Tuple[str, int], None, None]:
    """
    Fixture that provides a remote LanguageTool server for testing.
    This fixture initializes a LanguageTool instance and yields its host and port,
    ensuring proper cleanup after all tests in the module complete.

    :return: A tuple containing the server host and port (host, port).
    :rtype: Generator[Tuple[str, int], None, None]
    """
    import language_tool_python

    tool = language_tool_python.LanguageTool("en-US")
    host = tool._host
    port = tool._port

    try:
        yield host, port
    finally:
        tool.close()


def test_cli_remote_ok(remote_server: Tuple[str, int]) -> None:
    """
    Test the CLI with a remote server using valid input text.
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


def test_cli_remote_error(remote_server: Tuple[str, int]) -> None:
    """
    Test the CLI with a remote server using text containing errors.
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


def main_with_stdin(argv: List[str], stdin: str) -> int:
    """
    Helper function to execute the main CLI with simulated stdin input.
    This utility function temporarily replaces sys.stdin with a StringIO object
    containing the provided input, executes the main CLI function, and then
    restores the original stdin.

    :param argv: Command-line arguments to pass to the main function.
    :param stdin: Input text to simulate as stdin.
    :return: Exit code returned by the main function.
    :rtype: int
    """
    from language_tool_python.__main__ import main

    old_stdin = sys.stdin
    sys.stdin = io.StringIO(stdin)
    try:
        return main(argv)
    finally:
        sys.stdin = old_stdin
