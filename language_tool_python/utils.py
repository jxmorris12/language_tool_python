import http.client
import glob
import locale
import os
import re
import sys
import urllib.parse
import urllib.request

from .backports import subprocess
from .match import Match
from .which import which

JAR_NAMES = [
    'languagetool-server.jar',
    'languagetool-standalone*.jar',  # 2.1
    'LanguageTool.jar',
    'LanguageTool.uno.jar'
]
FAILSAFE_LANGUAGE = 'en'

# https://mail.python.org/pipermail/python-dev/2011-July/112551.html
USE_URLOPEN_RESOURCE_WARNING_FIX = (3, 1) < sys.version_info < (3, 4)

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

cache = {}

def parse_url(url_str):
    """ Parses a URL string, and adds 'http' if necessary. """
    if 'http' not in url_str:
        url_str = 'http://' + url_str   

    return urllib.parse.urlparse(url_str).geturl()

def correct(text: str, matches: [Match]) -> str:
    """Automatically apply suggestions to the text."""
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

def get_language_tool_download_path():
    # Get download path from environment or use default.
    download_path = os.environ.get(
        'LTP_PATH',
        os.path.join(os.path.expanduser("~"), ".cache", "language_tool_python")
    )
    # Make download path, if it doesn't exist.
    os.makedirs(download_path, exist_ok=True)
    return download_path

def get_language_tool_directory():
    """Get LanguageTool directory."""
    download_folder = get_language_tool_download_path()
    assert os.path.isdir(download_folder)
    language_tool_path_list = [
        path for path in
        glob.glob(os.path.join(download_folder, 'LanguageTool*'))
        if os.path.isdir(path)
    ]

    if not len(language_tool_path_list):
        raise FileNotFoundError('LanguageTool not found in {}.'.format(download_folder))

    return max(language_tool_path_list)


def get_server_cmd(port=None):
    try:
        cmd = cache['server_cmd']
    except KeyError:
        java_path, jar_path = get_jar_info()
        cmd = [java_path, '-cp', jar_path,
               'org.languagetool.server.HTTPServer']
        cache['server_cmd'] = cmd
    return cmd if port is None else cmd + ['-p', str(port)]


def get_jar_info():
    try:
        java_path, jar_path = cache['jar_info']
    except KeyError:
        java_path = which('java')
        if not java_path:
            raise JavaError("can't find Java")
        dir_name = get_language_tool_directory()
        jar_path = None
        for jar_name in JAR_NAMES:
            for jar_path in glob.glob(os.path.join(dir_name, jar_name)):
                if os.path.isfile(jar_path):
                    break
            else:
                jar_path = None
            if jar_path:
                break
        else:
            raise PathError("can't find languagetool-standalone in {!r}"
                            .format(dir_name))
        cache['jar_info'] = java_path, jar_path
    return java_path, jar_path


def get_locale_language():
    """Get the language code for the current locale setting."""
    return locale.getlocale()[0] or locale.getdefaultlocale()[0]


if USE_URLOPEN_RESOURCE_WARNING_FIX:
    class ClosingHTTPResponse(http.client.HTTPResponse):

        def __init__(self, sock, *args, **kwargs):
            super().__init__(sock, *args, **kwargs)
            self._socket_close = sock.close

        def close(self):
            super().close()
            self._socket_close()

    class ClosingHTTPConnection(http.client.HTTPConnection):
        response_class = ClosingHTTPResponse

    class ClosingHTTPHandler(urllib.request.HTTPHandler):

        def http_open(self, req):
            return self.do_open(ClosingHTTPConnection, req)

    urlopen = urllib.request.build_opener(ClosingHTTPHandler).open

else:
    try:
        urllib.response.addinfourl.__exit__
    except AttributeError:
        from contextlib import closing

        def urlopen(*args, **kwargs):
            return closing(urllib.request.urlopen(*args, **kwargs))
    else:
        urlopen = urllib.request.urlopen
