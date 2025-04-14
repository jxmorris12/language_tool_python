"""LanguageTool server management module."""

from typing import Dict, List, Optional, Any, Set

import atexit
import http.client
import json
import os
import re
import requests
import socket
import subprocess
import threading
import urllib.parse
import psutil

from .config_file import LanguageToolConfig
from .download_lt import download_lt, LTP_DOWNLOAD_VERSION
from .language_tag import LanguageTag
from .match import Match
from .utils import (
    correct,
    parse_url, get_locale_language,
    get_language_tool_directory, get_server_cmd,
    FAILSAFE_LANGUAGE, startupinfo,
    LanguageToolError, ServerError, PathError, RateLimitError,
    kill_process_force
)


DEBUG_MODE = False

# Keep track of running server PIDs in a global list. This way,
# we can ensure they're killed on exit.
RUNNING_SERVER_PROCESSES: List[subprocess.Popen] = []


class LanguageTool:
    """
    A class to interact with the LanguageTool server for text checking and correction.

    :param language: The language to be used by the LanguageTool server. If None, it will try to detect the system language.
    :type language: Optional[str]
    :param motherTongue: The mother tongue of the user.
    :type motherTongue: Optional[str]
    :param remote_server: URL of a remote LanguageTool server. If provided, the local server will not be started.
    :type remote_server: Optional[str]
    :param newSpellings: Custom spellings to be added to the LanguageTool server.
    :type newSpellings: Optional[List[str]]
    :param new_spellings_persist: Whether the new spellings should persist across sessions.
    :type new_spellings_persist: Optional[bool]
    :param host: The host address for the LanguageTool server. Defaults to 'localhost'.
    :type host: Optional[str]
    :param config: Path to a configuration file for the LanguageTool server.
    :type config: Optional[str]
    :param language_tool_download_version: The version of LanguageTool to download if needed.
    :type language_tool_download_version: Optional[str]
    
    Attributes:
        _MIN_PORT (int): The minimum port number to use for the server.
        _MAX_PORT (int): The maximum port number to use for the server.
        _TIMEOUT (int): The timeout for server requests.
        _remote (bool): A flag to indicate if the server is remote.
        _port (int): The port number to use for the server.
        _server (subprocess.Popen): The server process.
        _consumer_thread (threading.Thread): The thread to consume server output.
        _PORT_RE (re.Pattern): A compiled regular expression pattern to match the server port.
        language_tool_download_version (str): The version of LanguageTool to download.
        _new_spellings (List[str]): A list of new spellings to register.
        _new_spellings_persist (bool): A flag to indicate if new spellings should persist.
        _host (str): The host to use for the server.
        config (LanguageToolConfig): The configuration to use for the server.
        _url (str): The URL of the server if remote.
        _stop_consume_event (threading.Event): An event to signal the consumer thread to stop.
        motherTongue (str): The user's mother tongue (used in requests to the server).
        disabled_rules (Set[str]): A set of disabled rules (used in requests to the server).
        enabled_rules (Set[str]): A set of enabled rules (used in requests to the server).
        disabled_categories (Set[str]): A set of disabled categories (used in requests to the server).
        enabled_categories (Set[str]): A set of enabled categories (used in requests to the server).
        enabled_rules_only (bool): A flag to indicate if only enabled rules should be used (used in requests to the server).
        preferred_variants (Set[str]): A set of preferred variants (used in requests to the server).
        picky (bool): A flag to indicate if the tool should be picky (used in requests to the server).
        language (str): The language to use (used in requests to the server and in other methods).
        _spell_checking_categories (Set[str]): A set of spell-checking categories.
    """
    _MIN_PORT = 8081
    _MAX_PORT = 8999
    _TIMEOUT = 5 * 60
    _remote = False
    _port = _MIN_PORT
    _server: subprocess.Popen = None
    _consumer_thread: threading.Thread = None
    _PORT_RE = re.compile(r"(?:https?://.*:|port\s+)(\d+)", re.I)

    def __init__(
            self, language=None, motherTongue=None,
            remote_server=None, newSpellings=None,
            new_spellings_persist=True,
            host=None, config=None,
            language_tool_download_version: str = LTP_DOWNLOAD_VERSION
    ) -> None:
        """
        Initialize the LanguageTool server.
        """
        self.language_tool_download_version = language_tool_download_version
        self._new_spellings = None
        self._new_spellings_persist = new_spellings_persist
        self._host = host or socket.gethostbyname('localhost')

        if remote_server:
            assert config is None, "cannot pass config file to remote server"
        self.config = LanguageToolConfig(config) if config else None

        if remote_server is not None:
            self._remote = True
            self._url = parse_url(remote_server)
            self._url = urllib.parse.urljoin(self._url, 'v2/')
            self._update_remote_server_config(self._url)
        elif not self._server_is_alive():
            self._stop_consume_event = threading.Event()
            self._start_server_on_free_port()
        if language is None:
            try:
                language = get_locale_language()
            except ValueError:
                language = FAILSAFE_LANGUAGE
        if newSpellings:
            self._new_spellings = newSpellings
            self._register_spellings()
        self._language = LanguageTag(language, self._get_languages())
        self.motherTongue = motherTongue
        self.disabled_rules = set()
        self.enabled_rules = set()
        self.disabled_categories = set()
        self.enabled_categories = set()
        self.enabled_rules_only = False
        self.preferred_variants = set()
        self.picky = False

    def __enter__(self) -> 'LanguageTool':
        """
        Enter the runtime context related to this object.

        This method is called when execution flow enters the context of the
        `with` statement using this object. It returns the object itself.

        :return: The object itself.
        :rtype: LanguageTool
        """
        return self

    def __exit__(self, exc_type: Optional[type], exc_val: Optional[BaseException], exc_tb: Optional[Any]) -> None:
        """
        Exit the runtime context related to this object.
        This method is called when the runtime context is exited. It can be used to 
        clean up any resources that were allocated during the context. The parameters 
        describe the exception that caused the context to be exited. If the context 
        was exited without an exception, all three arguments will be None.

        :param exc_type: The exception type of the exception that caused the context 
                         to be exited, or None if no exception occurred.
        :type exc_type: Optional[type]
        :param exc_val: The exception instance that caused the context to be exited, 
                        or None if no exception occurred.
        :type exc_val: Optional[BaseException]
        :param exc_tb: The traceback object associated with the exception, or None 
                       if no exception occurred.
        :type exc_tb: Optional[Any]
        """
        self.close()

    def __del__(self) -> None:
        """
        Destructor method that ensures the server is properly closed.
        This method is called when the instance is about to be destroyed. It 
        ensures that the `close` method is called to release any resources 
        or perform any necessary cleanup.
        """
        
        self.close()

    def __repr__(self) -> str:
        """
        Return a string representation of the server instance.

        :return: A string that includes the class name, language, and mother tongue.
        :rtype: str
        """
        return f'{self.__class__.__name__}(language={self.language!r}, motherTongue={self.motherTongue!r})'

    def close(self) -> None:
        """
        Closes the server and performs necessary cleanup operations.

        This method performs the following actions:
        1. Checks if the server is alive and terminates it if necessary.
        2. If new spellings are not set to persist and there are new spellings,
           it unregisters the spellings and clears the list of new spellings.
        """
        if self._server_is_alive():
            self._terminate_server()
        if not self._new_spellings_persist and self._new_spellings:
            self._unregister_spellings()
            self._new_spellings = []

    @property
    def language(self) -> LanguageTag:
        """
        Returns the language tag associated with the server.

        :return: The language tag.
        :rtype: LanguageTag
        """
        
        return self._language

    @language.setter
    def language(self, language: str) -> None:
        """
        Sets the language for the language tool.

        :param language: The language code to set.
        :type language: str
        """

        self._language = LanguageTag(language, self._get_languages())
        self.disabled_rules.clear()
        self.enabled_rules.clear()

    @property
    def motherTongue(self) -> Optional[LanguageTag]:
        """
        Retrieve the mother tongue language tag.

        :return: The mother tongue language tag if set, otherwise None.
        :rtype: Optional[LanguageTag]
        """
        
        return self._motherTongue

    @motherTongue.setter
    def motherTongue(self, motherTongue: Optional[str]) -> None:
        """
        Sets the mother tongue for the language tool.

        :param motherTongue: The mother tongue language tag as a string. If None, the mother tongue is set to None.
        :type motherTongue: Optional[str]
        """

        self._motherTongue = (
            None if motherTongue is None
            else LanguageTag(motherTongue, self._get_languages())
        )

    @property
    def _spell_checking_categories(self) -> Set[str]:
        """
        Returns a set of categories used for spell checking.

        :return: A set containing the category 'TYPOS'.
        :rtype: Set[str]
        """

        return {'TYPOS'}

    def check(self, text: str) -> List[Match]:
        """
        Checks the given text for language issues using the LanguageTool server.

        :param text: The text to be checked for language issues.
        :type text: str
        :return: A list of Match objects representing the issues found in the text.
        :rtype: List[Match]
        """
        url = urllib.parse.urljoin(self._url, 'check')
        response = self._query_server(url, self._create_params(text))
        matches = response['matches']
        return [Match(match, text) for match in matches]

    def _create_params(self, text: str) -> Dict[str, str]:
        """
        Create a dictionary of parameters for the language tool server request.

        :param text: The text to be checked.
        :type text: str
        :return: A dictionary containing the parameters for the request.
        :rtype: Dict[str, str]

        The dictionary may contain the following keys:
        - 'language': The language code.
        - 'text': The text to be checked.
        - 'motherTongue': The mother tongue language code, if specified.
        - 'disabledRules': A comma-separated list of disabled rules, if specified.
        - 'enabledRules': A comma-separated list of enabled rules, if specified.
        - 'enabledOnly': 'true' if only enabled rules should be used.
        - 'disabledCategories': A comma-separated list of disabled categories, if specified.
        - 'enabledCategories': A comma-separated list of enabled categories, if specified.
        - 'preferredVariants': A comma-separated list of preferred language variants, if specified.
        - 'level': 'picky' if picky mode is enabled.
        """
        params = {'language': str(self.language), 'text': text}
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
        if self.preferred_variants:
            params['preferredVariants'] = ','.join(self.preferred_variants)
        if self.picky:
            params['level'] = 'picky'
        return params

    def correct(self, text: str) -> str:
        """
        Corrects the given text by applying language tool suggestions. Applies only the first suggestion for each issue.

        :param text: The text to be corrected.
        :type text: str
        :return: The corrected text.
        :rtype: str
        """
        return correct(text, self.check(text))

    def enable_spellchecking(self) -> None:
        """
        Enable spellchecking by removing spell checking categories from the disabled categories set.
        This method updates the `disabled_categories` attribute by removing any categories that are 
        related to spell checking, which are defined in the `_spell_checking_categories` attribute.
        """
        self.disabled_categories.difference_update(
            self._spell_checking_categories
        )

    def disable_spellchecking(self) -> None:
        """
        Disable spellchecking by updating the disabled categories with spell checking categories.
        """
        self.disabled_categories.update(self._spell_checking_categories)

    @staticmethod
    def _get_valid_spelling_file_path() -> str:
        """
        Retrieve the valid file path for the spelling file.
        This function constructs the file path for the spelling file used by the
        language tool. It checks if the file exists at the constructed path and
        raises a FileNotFoundError if the file is not found.

        :raises FileNotFoundError: If the spelling file does not exist at the
                                   constructed path.
        :return: The valid file path for the spelling file.
        :rtype: str
        """
        library_path = get_language_tool_directory()
        spelling_file_path = os.path.join(
            library_path, "org/languagetool/resource/en/hunspell/spelling.txt"
        )
        if not os.path.exists(spelling_file_path):
            raise FileNotFoundError(
                f"Failed to find the spellings file at {spelling_file_path}\n "
                "Please file an issue at "
                "https://github.com/jxmorris12/language_tool_python/issues")
        return spelling_file_path

    def _register_spellings(self) -> None:
        """
        Registers new spellings by adding them to the spelling file.
        This method reads the existing spellings from the spelling file, 
        filters out the new spellings that are already present, and appends 
        the remaining new spellings to the file. If the DEBUG_MODE is enabled, 
        it prints a message indicating the file where the new spellings were registered.
        """
        
        spelling_file_path = self._get_valid_spelling_file_path()
        with open(spelling_file_path, "r+", encoding='utf-8') as spellings_file:
            existing_spellings = set(line.strip() for line in spellings_file.readlines())
            new_spellings = [word for word in self._new_spellings if word not in existing_spellings]
            self._new_spellings = new_spellings
            if new_spellings:
                if len(existing_spellings) > 0:
                    spellings_file.write("\n")
                spellings_file.write("\n".join(new_spellings))
        if DEBUG_MODE:
            print(f"Registered new spellings at {spelling_file_path}")

    def _unregister_spellings(self) -> None:
        """
        Unregister new spellings from the spelling file.
        This method reads the current spellings from the spelling file, removes any
        spellings that are present in the `_new_spellings` attribute, and writes the
        updated list back to the file.
        """
        spelling_file_path = self._get_valid_spelling_file_path()

        with open(spelling_file_path, 'r', encoding='utf-8') as spellings_file:
            lines = spellings_file.readlines()

        updated_lines = [
            line for line in lines if line.strip() not in self._new_spellings
        ]
        if updated_lines and updated_lines[-1].endswith('\n'):
           updated_lines[-1] = updated_lines[-1].strip()

        with open(spelling_file_path, 'w', encoding='utf-8', newline='\n') as spellings_file:
            spellings_file.writelines(updated_lines)

        if DEBUG_MODE:
            print(f"Unregistered new spellings at {spelling_file_path}")

    def _get_languages(self) -> Set[str]:
        """
        Retrieve the set of supported languages from the server.
        This method starts the server if it is not already running, constructs the URL
        for querying the supported languages, and sends a request to the server. It then
        processes the server's response to extract the language codes and adds them to
        a set. The special code "auto" is also added to the set before returning it.

        :return: A set of language codes supported by the server.
        :rtype: Set[str]
        """
        self._start_server_if_needed()
        url = urllib.parse.urljoin(self._url, 'languages')
        languages = set()
        for e in self._query_server(url, num_tries=1):
            languages.add(e.get('code'))
            languages.add(e.get('longCode'))
        languages.add("auto")
        return languages

    def _start_server_if_needed(self) -> None:
        """
        Starts the server if it is not already running and if it is not a remote server.
        This method checks if the server is alive and if it is not a remote server.
        If the server is not alive and it is not remote, it starts the server on a free port.
        """
        if not self._server_is_alive() and self._remote is False:
            self._start_server_on_free_port()

    def _update_remote_server_config(self, url: str) -> None:
        """
        Update the configuration to use a remote server.

        :param url: The URL of the remote server.
        :type url: str
        """
        self._url = url
        self._remote = True

    def _query_server(
        self, url: str, params: Optional[Dict[str, str]] = None, num_tries: int = 2
    ) -> Any:
        """
        Query the server with the given URL and parameters.

        :param url: The URL to query.
        :type url: str
        :param params: The parameters to include in the query, defaults to None.
        :type params: Optional[Dict[str, str]], optional
        :param num_tries: The number of times to retry the query in case of failure, defaults to 2.
        :type num_tries: int, optional
        :return: The JSON response from the server.
        :rtype: Any
        :raises LanguageToolError: If the server returns an invalid JSON response or if the query fails after the specified number of retries.
        """
        if DEBUG_MODE:
            print('_query_server url:', url, 'params:', params)
        for n in range(num_tries):
            try:
                with (
                    requests.get(url, params=params, timeout=self._TIMEOUT)
                ) as response:
                    try:
                        return response.json()
                    except json.decoder.JSONDecodeError as e:
                        if DEBUG_MODE:
                            print(
                                f'URL {url} and params {params} '
                                f'returned invalid JSON response: {e}'
                            )
                            print(response)
                            print(response.content)
                        if response.status_code == 426:
                            raise RateLimitError(
                                'You have exceeded the rate limit for the free '
                                'LanguageTool API. Please try again later.'
                            )
                        raise LanguageToolError(response.content.decode())
            except (IOError, http.client.HTTPException) as e:
                if self._remote is False:
                    self._terminate_server()
                    self._start_local_server()
                if n + 1 >= num_tries:
                    raise LanguageToolError(f'{self._url}: {e}')

    def _start_server_on_free_port(self) -> None:
        """
        Attempt to start the server on a free port within the specified range.
        This method continuously tries to start the local server on the current host and port.
        If the port is already in use, it increments the port number and tries again until a free port is found
        or the maximum port number is reached.

        :raises ServerError: If the server cannot be started and the maximum port number is reached.
        """
        while True:
            self._url = f'http://{self._host}:{self._port}/v2/'
            try:
                self._start_local_server()
                break
            except ServerError:
                if self._MIN_PORT <= self._port < self._MAX_PORT:
                    self._port += 1
                else:
                    raise

    def _start_local_server(self) -> None:
        """
        Start the local LanguageTool server.
        This method starts a local instance of the LanguageTool server. If the 
        LanguageTool is not already downloaded, it will download the specified 
        version. It handles the server initialization, including setting up 
        the server command and managing the server process.

        Notes:
            - This method uses subprocess to start the server and reads the server 
              output to determine the port it is running on.
            - It also starts a consumer thread to handle the server's stdout.

        :raises PathError: If the path to LanguageTool cannot be found.
        :raises LanguageToolError: If the server starts on a different port than requested.
        :raises ServerError: If the server is already running or cannot be started.
        """
        # Before starting local server, download language tool if needed.
        download_lt(self.language_tool_download_version)
        err = None
        try:
            if DEBUG_MODE:
                if self._port:
                    print(
                        'language_tool_python initializing with port:',
                        self._port
                    )
                if self.config:
                    print(
                        'language_tool_python initializing '
                        'with temporary config file:',
                        self.config.path
                    )
            server_cmd = get_server_cmd(self._port, self.config)
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
                        raise LanguageToolError(f'requested port {self._port}, but got {port}')
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
                target=lambda: self._consume(self._server.stdout))
            self._consumer_thread.daemon = True
            self._consumer_thread.start()
        else:
            # Couldn't start the server, so maybe there is already one running.
            if err:
                raise Exception(err)
            else:
                raise ServerError(
                    'Server running; don\'t start a server here.'
                )
    
    def _consume(self, stdout: Any) -> None:
        """
        Continuously reads from the provided stdout until a stop event is set.

        :param stdout: The output stream to read from.
        :type stdout: Any
        """
        while not self._stop_consume_event.is_set() and stdout.readline():
            pass


    def _server_is_alive(self) -> bool:
        """
        Check if the server is alive.
        This method checks if the server instance exists and is currently running.

        :return: True if the server is alive (exists and running), False otherwise.
        :rtype: bool
        """
        return self._server and self._server.poll() is None

    def _terminate_server(self) -> str:
        """
        Terminates the server process and associated consumer thread.
        This method performs the following steps:
        1. Signals the consumer thread to stop consuming stdout.
        2. Waits for the consumer thread to finish.
        3. Attempts to terminate the server process gracefully.
        4. If the server process does not terminate within the timeout, force kills it.
        5. Closes all associated file descriptors (stdin, stdout, stderr).
        6. Captures any error messages from stderr, if available.

        :return: Error message from stderr, if any, for further logging or debugging.
        :rtype: str
        """
        # Signal the consumer thread to stop consuming stdout
        self._stop_consume_event.set()
        if self._consumer_thread:
            # Wait for the consumer thread to finish
            self._consumer_thread.join(timeout=5)

        error_message = ''
        if self._server:
            try:
                try:
                    # Get the main server process using psutil
                    proc = psutil.Process(self._server.pid)
                except psutil.NoSuchProcess:
                    # If the process doesn't exist, set proc to None
                    proc = None
                
                # Attempt to terminate the process gracefully
                self._server.terminate()
                # Wait for the process to terminate and capture any stderr output
                _, stderr = self._server.communicate(timeout=5)

            except subprocess.TimeoutExpired:
                # If the process does not terminate within the timeout, force kill it
                kill_process_force(proc=proc)
                # Capture remaining stderr output after force termination
                _, stderr = self._server.communicate()

            finally:
                # Close all associated file descriptors (stdin, stdout, stderr)
                if self._server.stdin:
                    self._server.stdin.close()
                if self._server.stdout:
                    self._server.stdout.close()
                if self._server.stderr:
                    self._server.stderr.close()

                # Release the server process object
                self._server = None

            # Capture any error messages from stderr, if available
            if stderr:
                error_message = stderr.strip()

        # Return the error message, if any, for further logging or debugging
        return error_message


class LanguageToolPublicAPI(LanguageTool):
    """
    A class to interact with the public LanguageTool API.
    This class extends the `LanguageTool` class and initializes it with the
    remote server set to the public LanguageTool API endpoint.

    :param args: Positional arguments passed to the parent class initializer.
    :type args: Any
    :param kwargs: Keyword arguments passed to the parent class initializer.
    :type kwargs: Any
    """
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """
        Initialize the server with the given arguments.
        """
        super().__init__(
            *args, remote_server='https://languagetool.org/api/', **kwargs
        )


@atexit.register
def terminate_server() -> None:
    """
    Terminates all running server processes.
    This function iterates over the list of running server processes and 
    forcefully kills each process by its PID.
    """
    for pid in [p.pid for p in RUNNING_SERVER_PROCESSES]:
        kill_process_force(pid=pid)
