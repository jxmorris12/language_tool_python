"""LanguageTool through server mode
"""
#   © 2012 spirit <hiddenspirit@gmail.com>
#   https://bitbucket.org/spirit/language_tool/
#
#   This program is free software: you can redistribute it and/or modify it
#   under the terms of the GNU Lesser General Public License as published
#   by the Free Software Foundation, either version 3 of the License,
#   or (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty
#   of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
#   See the GNU Lesser General Public License for more details.
#
#   You should have received a copy of the GNU Lesser General Public License
#   along with this program. If not, see <http://www.gnu.org/licenses/>.

import atexit
import glob
import locale
import os
import re
import socket
import subprocess
import sys
import urllib.parse
import urllib.request
from collections import namedtuple
from contextlib import closing
from functools import total_ordering
from weakref import WeakValueDictionary
try:
    # Deprecated since Python 3.3
    from xml.etree import cElementTree as ElementTree
except ImportError:
    from xml.etree import ElementTree

from .which import which


__all__ = ["LanguageTool", "Error", "get_languages",
           "get_version", "get_version_info",
           "get_language_tool_dir", "set_language_tool_dir"]

FAILSAFE_LANGUAGE = "en"
FIX_SENTENCES = False
LANGUAGE_RE = re.compile(r"^([a-z]{2,3})(?:[_-]([a-z]{2}))?$", re.I)
LANGUAGE_TAGS_MAPPING = {
    "English (Australian)": "en-AU",
    "English (Canadian)": "en-CA",
    "English (GB)": "en-GB",
    "English (New Zealand)": "en-NZ",
    "English (South African)": "en-ZA",
    "English (US)": "en-US",
    "German (Austria)": "de-AT",
    "German (Germany)": "de-DE",
    "German (Swiss)": "de-CH",
    "Portuguese (Brazil)": "pt-BR",
    "Portuguese (Portugal)": "pt-PT",
}

cache = {}


class Error(Exception):
    """LanguageTool Error
    """


class ServerError(Error):
    pass


class Match:
    """Hold information about where a rule matches text.
    """
    _SLOTS = ("fromy", "fromx", "toy", "tox", "frompos", "topos",
              "ruleId", "subId", "msg", "replacements",
              "context", "contextoffset", "errorlength")

    def __init__(self, attrib, language=None):
        for k, v in attrib.items():
            setattr(self, k, int(v) if v.isdigit() else v)
        if not isinstance(self.replacements, list):
            self.replacements = (self.replacements.split("#")
                                 if self.replacements else [])

    def __repr__(self):
        def _ordered_dict_repr():
            return "{{{}}}".format(
                ", ".join(
                    "{!r}: {!r}".format(k, self.__dict__[k])
                    for k in self._SLOTS +
                    tuple(set(self.__dict__).difference(self._SLOTS))
                    if getattr(self, k) is not None
                )
            )

        return "{}({})".format(self.__class__.__name__, _ordered_dict_repr())

    def __getattr__(self, name):
        return None


if FIX_SENTENCES:
    try:
        import translit
    except ImportError:
        translit = None
        import warnings
        warnings.warn("translit package is unavailable", ImportWarning)
    else:
        def fix_sentence(text, language=None):
            text = text.strip()
            if text[0].islower():
                text = text.capitalize()
            if text[-1] not in ".?!…,:;":
                text += "."
            text = translit.upgrade(text, language)
            return text

        class Match(Match):
            def __init__(self, attrib, language=None):
                super().__init__(attrib, language)
                self.msg = fix_sentence(self.msg, language)
                self.replacements = [translit.upgrade(r, language)
                                     for r in self.replacements]


class LanguageTool:
    """Main class used for checking text against different rules
    """
    URL_FORMAT = "http://localhost:{port}/"
    MIN_PORT = 8081
    MAX_PORT = 8083
    TIMEOUT = 30

    port = MIN_PORT
    _server = None
    _instances = WeakValueDictionary()
    _PORT_RE = re.compile(r"port (\d+)", re.I)

    if os.name == "nt":
        _startupinfo = subprocess.STARTUPINFO()
        _startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    else:
        _startupinfo = None

    def __init__(self, language=None, motherTongue=None):
        if not self._server_is_alive():
            while True:
                try:
                    self._start_server()
                    break
                except ServerError:
                    if self.MIN_PORT <= LanguageTool.port < self.MAX_PORT:
                        LanguageTool.port += 1
                    else:
                        raise
        if language is None:
            try:
                self.language = get_locale_language()
            except ValueError:
                self.language = FAILSAFE_LANGUAGE
        else:
            self.language = language
        self.motherTongue = motherTongue
        self._instances[id(self)] = self

    def __del__(self):
        if not self._instances and self._server_is_alive():
            self._terminate_server()

    @property
    def language(self):
        """The language to be used
        """
        return self._language

    @language.setter
    def language(self, language):
        self._language = LanguageTag(language)
        self.enabled = self.disabled = None

    @property
    def motherTongue(self):
        """The user’s mother tongue or None

        The mother tongue may also be used as a source language
        for checking bilingual texts.
        """
        return self._motherTongue

    @motherTongue.setter
    def motherTongue(self, motherTongue):
        self._motherTongue = (None if motherTongue is None
                              else LanguageTag(motherTongue))

    @classmethod
    def _start_server(cls):
        cls.url = cls.URL_FORMAT.format(port=cls.port)
        try:
            server_cmd = get_server_cmd(cls.port)
        except Error:
            pass
        else:
            # Need to PIPE all handles: http://bugs.python.org/issue3905
            cls._server = subprocess.Popen(server_cmd,
                                           stdin=subprocess.PIPE,
                                           stdout=subprocess.PIPE,
                                           stderr=subprocess.PIPE,
                                           universal_newlines=True,
                                           startupinfo=cls._startupinfo)
            match = cls._PORT_RE.search(cls._server.stdout.readline())
            if match:
                port = int(match.group(1))
                if port != cls.port:
                    raise Error("requested port {}, but got {}"
                                .format(cls.port, port))
            else:
                cls._terminate_server()
                cls.err_msg = cls._server.communicate()[1].strip()
                cls._server = None
                match = cls._PORT_RE.search(cls.err_msg)
                if not match:
                    raise Error(cls.err_msg)
                port = int(match.group(1))
                if port != cls.port:
                    raise Error(cls.err_msg)
        if not cls._server:
            params = {"language": FAILSAFE_LANGUAGE, "text": ""}
            data = urllib.parse.urlencode(params).encode()
            try:
                with closing(urllib.request.urlopen(cls.url, data, 10)) as f:
                    tree = ElementTree.parse(f)
            except (urllib.error.URLError, socket.error, socket.timeout) as e:
                raise ServerError("{}: {}".format(cls.url, e))
            root = tree.getroot()
            if root.tag != "matches":
                raise ServerError("unexpected root from {}: {!r}"
                                  .format(cls.url, root.tag))

    @classmethod
    def _server_is_alive(cls):
        return cls._server and cls._server.poll() is None

    @classmethod
    def _terminate_server(cls):
        try:
            cls._server.terminate()
        except OSError:
            pass

    def check(self, text: str, srctext=None) -> [Match]:
        """Tokenize the text into sentences and match those sentences
           against all currently active rules.
        """
        params = {"language": self.language, "text": text}
        if self.motherTongue is not None:
            params["motherTongue"] = self.motherTongue
        if srctext is not None:
            params["srctext"] = srctext
        if self.enabled is not None:
            params["enabled"] = ",".join(self.enabled)
        if self.disabled is not None:
            params["disabled"] = ",".join(self.disabled)
        data = urllib.parse.urlencode(params).encode()
        second_try = False
        try:
            while True:
                try:
                    with closing(
                        urllib.request.urlopen(self.url, data, self.TIMEOUT)
                    ) as f:
                        tree = ElementTree.parse(f)
                    break
                except (urllib.error.URLError, socket.error):
                    if second_try:
                        raise
                    second_try = True
                    self._start_server()
        except (urllib.error.URLError, socket.error, socket.timeout) as e:
            raise Error("{}: {}".format(self.url, e))
        return [Match(e.attrib, self.language) for e in tree.getroot()]

    @classmethod
    def _get_languages(cls):
        second_try = False
        try:
            while True:
                try:
                    url = urllib.parse.urljoin(cls.url, "Languages")
                    with closing(
                        urllib.request.urlopen(url, timeout=cls.TIMEOUT)
                    ) as f:
                        tree = ElementTree.parse(f)
                    break
                except (urllib.error.URLError, socket.error, AttributeError):
                    if second_try:
                        raise
                    second_try = True
                    cls._start_server()
        except (urllib.error.URLError, socket.error, socket.timeout) as e:
            raise Error("{}: {}".format(url, e))
        return {
            LANGUAGE_TAGS_MAPPING.get(e.attrib["name"], e.attrib["abbr"])
            for e in tree.getroot()
        }


@total_ordering
class LanguageTag(str):
    """Language tag supported by LanguageTool
    """
    def __new__(cls, tag):
        # Can’t use super() here because of 3to2.
        return str.__new__(cls, cls._normalize(tag))

    def __eq__(self, other):
        try:
            other = self._normalize(other)
        except ValueError:
            pass
        return str(self) == other

    def __lt__(self, other):
        try:
            other = self._normalize(other)
        except ValueError:
            pass
        return str(self) < other

    @staticmethod
    def _normalize(tag):
        if not tag:
            raise ValueError("empty language tag")
        languages = {l.lower().replace("-", "_"): l for l in get_languages()}
        try:
            return languages[tag.lower().replace("-", "_")]
        except KeyError:
            try:
                return languages[LANGUAGE_RE.match(tag).group(1).lower()]
            except (KeyError, AttributeError):
                raise ValueError("unsupported language: {!r}".format(tag))


def get_version():
    """Get LanguageTool version as a string.
    """
    try:
        return cache["version"]
    except KeyError:
        try:
            # LanguageTool 1.9+
            s = subprocess.check_output(
                get_version_cmd(),
                stdin=subprocess.PIPE, stderr=subprocess.PIPE,
                universal_newlines=True
            )
        except subprocess.CalledProcessError:
            s = get_language_tool_dir()
        match = re.search(r"LanguageTool-?.*?(\S+)$", s)
        if not match:
            raise Error("unexpected version output: {!r}".format(s))
        version = match.group(1)
        cache["version"] = version
    return version


def get_version_info():
    """Get LanguageTool version as a tuple.
    """
    VersionInfo = namedtuple("VersionInfo",
                             ("major", "minor", "micro", "release_level"))
    info_list = get_version().split("-")
    release_level = "" if len(info_list) < 2 else info_list[-1]
    info_list = [int(e) if e.isdigit() else e
                 for e in info_list[0].split(".")][:3]
    info_list += [0] * (3 - len(info_list))
    return VersionInfo(*info_list, release_level=release_level)


def get_languages():
    """Get available languages as a set.
    """
    try:
        languages = cache["languages"]
    except KeyError:
        try:
            languages = LanguageTool._get_languages()
        except Error:
            languages = get_languages_from_dir()
        cache["languages"] = languages
    return languages


def get_languages_from_dir():
    rules_path = os.path.join(get_language_tool_dir(), "rules")
    languages = {fn for fn in os.listdir(rules_path)
                 if os.path.isdir(os.path.join(rules_path, fn)) and
                 LANGUAGE_RE.match(fn)}
    variants = []
    for language in languages:
        d = os.path.join(rules_path, language)
        for fn in os.listdir(d):
            if os.path.isdir(os.path.join(d, fn)) and LANGUAGE_RE.match(fn):
                variants.append(fn)
    languages.update(variants)
    return languages


def get_language_tool_dir():
    """Get LanguageTool directory.
    """
    try:
        language_tool_dir = cache["language_tool_dir"]
    except KeyError:
        def version_key(s):
            return [int(e) if e.isdigit() else e
                    for e in re.split(r"(\d+)", s)]

        def get_lt_dir(base_dir):
            paths = [
                path for path in
                glob.glob(os.path.join(base_dir, "LanguageTool*"))
                if os.path.isdir(path)
            ]
            return max(paths, key=version_key) if paths else None

        base_dir = os.path.dirname(sys.argv[0])
        language_tool_dir = get_lt_dir(base_dir)
        if not language_tool_dir:
            try:
                base_dir = os.path.dirname(os.path.abspath(__file__))
            except NameError:
                pass
            else:
                language_tool_dir = get_lt_dir(base_dir)
            if not language_tool_dir:
                raise Error("can’t find LanguageTool directory in {!r}"
                            .format(base_dir))
        cache["language_tool_dir"] = language_tool_dir
    return language_tool_dir


def set_language_tool_dir(path=None):
    """Set LanguageTool directory.
    """
    terminate_server()
    cache.clear()
    if path:
        cache["language_tool_dir"] = path
        get_jar_info()


def get_server_cmd(port=None):
    try:
        cmd = cache["server_cmd"]
    except KeyError:
        java_path, jar_path = get_jar_info()
        cmd = [java_path, "-cp", jar_path,
               "org.languagetool.server.HTTPServer"]
        cache["server_cmd"] = cmd
    return cmd if port is None else cmd + ["-p", str(port)]


def get_version_cmd():
    try:
        cmd = cache["version_cmd"]
    except KeyError:
        java_path, jar_path = get_jar_info()
        cmd = [java_path, "-jar", jar_path, "--version"]
        cache["version_cmd"] = cmd
    return cmd


def get_jar_info():
    try:
        java_path, jar_path = cache["jar_info"]
    except KeyError:
        java_path = which("java")
        if not java_path:
            raise Error("can’t find Java")
        jar_names = ["LanguageTool.jar", "LanguageTool.uno.jar"]
        for jar_name in jar_names:
            jar_path = os.path.join(get_language_tool_dir(), jar_name)
            if os.path.isfile(jar_path):
                break
        else:
            raise Error("can’t find {!r} in {!r}"
                        .format(jar_names[0], get_language_tool_dir()))
        cache["jar_info"] = java_path, jar_path
    return java_path, jar_path


def get_locale_language():
    """Get the language code for the current locale setting.
    """
    language = locale.getlocale()[0]
    if not language:
        locale.setlocale(locale.LC_ALL, "")
        language = locale.getlocale()[0]
    return language


@atexit.register
def terminate_server():
    """Terminate the server.
    """
    if LanguageTool._server_is_alive():
        LanguageTool._terminate_server()
