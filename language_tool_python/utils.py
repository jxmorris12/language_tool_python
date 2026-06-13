"""Utility functions for the LanguageTool library."""

from __future__ import annotations

import contextlib
import locale
import logging
import math
import os
import urllib.parse
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, runtime_checkable

import psutil

from .exceptions import PathError

if TYPE_CHECKING:
    from .match import Match

logger = logging.getLogger(__name__)

JAR_NAMES = [
    "languagetool-server.jar",
    "LanguageTool.jar",
]
FAILSAFE_LANGUAGE = "en"

LTP_PATH_ENV_VAR = "LTP_PATH"  # LanguageTool download path

# Directory containing the LanguageTool jar file:
LTP_JAR_DIR_PATH_ENV_VAR = "LTP_JAR_DIR_PATH"


def parse_url(url_str: str) -> str:
    """Parse the given URL string and ensure it has a scheme.

    If the input URL string does not contain 'http', 'http://' is prepended to it. The
    function then parses the URL and returns its canonical form.

    :param url_str: The URL string to be parsed.
    :type url_str: str
    :return: The parsed URL in its canonical form.
    :rtype: str
    """
    if "http" not in url_str:
        url_str = "http://" + url_str

    return urllib.parse.urlparse(url_str).geturl()


def get_env_int(env_var: str, default: int) -> int:
    """Read a positive integer from the environment.

    :param env_var: Environment variable name.
    :type env_var: str
    :param default: Value to use when the environment variable is absent.
    :type default: int
    :return: Configured integer value, or the default.
    :rtype: int
    :raises PathError: If the configured value is invalid.
    """
    configured = os.environ.get(env_var)

    if configured is None:
        return default

    try:
        value = int(configured)
    except ValueError as e:
        err = f"Invalid integer configured by {env_var}: {configured!r}."
        raise PathError(err) from e

    if value <= 0:
        err = f"Invalid integer configured by {env_var}: {configured!r}."
        raise PathError(err)

    return value


def get_env_float(env_var: str, default: float) -> float:
    """Read a positive float from the environment.

    :param env_var: Environment variable name.
    :type env_var: str
    :param default: Value to use when the environment variable is absent.
    :type default: float
    :return: Configured float value, or the default.
    :rtype: float
    :raises PathError: If the configured value is invalid.
    """
    configured = os.environ.get(env_var)

    if configured is None:
        return default

    try:
        value = float(configured)
    except ValueError as e:
        err = f"Invalid float configured by {env_var}: {configured!r}."
        raise PathError(err) from e

    if not math.isfinite(value) or value <= 0:
        err = f"Invalid float configured by {env_var}: {configured!r}."
        raise PathError(err)

    return value


class TextStatus(Enum):
    """Status classification for matches."""

    CORRECT = "correct"
    FAULTY = "faulty"
    GARBAGE = "garbage"


def classify_matches(matches: list[Match]) -> TextStatus:
    """Classify matches as CORRECT, FAULTY, or GARBAGE.

    This function checks the status of the matches and returns a corresponding
    ``TextStatus`` value.

    :param matches: A list of Match objects to be classified.
    :type matches: list[Match]
    :return: The classification of the matches as a ``TextStatus`` value.
    :rtype: TextStatus
    """
    if not len(matches):
        return TextStatus.CORRECT
    matches = [match for match in matches if match.replacements]
    if not matches:
        return TextStatus.GARBAGE
    return TextStatus.FAULTY


def correct(text: str, matches: list[Match]) -> str:
    """Corrects the given text based on the provided matches.

    Only the first replacement for each match is applied to the text.

    :param text: The original text to be corrected.
    :type text: str
    :param matches: A list of Match objects that contain the positions and replacements
        for errors in the text.
    :type matches: list[Match]
    :return: The corrected text.
    :rtype: str
    """
    ltext = list(text)
    matches = [match for match in matches if match.replacements]
    errors = [
        ltext[match.offset : match.offset + match.error_length] for match in matches
    ]
    correct_offset = 0
    for n, match in enumerate(matches):
        frompos, topos = (
            correct_offset + match.offset,
            correct_offset + match.offset + match.error_length,
        )
        if ltext[frompos:topos] != errors[n]:
            continue
        repl = match.replacements[0]
        ltext[frompos:topos] = list(repl)
        correct_offset += len(repl) - len(errors[n])
    return "".join(ltext)


def get_language_tool_download_path() -> Path:
    """Get the download path for LanguageTool.

    This function retrieves the download path for LanguageTool from the environment
    variable specified by ``LTP_PATH_ENV_VAR``. If the environment variable is not set,
    it defaults to a path in the user's home directory under
    ``.cache/language_tool_python``. The function ensures that the directory exists
    before returning it.

    :return: The download path for LanguageTool.
    :rtype: Path
    """
    # Get download path from environment or use default.
    path_str = os.environ.get(
        LTP_PATH_ENV_VAR,
        str(Path.home() / ".cache" / "language_tool_python"),
    )
    path = Path(path_str)
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_locale_language() -> str:
    """Get the current locale language.

    This function retrieves the current locale language setting of the system. It first
    attempts to get the locale using ``locale.getlocale()``. If that fails, it falls
    back to using ``locale.getdefaultlocale()``. If both methods fail to provide a valid
    language code, it returns a default failsafe language code.

    :return: The language code of the current locale.
    :rtype: str
    """
    return locale.getlocale()[0] or locale.getdefaultlocale()[0] or FAILSAFE_LANGUAGE


def kill_process_force(
    *,
    pid: int | None = None,
    proc: psutil.Process | None = None,
) -> None:
    """Terminate a process and all of its child processes forcefully.

    This function attempts to kill a process specified either by its PID or by a
    psutil.Process object. If the process has any child processes, they will be killed
    first.

    :param pid: The process ID of the process to be killed. Either ``pid`` or ``proc``
        must be provided.
    :type pid: int | None
    :param proc: A psutil.Process object representing the process to be killed. Either
        ``pid`` or ``proc`` must be provided.
    :type proc: psutil.Process | None
    :raises ValueError: If neither ``pid`` nor ``proc`` is provided.
    """
    if not any([pid, proc]):
        err = "Must pass either pid or proc"
        raise ValueError(err)
    try:
        proc = psutil.Process(pid) if proc is None else proc
    except psutil.NoSuchProcess:
        logger.debug("Process %s does not exist, nothing to kill", pid)
        return
    logger.debug("Killing process %s and its children", proc.pid)
    for child in proc.children(recursive=True):
        with contextlib.suppress(psutil.NoSuchProcess):
            logger.debug("Killing child process %s", child.pid)
            child.kill()
    with contextlib.suppress(psutil.NoSuchProcess):
        proc.kill()


@runtime_checkable
class SupportsBool(Protocol):
    """Protocol for types that can be converted to a boolean value."""

    def __bool__(self) -> bool:
        """Define the interface for types that can be evaluated in a boolean context."""
        ...


def version_tuple(v: str) -> tuple[int, int]:
    """Convert a version string into a tuple of integers.

    This function takes a version string in the format 'X.Y' and converts it into a
    tuple of integers (X, Y). This can be useful for comparing version numbers.

    :param v: The version string to be converted, expected in the format 'X.Y'.
    :type v: str
    :return: A tuple of integers representing the version, in the format (X, Y).
    :rtype: tuple[int, int]
    :raises ValueError: If the version string is not in the expected format or contains
     non-integer components.
    """
    major, minor = v.split(".")
    return int(major), int(minor)
