"""Utility functions for the LanguageTool library."""

from typing import List, Tuple, Optional
from shutil import which

import glob
import locale
import os
import subprocess
import urllib.parse
from enum import Enum
import psutil

from .config_file import LanguageToolConfig
from .match import Match

JAR_NAMES = [
    'languagetool-server.jar',
    'languagetool-standalone*.jar',  # 2.1
    'LanguageTool.jar',
    'LanguageTool.uno.jar'
]
FAILSAFE_LANGUAGE = 'en'

LTP_PATH_ENV_VAR = "LTP_PATH"  # LanguageTool download path

# Directory containing the LanguageTool jar file:
LTP_JAR_DIR_PATH_ENV_VAR = "LTP_JAR_DIR_PATH"

# https://mail.python.org/pipermail/python-dev/2011-July/112551.html

if os.name == 'nt':
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
else:
    startupinfo = None


class LanguageToolError(Exception):
    """
    Exception raised for errors in the LanguageTool library.
    This is a generic exception that can be used to indicate various types of
    errors encountered while using the LanguageTool library.
    """
    pass


class ServerError(LanguageToolError):
    """
    Exception raised for errors that occur when interacting with the LanguageTool server.
    This exception is a subclass of `LanguageToolError` and is used to indicate
    issues such as server startup failures.
    """
    pass


class JavaError(LanguageToolError):
    """
    Exception raised for errors related to the Java backend of LanguageTool.
    This exception is a subclass of `LanguageToolError` and is used to indicate
    issues that occur when interacting with Java, such as Java not being found.
    """
    pass


class PathError(LanguageToolError):
    """
    Exception raised for errors in the file path used in LanguageTool.
    This error is raised when there is an issue with the file path provided
    to LanguageTool, such as the LanguageTool JAR file not being found,
    or a download path not being a valid available file path.
    """
    pass


class RateLimitError(LanguageToolError):
    """
    Exception raised for errors related to rate limiting in the LanguageTool server.
    This exception is a subclass of `LanguageToolError` and is used to indicate
    issues such as exceeding the allowed number of requests to the public API without a key.
    """
    pass


def parse_url(url_str: str) -> str:
    """
    Parse the given URL string and ensure it has a scheme.
    If the input URL string does not contain 'http', 'http://' is prepended to it.
    The function then parses the URL and returns its canonical form.

    :param url_str: The URL string to be parsed.
    :type url_str: str
    :return: The parsed URL in its canonical form.
    :rtype: str
    """
    if 'http' not in url_str:
        url_str = 'http://' + url_str

    return urllib.parse.urlparse(url_str).geturl()


class TextStatus(Enum):
    CORRECT = "correct"
    FAULTY = "faulty"
    GARBAGE = "garbage"


def classify_matches(matches: List[Match]) -> TextStatus:
    """
    Classify the matches (result of a check on a text) into one of three categories:
    CORRECT, FAULTY, or GARBAGE.
    This function checks the status of the matches and returns a corresponding
    `TextStatus` value.

    :param matches: A list of Match objects to be classified.
    :type matches: List[Match]
    :return: The classification of the matches as a `TextStatus` value.
    :rtype: TextStatus
    """
    if not len(matches):
        return TextStatus.CORRECT
    matches = [match for match in matches if match.replacements]
    if not len(matches):
        return TextStatus.GARBAGE
    return TextStatus.FAULTY


def correct(text: str, matches: List[Match]) -> str:
    """
    Corrects the given text based on the provided matches.
    Only the first replacement for each match is applied to the text.

    :param text: The original text to be corrected.
    :type text: str
    :param matches: A list of Match objects that contain the positions and replacements for errors in the text.
    :type matches: List[Match]
    :return: The corrected text.
    :rtype: str
    """
    ltext = list(text)
    matches = [match for match in matches if match.replacements]
    errors = [ltext[match.offset:match.offset + match.errorLength]
              for match in matches]
    correct_offset = 0
    for n, match in enumerate(matches):
        frompos, topos = (correct_offset + match.offset,
                          correct_offset + match.offset + match.errorLength)
        if ltext[frompos:topos] != errors[n]:
            continue
        repl = match.replacements[0]
        ltext[frompos:topos] = list(repl)
        correct_offset += len(repl) - len(errors[n])
    return ''.join(ltext)


def get_language_tool_download_path() -> str:
    """
    Get the download path for LanguageTool.
    This function retrieves the download path for LanguageTool from the environment variable
    specified by `LTP_PATH_ENV_VAR`. If the environment variable is not set, it defaults to
    a path in the user's home directory under `.cache/language_tool_python`.

    :return: The download path for LanguageTool.
    :rtype: str
    """
    # Get download path from environment or use default.
    download_path = os.environ.get(
        LTP_PATH_ENV_VAR,
        os.path.join(os.path.expanduser("~"), ".cache", "language_tool_python")
    )
    return download_path


def find_existing_language_tool_downloads(download_folder: str) -> List[str]:
    """
    Find existing LanguageTool downloads in the specified folder.
    This function searches for directories in the given download folder
    that match the pattern 'LanguageTool*' and returns a list of their paths.

    :param download_folder: The folder where LanguageTool downloads are stored.
    :type download_folder: str
    :return: A list of paths to the existing LanguageTool download directories.
    :rtype: List[str]
    """
    language_tool_path_list = [
        path for path in
        glob.glob(os.path.join(download_folder, 'LanguageTool*'))
        if os.path.isdir(path)
    ]
    return language_tool_path_list


def get_language_tool_directory() -> str:
    """
    Get the directory path of the LanguageTool installation.
    This function checks the download folder for LanguageTool installations,
    verifies that the folder exists and is a directory, and returns the path
    to the latest version of LanguageTool found in the directory.

    :raises NotADirectoryError: If the download folder path is not a valid directory.
    :raises FileNotFoundError: If no LanguageTool installation is found in the download folder.
    :return: The path to the latest version of LanguageTool found in the directory.
    :rtype: str
    """
    
    download_folder = get_language_tool_download_path()
    if not os.path.isdir(download_folder):
        raise NotADirectoryError(f"LanguageTool directory path is not a valid directory {download_folder}.")
    language_tool_path_list = find_existing_language_tool_downloads(
        download_folder
    )

    if not len(language_tool_path_list):
        raise FileNotFoundError(f'LanguageTool not found in {download_folder}.')

    # Return the latest version found in the directory.
    return max(language_tool_path_list)


def get_server_cmd(
    port: Optional[int] = None, config: Optional[LanguageToolConfig] = None
) -> List[str]:
    """
    Generate the command to start the LanguageTool HTTP server.

    :param port: Optional; The port number on which the server should run. If not provided, the default port will be used.
    :type port: Optional[int]
    :param config: Optional; The configuration for the LanguageTool server. If not provided, default configuration will be used.
    :type config: Optional[LanguageToolConfig]
    :return: A list of command line arguments to start the LanguageTool HTTP server.
    :rtype: List[str]
    """
    java_path, jar_path = get_jar_info()
    cmd = [java_path, '-cp', jar_path,
           'org.languagetool.server.HTTPServer']

    if port is not None:
        cmd += ['-p', str(port)]

    if config is not None:
        cmd += ['--config', config.path]

    return cmd


def get_jar_info() -> Tuple[str, str]:
    """
    Retrieve the path to the Java executable and the LanguageTool JAR file.
    This function searches for the Java executable in the system's PATH and 
    locates the LanguageTool JAR file either in a directory specified by an 
    environment variable or in a default download directory.

    :raises JavaError: If the Java executable cannot be found.
    :raises PathError: If the LanguageTool JAR file cannot be found in the specified directory.
    :return: A tuple containing the path to the Java executable and the path to the LanguageTool JAR file.
    :rtype: Tuple[str, str]
    """

    java_path = which('java')
    if not java_path:
        raise JavaError("can't find Java")

    # Use the env var to the jar directory if it is defined
    # otherwise look in the download directory
    jar_dir_name = os.environ.get(
        LTP_JAR_DIR_PATH_ENV_VAR,
        get_language_tool_directory()
    )
    jar_path = None
    for jar_name in JAR_NAMES:
        for jar_path in glob.glob(os.path.join(jar_dir_name, jar_name)):
            if os.path.isfile(jar_path):
                break
        else:
            jar_path = None
        if jar_path:
            break
    else:
        raise PathError(f"can't find languagetool-standalone in {jar_dir_name!r}")
    return java_path, jar_path


def get_locale_language() -> str:
    """
    Get the current locale language.
    This function retrieves the current locale language setting of the system.
    It first attempts to get the locale using `locale.getlocale()`. If that fails,
    it falls back to using `locale.getdefaultlocale()`.

    :return: The language code of the current locale.
    :rtype: str
    """
    return locale.getlocale()[0] or locale.getdefaultlocale()[0]


def kill_process_force(*, pid: Optional[int] = None, proc: Optional[psutil.Process] = None) -> None:
    """
    Forcefully kills a process and all its child processes.
    This function attempts to kill a process specified either by its PID or by a psutil.Process object.
    If the process has any child processes, they will be killed first.

    :param pid: The process ID of the process to be killed. Either `pid` or `proc` must be provided.
    :type pid: Optional[int]
    :param proc: A psutil.Process object representing the process to be killed. Either `pid` or `proc` must be provided.
    :type proc: Optional[psutil.Process]
    :raises AssertionError: If neither `pid` nor `proc` is provided.
    """
    assert any([pid, proc]), "Must pass either pid or proc"
    try:
        proc = psutil.Process(pid) if proc is None else proc
    except psutil.NoSuchProcess:
        return
    for child in proc.children(recursive=True):
        try:
            child.kill()
        except psutil.NoSuchProcess:
            pass
    try:
        proc.kill()
    except psutil.NoSuchProcess:
        pass
