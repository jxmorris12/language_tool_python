from typing import List, Tuple

import glob
import locale
import os
import subprocess
import urllib.parse
import urllib.request

from .config_file import LanguageToolConfig
from .match import Match
from .which import which

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
    pass


class ServerError(LanguageToolError):
    pass


class JavaError(LanguageToolError):
    pass


class PathError(LanguageToolError):
    pass


def parse_url(url_str):
    """ Parses a URL string, and adds 'http' if necessary. """
    if 'http' not in url_str:
        url_str = 'http://' + url_str

    return urllib.parse.urlparse(url_str).geturl()


def _4_bytes_encoded_positions(text: str) -> List[int]:
    """Return a list of positions of 4-byte encoded characters in the text."""
    positions = []
    char_index = 0
    for char in text:
        if len(char.encode('utf-8')) == 4:
            positions.append(char_index)
            # Adding 1 to the index because 4 byte characters are
            # 2 bytes in length in LanguageTool, instead of 1 byte in Python.
            char_index += 1
        char_index += 1
    return positions


def correct(text: str, matches: List[Match]) -> str:
    """Automatically apply suggestions to the text."""
    # Get the positions of 4-byte encoded characters in the text because without 
    # carrying out this step, the offsets of the matches could be incorrect.
    for match in matches:
        match.offset -= sum(1 for i in _4_bytes_encoded_positions(text) if i <= match.offset)
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
    # Get download path from environment or use default.
    download_path = os.environ.get(
        LTP_PATH_ENV_VAR,
        os.path.join(os.path.expanduser("~"), ".cache", "language_tool_python")
    )
    return download_path


def find_existing_language_tool_downloads(download_folder: str) -> List[str]:
    language_tool_path_list = [
        path for path in
        glob.glob(os.path.join(download_folder, 'LanguageTool*'))
        if os.path.isdir(path)
    ]
    return language_tool_path_list


def get_language_tool_directory() -> str:
    """Get LanguageTool directory."""
    download_folder = get_language_tool_download_path()
    if not os.path.isdir(download_folder):
        raise NotADirectoryError(
            "LanguageTool directory path is not a valid directory {}."
            .format(download_folder)
        )
    language_tool_path_list = find_existing_language_tool_downloads(
        download_folder
    )

    if not len(language_tool_path_list):
        raise FileNotFoundError(
            'LanguageTool not found in {}.'.format(download_folder)
        )

    # Return the latest version found in the directory.
    return max(language_tool_path_list)


def get_server_cmd(
        port: int = None, config: LanguageToolConfig = None
) -> List[str]:
    java_path, jar_path = get_jar_info()
    cmd = [java_path, '-cp', jar_path,
           'org.languagetool.server.HTTPServer']

    if port is not None:
        cmd += ['-p', str(port)]

    if config is not None:
        cmd += ['--config', config.path]

    return cmd


def get_jar_info() -> Tuple[str, str]:
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
        raise PathError("can't find languagetool-standalone in {!r}"
                        .format(jar_dir_name))
    return java_path, jar_path


def get_locale_language():
    """Get the language code for the current locale setting."""
    return locale.getlocale()[0] or locale.getdefaultlocale()[0]
