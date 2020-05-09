import atexit
import http.client
import json
import re
import socket
import threading
import urllib.parse

from weakref import WeakValueDictionary

from .download_lt import download_lt
from .language_tag import LanguageTag
from .match import Match
from .utils import *

class LanguageTool:
    """ Main class used for checking text against different rules. """
    _HOST = socket.gethostbyname('localhost')
    _MIN_PORT = 8081
    _MAX_PORT = 8999
    _TIMEOUT = 5 * 60

    _remote = False
    _port = _MIN_PORT
    _server = None
    _consumer_thread = None
    _instances = WeakValueDictionary()
    _PORT_RE = re.compile(r"(?:https?://.*:|port\s+)(\d+)", re.I)

    def __init__(self, language=None, motherTongue=None, remote_server=None):
        if remote_server is not None:
            self._remote = True
            if remote_server[-1] == '/': remote_server = remote_server[:-1]
            self._url = '{}/v2/'.format(remote_server)
            self._update_remote_server_config(self._url)
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
        url = urllib.parse.urljoin(self._url, 'check')
        response = self._get_root(url, self._encode(text, srctext))
        matches = response['matches']
        return [Match(match) for match in matches]

    def _check_api(self, text: str, srctext=None) -> bytes:
        """ Match text against enabled rules (result in XML format)."""
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
        cls._start_server_if_needed()
        url = urllib.parse.urljoin(cls._url, 'languages')
        languages = set()
        for e in cls._get_root(url, num_tries=1):
            languages.add(e.get('code'))
            languages.add(e.get('longCode'))
        return languages

    @classmethod
    def _get_attrib(cls):
        """Get matches element attributes."""
        cls._start_server_if_needed()
        params = {'language': FAILSAFE_LANGUAGE, 'text': ''}
        data = urllib.parse.urlencode(params).encode()
        root = cls._get_root(cls._url, data, num_tries=1)
        return root.attrib

    @classmethod
    def _start_server_if_needed(cls):
        # Start server.
        if not cls._server_is_alive() and cls._remote is False:
            cls._start_server_on_free_port()

    @classmethod
    def _update_remote_server_config(cls, url):
        cls._url = url
        cls._remote = True

    @classmethod
    def _get_root(cls, url, data=None, num_tries=2):
        for n in range(num_tries):
            try:
                with urlopen(url, data, cls._TIMEOUT) as f:
                    raw_data = f.read().decode('utf-8')
                    try:
                        return json.loads(raw_data)
                    except json.decoder.JSONDecodeError as e:
                        print('URL {url} and data {data} returned invalid JSON response:')
                        print(raw_data)
                        raise e
            except (IOError, http.client.HTTPException) as e:
                if cls._remote is False:
                    cls._terminate_server()
                    cls._start_local_server()
                if n + 1 >= num_tries:
                    raise LanguageToolError('{}: {}'.format(cls._url, e))

    @classmethod
    def _start_server_on_free_port(cls):
        while True:
            cls._url = 'http://{}:{}/v2/'.format(cls._HOST, cls._port)
            try:
                cls._start_local_server()
                break
            except ServerError:
                if cls._MIN_PORT <= cls._port < cls._MAX_PORT:
                    cls._port += 1
                else:
                    raise

    @classmethod
    def _start_local_server(cls):
        # Before starting local server, download language tool if needed.
        download_lt()

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
                        raise LanguageToolError('requested port {}, but got {}'.format(
                            cls._port, port))
                    break
            if not match:
                err_msg = cls._terminate_server()
                match = cls._PORT_RE.search(err_msg)
                if not match:
                    raise LanguageToolError(err_msg)
                port = int(match.group(1))
                if port != cls._port:
                    raise LanguageToolError(err_msg)

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
            raise ServerError('Server running; don\'t start a server here.')

    @classmethod
    def _server_is_alive(cls):
        return cls._server and cls._server.poll() is None

    @classmethod
    def _terminate_server(cls):
        LanguageToolError_message = ''

        try:
            cls._server.terminate()
        except OSError:
            pass

        try:
            LanguageToolError_message = cls._server.communicate()[1].strip()
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

        return LanguageToolError_message


class LanguageToolPublicAPI(LanguageTool):
    """  Language tool client of the official API. """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, remote_server='https://api.languagetool.org', **kwargs)

@atexit.register
def terminate_server():
    """Terminate the server."""
    if LanguageTool._server_is_alive():
        LanguageTool._terminate_server()



def _consume(stdout):
    """Consume/ignore the rest of the server output.

    Without this, the server will end up hanging due to the buffer
    filling up.

    """
    while stdout.readline():
        pass
