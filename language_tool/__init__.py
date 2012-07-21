"""LanguageTool through server mode
"""
#   © 2012 spirit <hiddenspirit@gmail.com>
#   https://bitbucket.org/spirit/language_tool
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
import http.client
import locale
import os
import re
import socket
import sys
import urllib.parse
import urllib.request
import warnings
from collections import namedtuple, OrderedDict
from functools import total_ordering
from weakref import WeakValueDictionary

try:
    from collections.abc import Sequence
except ImportError:
    from collections import Sequence

try:
    from xml.etree import cElementTree as ElementTree
except ImportError:
    from xml.etree import ElementTree

from .backports import subprocess
from .country_codes import get_country_code
from .which import which


__all__ = ["LanguageTool", "Error", "get_languages", "correct", "get_version",
           "get_directory", "set_directory"]

FAILSAFE_LANGUAGE = "en"
LANGUAGE_RE = re.compile(r"^([a-z]{2,3})(?:[_-]([a-z]{2}))?$", re.I)

# http://mail.python.org/pipermail/python-dev/2011-July/112551.html
USE_URLOPEN_RESOURCE_WARNING_FIX = (3, 1) < sys.version_info < (3, 4)

if os.name == "nt":
    startupinfo = subprocess.STARTUPINFO() #@UndefinedVariable
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW #@UndefinedVariable
else:
    startupinfo = None

cache = {}


class Error(Exception):
    """LanguageTool Error
    """


class ServerError(Error):
    pass


class JavaError(Error):
    pass


class PathError(Error):
    pass


def replacement_list(string, sep="#"):
    if isinstance(string, list):
        return string
    return string.split(sep) if string else []


class Match:
    """Hold information about where a rule matches text.
    """
    _SLOTS = OrderedDict([
        ("fromy", int), ("fromx", int), ("toy", int), ("tox", int),
        ("frompos", int), ("topos", int),
        ("ruleId", str), ("subId", str), ("msg", str),
        ("replacements", replacement_list),
        ("context", str), ("contextoffset", int), ("errorlength", int),
        ("url", str),
    ])
    _frompos_cache, _topos_cache = None, None

    def __init__(self, attrib, text=None):
        for k, v in attrib.items():
            setattr(self, k, v)
        self._lines = text

    def __repr__(self):
        def _ordered_dict_repr():
            slots = list(self._SLOTS.keys())
            attrs = slots + list(set(self.__dict__).difference(slots))
            return "{{{}}}".format(
                ", ".join(
                    "{!r}: {!r}".format(attr, self.__dict__[attr])
                    for attr in attrs
                    if attr in self.__dict__ and not attr.startswith("_")
                )
            )

        return "{}({})".format(self.__class__.__name__, _ordered_dict_repr())

    def __str__(self):
        ruleId = self.ruleId
        if self.subId is not None:
            ruleId += "[{}]".format(self.subId)
        s = "Line {}, column {}, Rule ID: {}".format(
            self.fromy + 1, self.fromx + 1, ruleId)
        if self.msg:
            s += "\nMessage: {}".format(self.msg)
        if self.replacements:
            s += "\nSuggestion: {}".format("; ".join(self.replacements))
        s += "\n{}\n{}".format(
            self.context, " " * self.contextoffset + "^" * self.errorlength
            #+" " * (len(self.context) - self.contextoffset - self.errorlength)
        )
        return s

    def __setattr__(self, name, value):
        if name in self._SLOTS:
            value = self._SLOTS[name](value)
        super().__setattr__(name, value)

    def __getattr__(self, name):
        # Fallback to calculated `frompos` and `topos` attributes
        # if using unpatched LanguageTool server.
        if name == "frompos":
            return self._frompos
        elif name == "topos":
            return self._topos
        return None

    @property
    def _frompos(self):
        if self._frompos_cache is None:
            self._frompos_cache = self._get_pos(self.fromy, self.fromx)
        return self._frompos_cache

    @property
    def _topos(self):
        if self._topos_cache is None:
            self._topos_cache = self._get_pos(self.toy, self.tox)
        return self._topos_cache

    def _get_pos(self, y, x):
        if not isinstance(self._lines, list):
            self._lines = self._lines.split("\n")
        prev_lines = self._lines[:y]
        return sum([len(line) for line in prev_lines]) + len(prev_lines) + x


class LanguageTool:
    """Main class used for checking text against different rules
    """
    _HOST = socket.gethostbyname("localhost")
    _MIN_PORT = 8081
    _MAX_PORT = 8083
    _TIMEOUT = 30

    _port = _MIN_PORT
    _server = None
    _instances = WeakValueDictionary()
    _PORT_RE = re.compile(r"port (\d+)", re.I)

    def __init__(self, language=None, motherTongue=None):
        if not self._server_is_alive():
            self._start_server_on_free_port()
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
        self.reset_disabled()
        self.reset_enabled()

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

    @property
    def _spell_checking_rules(self):
        return {"HUNSPELL_RULE", "HUNSPELL_NO_SUGGEST_RULE",
                "MORFOLOGIK_RULE_" + self.language.replace("-", "_").upper()}

    def check(self, text: str, srctext=None) -> [Match]:
        """Match text against enabled rules.
        """
        root = self._get_root(self._url, self._encode(text, srctext))
        return [Match(e.attrib, text) for e in root]

    def _check_api(self, text: str, srctext=None) -> bytes:
        """Match text against enabled rules (result in XML format).
        """
        root = self._get_root(self._url, self._encode(text, srctext))
        return (b'<?xml version="1.0" encoding="UTF-8"?>\n' +
                ElementTree.tostring(root) + b"\n")

    def _encode(self, text, srctext=None):
        params = {"language": self.language, "text": text.encode("utf-8")}
        if srctext is not None:
            params["srctext"] = srctext.encode("utf-8")
        if self.motherTongue is not None:
            params["motherTongue"] = self.motherTongue
        if self.disabled is not None:
            params["disabled"] = ",".join(self.disabled)
        if self.enabled is not None:
            params["enabled"] = ",".join(self.enabled)
        return urllib.parse.urlencode(params).encode()

    def correct(self, text: str, srctext=None) -> str:
        """Automatically apply suggestions to the text.
        """
        return correct(text, self.check(text, srctext))

    def disable(self, rules: Sequence):
        """Disable specified rules.
        """
        if self.disabled is None:
            self.disabled = set()
        for rule in rules:
            self.disabled.add(rule)

    def enable(self, rules: Sequence):
        """Enable specified rules.
        """
        if self.enabled is None:
            self.enabled = set()
        for rule in rules:
            self.enabled.add(rule)

    def reset_disabled(self):
        """Reset disabled rules.
        """
        self.disabled = self._spell_checking_rules

    def reset_enabled(self):
        """Reset enabled rules.
        """
        self.enabled = None

    def enable_spellchecking(self):
        """Enable spell-checking rules.
        """
        if self.disabled is None:
            return
        for rule in self._spell_checking_rules:
            self.disabled.remove(rule)

    def disable_spellchecking(self):
        """Disable spell-checking rules.
        """
        if self.disabled is None:
            self.disabled = set()
        for rule in self._spell_checking_rules:
            self.disabled.add(rule)

    @classmethod
    def _get_languages(cls):
        if not cls._server_is_alive():
            cls._start_server_on_free_port()
        url = urllib.parse.urljoin(cls._url, "Languages")
        languages = set()
        for e in cls._get_root(url, num_tries=1):
            language = e.get("abbr")
            if len(re.split(r"[_-]", language)) < 2:
                match = re.search(r"\((.*?)\)", e.get("name"))
                if match:
                    country_name = match.group(1)
                    try:
                        country_code = get_country_code(country_name)
                    except KeyError:
                        warnings.warn(
                            "unknown language: {!r}".format(e.get("name")))
                    else:
                        language += "-" + country_code
            languages.add(language)
        return languages

    @classmethod
    def _get_root(cls, url, data=None, num_tries=2):
        for n in range(num_tries):
            try:
                with urlopen(url, data, cls._TIMEOUT) as f:
                    return ElementTree.parse(f).getroot()
            except (IOError, http.client.HTTPException) as e:
                if n + 1 < num_tries:
                    cls._start_server()
                else:
                    raise Error("{}: {}".format(cls._url, e))

    @classmethod
    def _start_server_on_free_port(cls):
        while True:
            cls._url = "http://{}:{}".format(cls._HOST, cls._port)
            try:
                cls._start_server()
                break
            except ServerError:
                if cls._MIN_PORT <= cls._port < cls._MAX_PORT:
                    cls._port += 1
                else:
                    raise

    @classmethod
    def _start_server(cls):
        err = None
        try:
            server_cmd = get_server_cmd(cls._port)
        except PathError as e:
            # Can’t find path to LanguageTool.
            err = e
        else:
            # Need to PIPE all handles: http://bugs.python.org/issue3905
            cls._server = subprocess.Popen(
                server_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                startupinfo=startupinfo
            )
            match = cls._PORT_RE.search(cls._server.stdout.readline())
            if match:
                port = int(match.group(1))
                if port != cls._port:
                    raise Error("requested port {}, but got {}"
                                .format(cls._port, port))
            else:
                cls._terminate_server()
                err_msg = cls._server.communicate("")[1].strip()
                cls._server = None
                match = cls._PORT_RE.search(err_msg)
                if not match:
                    raise Error(err_msg)
                port = int(match.group(1))
                if port != cls._port:
                    raise Error(err_msg)
        if not cls._server:
            # Couldn’t start the server, so maybe there is already one running.
            params = {"language": FAILSAFE_LANGUAGE, "text": ""}
            data = urllib.parse.urlencode(params).encode()
            try:
                with urlopen(cls._url, data, cls._TIMEOUT) as f:
                    tree = ElementTree.parse(f)
            except (IOError, http.client.HTTPException) as e:
                if err:
                    raise err
                raise ServerError("{}: {}".format(cls._url, e))
            root = tree.getroot()
            if root.tag != "matches":
                raise ServerError("unexpected root from {}: {!r}"
                                  .format(cls._url, root.tag))

    @classmethod
    def _server_is_alive(cls):
        return cls._server and cls._server.poll() is None

    @classmethod
    def _terminate_server(cls):
        try:
            cls._server.terminate()
        except OSError:
            pass


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


def correct(text: str, matches: [Match]) -> str:
    """Automatically apply suggestions to the text.
    """
    ltext = list(text)
    matches = [match for match in matches if match.replacements]
    errors = [ltext[match.frompos:match.topos] for match in matches]
    offset = 0
    for n, match in enumerate(matches):
        frompos, topos = match.frompos + offset, match.topos + offset
        if ltext[frompos:topos] != errors[n]:
            continue
        repl = match.replacements[0]
        ltext[frompos:topos] = list(repl)
        offset += len(repl) - len(errors[n])
    return "".join(ltext)


def get_version():
    """Get LanguageTool version as a string.
    """
    try:
        return cache["version"]
    except KeyError:
        version_re = re.compile(r"LanguageTool-?.*?(\S+)$")

        # LanguageTool 1.9+
        proc = subprocess.Popen(
            get_version_cmd(),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            startupinfo=startupinfo
        )
        out = proc.communicate("", LanguageTool._TIMEOUT)[0]
        match = version_re.search(out)

        if not match:
            match = version_re.search(get_directory())
            if not match:
                raise Error("unexpected version output: {!r}".format(out))
        version = match.group(1)
        cache["version"] = version
    return version


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
    rules_path = os.path.join(get_directory(), "rules")
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


def get_directory():
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
                raise PathError("can’t find LanguageTool directory in {!r}"
                                .format(base_dir))
        cache["language_tool_dir"] = language_tool_dir
    return language_tool_dir


def set_directory(path=None):
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
            raise JavaError("can’t find Java")
        jar_names = ["LanguageTool.jar", "LanguageTool.uno.jar"]
        for jar_name in jar_names:
            jar_path = os.path.join(get_directory(), jar_name)
            if os.path.isfile(jar_path):
                break
        else:
            raise PathError("can’t find {!r} in {!r}"
                            .format(jar_names[0], get_directory()))
        cache["jar_info"] = java_path, jar_path
    return java_path, jar_path


def get_locale_language():
    """Get the language code for the current locale setting.
    """
    return locale.getlocale()[0] or locale.getdefaultlocale()[0]


@atexit.register
def terminate_server():
    """Terminate the server.
    """
    if LanguageTool._server_is_alive():
        LanguageTool._terminate_server()


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
