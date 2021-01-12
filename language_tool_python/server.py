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


DEBUG_MODE = False

# Keep track of running server PIDs in a global list. This way,
# we can ensure they're killed on exit.
RUNNING_SERVER_PROCESSES = []

class LanguageTool:
    """ Main class used for checking text against different rules. 
        LanguageTool v2 API documentation: https://languagetool.org/http-api/swagger-ui/#!/default/post_check
    """
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
    
    def __init__(self, language=None, motherTongue=None, remote_server=None, newSpellings=None):
        if newSpellings:
            self._register_spellings(newSpellings)
        if remote_server is not None:
            self._remote = True
            self._url = parse_url(remote_server)
            self._url = urllib.parse.urljoin(self._url, 'v2/')
            self._update_remote_server_config(self._url)
        elif not self._server_is_alive():
            self._start_server_on_free_port()
        if language is None:
            try:
                language = get_locale_language()
            except ValueError:
                language = FAILSAFE_LANGUAGE
        self._language = LanguageTag(language, self._get_languages())
        self.motherTongue = motherTongue
        self.disabled_rules = set()
        self.enabled_rules = set()
        self.disabled_categories = set()
        self.enabled_categories = set()
        self.enabled_rules_only = False
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
        self._language = LanguageTag(language, self._get_languages())
        self.disabled_rules.clear()
        self.enabled_rules.clear()

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
                              else LanguageTag(motherTongue, self._get_languages()))
    @property
    def _spell_checking_categories(self):
        return {'TYPOS'}

    def check(self, text: str) -> [Match]:
        """Match text against enabled rules."""
        url = urllib.parse.urljoin(self._url, 'check')
        response = self._query_server(url, self._encode(text))
        matches = response['matches']
        return [Match(match) for match in matches]

    def _encode(self, text):
        params = {'language': self.language, 'text': text.encode('utf-8')}
        if self.motherTongue is not None:
            params['motherTongue'] = self.motherTongue
        if self.disabled_rules:
            params['disabledRules'] = ','.join(self.disabled_rules)
        if self.enabled_rules:
            params['enabledRules'] = ','.join(self.enabled_rules)
        if self.enabled_rules_only:
            params['enabledOnly'] = 'true'
        if self.disabled_categories:
            params['disabledCategories'] = ','.join(self.disabled_categories)
        if self.enabled_categories:
            params['enabledCategories'] = ','.join(self.enabled_categories)
        return urllib.parse.urlencode(params).encode()

    def correct(self, text: str) -> str:
        """Automatically apply suggestions to the text."""
        return correct(text, self.check(text))
    
    def enable_spellchecking(self):
        """Enable spell-checking rules."""
        self.disabled_categories.difference_update(self._spell_checking_categories)

    def disable_spellchecking(self):
        """Disable spell-checking rules."""
        self.disabled_categories.update(self._spell_checking_categories)

    def _register_spellings(self, spellings):
        library_path = get_language_tool_directory()
        spelling_file_path = os.path.join(library_path, "org/languagetool/resource/en/hunspell/spelling.txt")
        if not os.path.exists(spelling_file_path):
            raise FileNotFoundError("Failed to find the spellings file at {}\n Please file an issue at https://github.com/jxmorris12/language_tool_python".format(spelling_file_path))
        with open(spelling_file_path, "a+") as spellings_file:
            spellings_file.write("\n" + "\n".join([word for word in spellings]))
        print("Updated the spellings at {}".format(spelling_file_path))

    def _get_languages(self) -> set:
        """Get supported languages (by querying the server)."""
        self._start_server_if_needed()
        url = urllib.parse.urljoin(self._url, 'languages')
        languages = set()
        for e in self._query_server(url, num_tries=1):
            languages.add(e.get('code'))
            languages.add(e.get('longCode'))
        return languages

    def _start_server_if_needed(self):
        # Start server.
        if not self._server_is_alive() and self._remote is False:
            self._start_server_on_free_port()

    def _update_remote_server_config(self, url):
        self._url = url
        self._remote = True

    def _query_server(self, url, data=None, num_tries=2):
        if DEBUG_MODE:
            print('_query_server url:', url, 'data:', data)
        for n in range(num_tries):
            try:
                with urlopen(url, data, self._TIMEOUT) as f:
                    raw_data = f.read().decode('utf-8')
                    try:
                        return json.loads(raw_data)
                    except json.decoder.JSONDecodeError as e:
                        print('URL {url} and data {data} returned invalid JSON response:')
                        print(raw_data)
                        raise e
            except (IOError, http.client.HTTPException) as e:
                if self._remote is False:
                    self._terminate_server()
                    self._start_local_server()
                if n + 1 >= num_tries:
                    raise LanguageToolError('{}: {}'.format(self._url, e))

    def _start_server_on_free_port(self):
        while True:
            self._url = 'http://{}:{}/v2/'.format(self._HOST, self._port)
            try:
                self._start_local_server()
                break
            except ServerError:
                if self._MIN_PORT <= self._port < self._MAX_PORT:
                    self._port += 1
                else:
                    raise

    def _start_local_server(self):
        # Before starting local server, download language tool if needed.
        download_lt()
        err = None
        try:
            server_cmd = get_server_cmd(self._port)
        except PathError as e:
            # Can't find path to LanguageTool.
            err = e
        else:
            # Need to PIPE all handles: http://bugs.python.org/issue3905
            self._server = subprocess.Popen(
                server_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                startupinfo=startupinfo
            )
            global RUNNING_SERVER_PROCESSES
            RUNNING_SERVER_PROCESSES.append(self._server)

            match = None
            while True:
                line = self._server.stdout.readline()
                if not line:
                    break
                match = self._PORT_RE.search(line)
                if match:
                    port = int(match.group(1))
                    if port != self._port:
                        raise LanguageToolError('requested port {}, but got {}'.format(
                            self._port, port))
                    break
            if not match:
                err_msg = self._terminate_server()
                match = self._PORT_RE.search(err_msg)
                if not match:
                    raise LanguageToolError(err_msg)
                port = int(match.group(1))
                if port != self._port:
                    raise LanguageToolError(err_msg)

        if self._server:
            self._consumer_thread = threading.Thread(
                target=lambda: _consume(self._server.stdout))
            self._consumer_thread.daemon = True
            self._consumer_thread.start()
        else:
            # Couldn't start the server, so maybe there is already one running.
            raise ServerError('Server running; don\'t start a server here.')

    def _server_is_alive(self):
        return self._server and self._server.poll() is None

    def _terminate_server(self):
        LanguageToolError_message = ''
        try:
            self._server.terminate()
        except OSError:
            pass
        try:
            LanguageToolError_message = self._server.communicate()[1].strip()
        except (IOError, ValueError):
            pass
        try:
            self._server.stdout.close()
        except IOError:
            pass
        try:
            self._server.stdin.close()
        except IOError:
            pass
        try:
            self._server.stderr.close()
        except IOError:
            pass
        self._server = None
        return LanguageToolError_message

class LanguageToolPublicAPI(LanguageTool):
    """  Language tool client of the official API. """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, remote_server='https://languagetool.org/api/', **kwargs)

@atexit.register
def terminate_server():
    """Terminate the server."""
    for proc in RUNNING_SERVER_PROCESSES:
        proc.terminate()


def _consume(stdout):
    """Consume/ignore the rest of the server output.
    Without this, the server will end up hanging due to the buffer
    filling up.
    """
    while stdout.readline():
        pass
