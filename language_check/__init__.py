# -*- coding: utf-8 -*-

# © 2012 spirit <hiddenspirit@gmail.com>
# © 2013-2014 Steven Myint
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU Lesser General Public License as published
# by the Free Software Foundation, either version 3 of the License,
# or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty
# of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

"""LanguageTool through server mode."""

import atexit
import glob
import http.client
import locale
import os
import re
import socket
import sys
import threading
import urllib.parse
import urllib.request
from collections import OrderedDict
from functools import total_ordering
from weakref import WeakValueDictionary

try:
    from xml.etree import cElementTree as ElementTree
except ImportError:
    from xml.etree import ElementTree

from .backports import subprocess
from .which import which


__version__ = '1.0'


__all__ = ['LanguageTool', 'Error', 'get_languages', 'correct', 'get_version',
           'get_directory', 'set_directory']

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

cache = {}


class Error(Exception):

    """LanguageTool Error."""


class ServerError(Error):
    pass


class JavaError(Error):
    pass


class PathError(Error):
    pass


def get_replacement_list(string, sep='#'):
    if isinstance(string, list):
        return string
    return string.split(sep) if string else []


def auto_type(string):
    try:
        return int(string)
    except ValueError:
        try:
            return float(string)
        except ValueError:
            return string


@total_ordering
class Match:

    """Hold information about where a rule matches text."""
    _SLOTS = OrderedDict([
        ('fromy', int), ('fromx', int), ('toy', int), ('tox', int),
        ('ruleId', str), ('subId', str), ('msg', str),
        ('replacements', get_replacement_list),
        ('context', str), ('contextoffset', int),
        ('offset', int), ('errorlength', int),
        ('url', str), ('category', str), ('locqualityissuetype', str),
    ])

    def __init__(self, attrib):
        for k, v in attrib.items():
            setattr(self, k, v)

    def __repr__(self):
        def _ordered_dict_repr():
            slots = list(self._SLOTS)
            slots += list(set(self.__dict__).difference(slots))
            attrs = [slot for slot in slots
                     if slot in self.__dict__ and not slot.startswith('_')]
            return '{{{}}}'.format(
                ', '.join([
                    '{!r}: {!r}'.format(attr, getattr(self, attr))
                    for attr in attrs
                ])
            )

        return '{}({})'.format(self.__class__.__name__, _ordered_dict_repr())

    def __str__(self):
        ruleId = self.ruleId
        if self.subId is not None:
            ruleId += '[{}]'.format(self.subId)
        s = 'Line {}, column {}, Rule ID: {}'.format(
            self.fromy + 1, self.fromx + 1, ruleId)
        if self.msg:
            s += '\nMessage: {}'.format(self.msg)
        if self.replacements:
            s += '\nSuggestion: {}'.format('; '.join(self.replacements))
        s += '\n{}\n{}'.format(
            self.context, ' ' * self.contextoffset + '^' * self.errorlength
        )
        return s

    def __eq__(self, other):
        return list(self) == list(other)

    def __lt__(self, other):
        return list(self) < list(other)

    def __iter__(self):
        return iter(getattr(self, attr) for attr in self._SLOTS)

    def __setattr__(self, name, value):
        try:
            value = self._SLOTS[name](value)
        except KeyError:
            value = auto_type(value)
        super().__setattr__(name, value)

    def __getattr__(self, name):
        if name not in self._SLOTS:
            raise AttributeError('{!r} object has no attribute {!r}'
                                 .format(self.__class__.__name__, name))


class LanguageTool:

    """Main class used for checking text against different rules."""
    _REMOTE = False
    _HOST = socket.gethostbyname('localhost')
    _MIN_PORT = 8081
    _MAX_PORT = 8083
    _TIMEOUT = 5 * 60

    _port = _MIN_PORT
    _server = None
    _consumer_thread = None
    _instances = WeakValueDictionary()
    _PORT_RE = re.compile(r"(?:https?://.*:|port\s+)(\d+)", re.I)

    def __init__(self, language=None, motherTongue=None, remote_server=None):
        if remote_server is not None:
            self._REMOTE = True
            self._HOST = remote_server["host"]
            self._port = remote_server["port"]
            self._url = 'http://{}:{}/v2/check'.format(self._HOST, self._port)
        elif not self._server_is_alive():
            self._start_server_on_free_port()
        if language is None:
            try:
                language = get_locale_language()
            except ValueError:
                language = FAILSAFE_LANGUAGE
        self._language = LanguageTag(language)
        self.motherTongue = motherTongue
        self.disabled = set()
        self.enabled = set()
        self.enabled_only = False
        self._instances[id(self)] = self

    def __del__(self):
        if not self._instances and self._server_is_alive():
            self._terminate_server()

    def __repr__(self):
        return '{}(language={!r}, motherTongue={!r})'.format(
            self.__class__.__name__, self.language, self.motherTongue)

    @property
    def language(self):
        """The language to be used."""
        return self._language

    @language.setter
    def language(self, language):
        self._language = LanguageTag(language)
        self.disabled.clear()
        self.enabled.clear()

    @property
    def motherTongue(self):
        """The user's mother tongue or None.

        The mother tongue may also be used as a source language for
        checking bilingual texts.

        """
        return self._motherTongue

    @motherTongue.setter
    def motherTongue(self, motherTongue):
        self._motherTongue = (None if motherTongue is None
                              else LanguageTag(motherTongue))

    @property
    def _spell_checking_rules(self):
        return {'HUNSPELL_RULE', 'HUNSPELL_NO_SUGGEST_RULE',
                'MORFOLOGIK_RULE_' + self.language.replace('-', '_').upper()}

    def check(self, text: str, srctext=None) -> [Match]:
        """Match text against enabled rules."""
        root = self._get_root(self._url, self._encode(text, srctext))
        return [Match(e.attrib) for e in root if e.tag == 'error']

    def _check_api(self, text: str, srctext=None) -> bytes:
        """Match text against enabled rules (result in XML format)."""
        root = self._get_root(self._url, self._encode(text, srctext))
        return (b'<?xml version="1.0" encoding="UTF-8"?>\n' +
                ElementTree.tostring(root) + b"\n")

    def _encode(self, text, srctext=None):
        params = {'language': self.language, 'text': text.encode('utf-8')}
        if srctext is not None:
            params['srctext'] = srctext.encode('utf-8')
        if self.motherTongue is not None:
            params['motherTongue'] = self.motherTongue
        if self.disabled:
            params['disabled'] = ','.join(self.disabled)
        if self.enabled:
            params['enabled'] = ','.join(self.enabled)
        if self.enabled_only:
            params['enabledOnly'] = 'yes'
        return urllib.parse.urlencode(params).encode()

    def correct(self, text: str, srctext=None) -> str:
        """Automatically apply suggestions to the text."""
        return correct(text, self.check(text, srctext))

    def enable_spellchecking(self):
        """Enable spell-checking rules."""
        self.disabled.difference_update(self._spell_checking_rules)

    def disable_spellchecking(self):
        """Disable spell-checking rules."""
        self.disabled.update(self._spell_checking_rules)

    @classmethod
    def _get_languages(cls) -> set:
        """Get supported languages (by querying the server)."""
        if not cls._server_is_alive():
            cls._start_server_on_free_port()
        url = urllib.parse.urljoin(cls._url, 'Languages')
        languages = set()
        for e in cls._get_root(url, num_tries=1):
            languages.add(e.get('abbr'))
            languages.add(e.get('abbrWithVariant'))
        return languages

    @classmethod
    def _get_attrib(cls):
        """Get matches element attributes."""
        if not cls._server_is_alive() and cls._REMOTE is False:
            cls._start_server_on_free_port()
        params = {'language': FAILSAFE_LANGUAGE, 'text': ''}
        data = urllib.parse.urlencode(params).encode()
        root = cls._get_root(cls._url, data, num_tries=1)
        return root.attrib

    @classmethod
    def _get_root(cls, url, data=None, num_tries=2):
        for n in range(num_tries):
            try:
                with urlopen(url, data, cls._TIMEOUT) as f:
                    return ElementTree.parse(f).getroot()
            except (IOError, http.client.HTTPException) as e:
                if cls._REMOTE is False:
                    cls._terminate_server()
                    cls._start_server()
                if n + 1 >= num_tries:
                    raise Error('{}: {}'.format(cls._url, e))

    @classmethod
    def _start_server_on_free_port(cls):
        while True:
            cls._url = 'http://{}:{}'.format(cls._HOST, cls._port)
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
            # Can't find path to LanguageTool.
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
            # Python 2.7 compatibility
            # for line in cls._server.stdout:
            match = None
            while True:
                line = cls._server.stdout.readline()
                if not line:
                    break
                match = cls._PORT_RE.search(line)
                if match:
                    port = int(match.group(1))
                    if port != cls._port:
                        raise Error('requested port {}, but got {}'.format(
                            cls._port, port))
                    break
            if not match:
                err_msg = cls._terminate_server()
                match = cls._PORT_RE.search(err_msg)
                if not match:
                    raise Error(err_msg)
                port = int(match.group(1))
                if port != cls._port:
                    raise Error(err_msg)

        if cls._server:
            cls._consumer_thread = threading.Thread(
                target=lambda: _consume(cls._server.stdout))
            cls._consumer_thread.daemon = True
            cls._consumer_thread.start()
        else:
            # Couldn't start the server, so maybe there is already one running.
            params = {'language': FAILSAFE_LANGUAGE, 'text': ''}
            data = urllib.parse.urlencode(params).encode()
            try:
                with urlopen(cls._url, data, cls._TIMEOUT) as f:
                    tree = ElementTree.parse(f)
            except (IOError, http.client.HTTPException) as e:
                if err:
                    raise err
                raise ServerError('{}: {}'.format(cls._url, e))
            root = tree.getroot()

            # LanguageTool 1.9+
            if root.get('software') != 'LanguageTool':
                raise ServerError('unexpected software from {}: {!r}'
                                  .format(cls._url, root.get('software')))

    @classmethod
    def _server_is_alive(cls):
        return cls._server and cls._server.poll() is None

    @classmethod
    def _terminate_server(cls):
        error_message = ''

        try:
            cls._server.terminate()
        except OSError:
            pass

        try:
            error_message = cls._server.communicate()[1].strip()
        except (IOError, ValueError):
            pass

        try:
            cls._server.stdout.close()
        except IOError:
            pass

        try:
            cls._server.stdin.close()
        except IOError:
            pass

        try:
            cls._server.stderr.close()
        except IOError:
            pass

        cls._server = None

        return error_message


def _consume(stdout):
    """Consume/ignore the rest of the server output.

    Without this, the server will end up hanging due to the buffer
    filling up.

    """
    while stdout.readline():
        pass


@total_ordering
class LanguageTag(str):

    """Language tag supported by LanguageTool."""
    _LANGUAGE_RE = re.compile(r"^([a-z]{2,3})(?:[_-]([a-z]{2}))?$", re.I)

    def __new__(cls, tag):
        # Can't use super() here because of 3to2.
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

    @classmethod
    def _normalize(cls, tag):
        if not tag:
            raise ValueError('empty language tag')
        languages = {language.lower().replace('-', '_'): language
                     for language in get_languages()}
        try:
            return languages[tag.lower().replace('-', '_')]
        except KeyError:
            try:
                return languages[cls._LANGUAGE_RE.match(tag).group(1).lower()]
            except (KeyError, AttributeError):
                raise ValueError('unsupported language: {!r}'.format(tag))


def correct(text: str, matches: [Match]) -> str:
    """Automatically apply suggestions to the text."""
    ltext = list(text)
    matches = [match for match in matches if match.replacements]
    errors = [ltext[match.offset:match.offset + match.errorlength]
              for match in matches]
    correct_offset = 0
    for n, match in enumerate(matches):
        frompos, topos = (correct_offset + match.offset,
                          correct_offset + match.offset + match.errorlength)
        if ltext[frompos:topos] != errors[n]:
            continue
        repl = match.replacements[0]
        ltext[frompos:topos] = list(repl)
        correct_offset += len(repl) - len(errors[n])
    return ''.join(ltext)


def _get_attrib():
    try:
        attrib = cache['attrib']
    except KeyError:
        attrib = LanguageTool._get_attrib()
        cache['attrib'] = attrib
    return attrib


def get_version():
    """Get LanguageTool version."""
    version = _get_attrib().get('version')
    if not version:
        match = re.search(r"LanguageTool-?.*?(\S+)$", get_directory())
        if match:
            version = match.group(1)
    return version


def get_build_date():
    """Get LanguageTool build date."""
    return _get_attrib().get('buildDate')


def get_languages() -> set:
    """Get supported languages."""
    try:
        languages = cache['languages']
    except KeyError:
        languages = LanguageTool._get_languages()
        cache['languages'] = languages
    return languages


def get_directory():
    """Get LanguageTool directory."""
    try:
        language_check_dir = cache['language_check_dir']
    except KeyError:
        def version_key(string):
            return [int(e) if e.isdigit() else e
                    for e in re.split(r"(\d+)", string)]

        def get_lt_dir(base_dir):
            paths = [
                path for path in
                glob.glob(os.path.join(base_dir, 'LanguageTool*'))
                if os.path.isdir(path)
            ]
            return max(paths, key=version_key) if paths else None

        base_dir = os.path.dirname(sys.argv[0])
        language_check_dir = get_lt_dir(base_dir)
        if not language_check_dir:
            try:
                base_dir = os.path.dirname(os.path.abspath(__file__))
            except NameError:
                pass
            else:
                language_check_dir = get_lt_dir(base_dir)
            if not language_check_dir:
                raise PathError("can't find LanguageTool directory in {!r}"
                                .format(base_dir))
        cache['language_check_dir'] = language_check_dir
    return language_check_dir


def set_directory(path=None):
    """Set LanguageTool directory."""
    old_path = get_directory()
    terminate_server()
    cache.clear()
    if path:
        cache['language_check_dir'] = path
        try:
            get_jar_info()
        except Error:
            cache['language_check_dir'] = old_path
            raise


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
        dir_name = get_directory()
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


@atexit.register
def terminate_server():
    """Terminate the server."""
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
