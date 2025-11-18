"""LanguageTool server management module."""

import atexit
import contextlib
import http.client
import json
import logging
import random
import socket
import subprocess
import time
import urllib.parse
import warnings
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Set

import psutil
import requests

from .config_file import LanguageToolConfig
from .download_lt import LTP_DOWNLOAD_VERSION, download_lt
from .exceptions import (
    LanguageToolError,
    PathError,
    RateLimitError,
    ServerError,
)
from .language_tag import LanguageTag
from .match import Match
from .utils import (
    FAILSAFE_LANGUAGE,
    correct,
    get_language_tool_directory,
    get_locale_language,
    get_server_cmd,
    kill_process_force,
    parse_url,
    startupinfo,
)

logger = logging.getLogger(__name__)

# Keep track of running server PIDs in a global list. This way,
# we can ensure they're killed on exit.
RUNNING_SERVER_PROCESSES: List[subprocess.Popen[str]] = []


def _kill_processes(processes: List[subprocess.Popen[str]]) -> None:
    """
    Kill all running server processes.
    This function iterates over the list of running server processes and
    forcefully kills each process by its PID.

    :param processes: A list of subprocess.Popen objects representing the running server processes.
    :type processes: List[subprocess.Popen]
    """
    for pid in [p.pid for p in processes]:
        with contextlib.suppress(psutil.NoSuchProcess):
            kill_process_force(pid=pid)


class LanguageTool:
    """
    A class to interact with the LanguageTool server for text checking and correction.

    :param language: The language to be used by the LanguageTool server. If None, it will try to detect the system language.
    :type language: Optional[str]
    :param mother_tongue: The mother tongue of the user.
    :type mother_tongue: Optional[str]
    :param remote_server: URL of a remote LanguageTool server. If provided, the local server will not be started.
    :type remote_server: Optional[str]
    :param new_spellings: Custom spellings to be added to the LanguageTool server.
    :type new_spellings: Optional[List[str]]
    :param new_spellings_persist: Whether the new spellings should persist across sessions.
    :type new_spellings_persist: Optional[bool]
    :param host: The host address for the LanguageTool server. Defaults to 'localhost'.
    :type host: Optional[str]
    :param config: Path to a configuration file for the LanguageTool server.
    :type config: Optional[str]
    :param language_tool_download_version: The version of LanguageTool to download if needed.
    :type language_tool_download_version: Optional[str]
    """

    _available_ports: List[int]
    """A list of available ports for the server, shuffled randomly."""

    _TIMEOUT: Literal[300] = 300
    """The timeout for server requests."""

    _remote: bool
    """A flag to indicate if the server is remote."""

    _port: int
    """The port number to use for the server."""

    _server: Optional[subprocess.Popen[str]]
    """The server process."""

    _language_tool_download_version: str
    """The version of LanguageTool to download."""

    _new_spellings: Optional[List[str]]
    """A list of new spellings to register."""

    _new_spellings_persist: bool
    """A flag to indicate if new spellings should persist."""

    _host: str
    """The host to use for the server."""

    config: Optional[LanguageToolConfig]
    """The configuration to use for the server."""

    _url: str
    """The URL of the server if remote."""

    _mother_tongue: Optional[str]
    """The user's mother tongue (used in requests to the server)."""

    disabled_rules: Set[str]
    """A set of disabled rules (used in requests to the server)."""

    enabled_rules: Set[str]
    """A set of enabled rules (used in requests to the server)."""

    disabled_categories: Set[str]
    """A set of disabled categories (used in requests to the server)."""

    enabled_categories: Set[str]
    """A set of enabled categories (used in requests to the server)."""

    enabled_rules_only: bool
    """A flag to indicate if only enabled rules should be used (used in requests to the server)."""

    preferred_variants: Set[str]
    """A set of preferred variants (used in requests to the server)."""

    picky: bool
    """A flag to indicate if the tool should be picky (used in requests to the server)."""

    _language: LanguageTag
    """The language to use (used in requests to the server and in other methods)."""

    def __init__(
        self,
        language: Optional[str] = None,
        mother_tongue: Optional[str] = None,
        remote_server: Optional[str] = None,
        new_spellings: Optional[List[str]] = None,
        new_spellings_persist: bool = True,
        host: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
        language_tool_download_version: str = LTP_DOWNLOAD_VERSION,
    ) -> None:
        """
        Initialize the LanguageTool server.
        """
        self._remote = False
        self.language_tool_download_version = language_tool_download_version
        self._new_spellings = None
        self._new_spellings_persist = new_spellings_persist
        self._host = host or socket.gethostbyname("localhost")
        self._available_ports = random.sample(range(8081, 8999), (8999 - 8081))
        self._port = self._available_ports.pop()
        self._server = None

        if remote_server and config is not None:
            err = "Cannot use both remote_server and config parameters."
            raise ValueError(err)
        self.config = LanguageToolConfig(config) if config else None

        if remote_server is not None:
            self._remote = True
            self._url = parse_url(remote_server)
            self._url = urllib.parse.urljoin(self._url, "v2/")
            self._update_remote_server_config(self._url)
        elif not self._server_is_alive():
            self._url = f"http://{self._host}:{self._port}/v2/"
            self._start_server_on_free_port()
        if language is None:
            try:
                language = get_locale_language()
            except ValueError:
                language = FAILSAFE_LANGUAGE
        if new_spellings:
            self._new_spellings = new_spellings
            self._register_spellings()
        self._language = LanguageTag(language, self._get_languages())
        self._mother_tongue = mother_tongue
        self.disabled_rules = set()
        self.enabled_rules = set()
        self.disabled_categories = set()
        self.enabled_categories = set()
        self.enabled_rules_only = False
        self.preferred_variants = set()
        self.picky = False

    def __enter__(self) -> "LanguageTool":
        """
        Enter the runtime context related to this object.

        This method is called when execution flow enters the context of the
        ``with`` statement using this object. It returns the object itself.

        :return: The object itself.
        :rtype: LanguageTool
        """
        return self

    def __exit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[BaseException],
        exc_tb: Optional[Any],
    ) -> None:
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
        ensures that the ``close`` method is called to release any resources
        or perform any necessary cleanup.
        """
        if self._server_is_alive():
            warnings.warn("unclosed server", ResourceWarning, stacklevel=2)
            logger.warning(
                "Unclosed server (server still running at %s). Closing it now.",
                getattr(self, "_url", "unknown"),
            )
            self.close()

    def __repr__(self) -> str:
        """
        Return a string representation of the server instance.

        :return: A string that includes the class name, language, and mother tongue.
        :rtype: str
        """
        return f"{self.__class__.__name__}(language={self.language!r}, motherTongue={self.mother_tongue!r})"

    def close(self) -> None:
        """
        Closes the server and performs necessary cleanup operations.

        This method performs the following actions:
        1. Checks if the server is alive, not remote and terminates it if necessary.
        2. If new spellings are not set to persist and there are new spellings,
        it unregisters the spellings and clears the list of new spellings.
        """
        if self._remote is not True and self._server_is_alive():
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
    def mother_tongue(self) -> Optional[LanguageTag]:
        """
        Retrieve the mother tongue language tag.

        :return: The mother tongue language tag if set, otherwise None.
        :rtype: Optional[LanguageTag]
        """
        if self._mother_tongue is not None:
            return LanguageTag(self._mother_tongue, self._get_languages())
        return None

    @mother_tongue.setter
    def mother_tongue(self, mother_tongue: Optional[str]) -> None:
        """
        Sets the mother tongue for the language tool.

        :param mother_tongue: The mother tongue language tag as a string. If None, the mother tongue is set to None.
        :type mother_tongue: Optional[str]
        """

        self._mother_tongue = mother_tongue

    @property
    def _spell_checking_categories(self) -> Set[str]:
        """
        Returns a set of categories used for spell checking.

        :return: A set containing the category 'TYPOS'.
        :rtype: Set[str]
        """

        return {"TYPOS"}

    def check(self, text: str) -> List[Match]:
        """
        Checks the given text for language issues using the LanguageTool server.

        :param text: The text to be checked for language issues.
        :type text: str
        :return: A list of Match objects representing the issues found in the text.
        :rtype: List[Match]
        """
        url = urllib.parse.urljoin(self._url, "check")
        logger.debug("Sending text to LanguageTool server at %s", url)
        response = self._query_server(url, self._create_params(text))
        matches = response["matches"]
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
        params = {"language": str(self.language), "text": text}
        if self.mother_tongue is not None:
            params["motherTongue"] = self.mother_tongue.tag
        if self.disabled_rules:
            params["disabledRules"] = ",".join(self.disabled_rules)
        if self.enabled_rules:
            params["enabledRules"] = ",".join(self.enabled_rules)
        if self.enabled_rules_only:
            params["enabledOnly"] = "true"
        if self.disabled_categories:
            params["disabledCategories"] = ",".join(self.disabled_categories)
        if self.enabled_categories:
            params["enabledCategories"] = ",".join(self.enabled_categories)
        if self.preferred_variants:
            params["preferredVariants"] = ",".join(self.preferred_variants)
        if self.picky:
            params["level"] = "picky"
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
        This method updates the ``disabled_categories`` attribute by removing any categories that are
        related to spell checking, which are defined in the ``_spell_checking_categories`` attribute.
        """
        self.disabled_categories.difference_update(self._spell_checking_categories)

    def disable_spellchecking(self) -> None:
        """
        Disable spellchecking by updating the disabled categories with spell checking categories.
        """
        self.disabled_categories.update(self._spell_checking_categories)

    @staticmethod
    def _get_valid_spelling_file_path() -> Path:
        """
        Retrieve the valid file path for the spelling file.
        This function constructs the file path for the spelling file used by the
        language tool. It checks if the file exists at the constructed path and
        raises a FileNotFoundError if the file is not found.

        :raises FileNotFoundError: If the spelling file does not exist at the
                                   constructed path.
        :return: The valid file path for the spelling file.
        :rtype: Path
        """
        library_path = get_language_tool_directory()
        spelling_file_path = (
            library_path
            / "org"
            / "languagetool"
            / "resource"
            / "en"
            / "hunspell"
            / "spelling.txt"
        )
        if not spelling_file_path.exists():
            err = (
                f"Failed to find the spellings file at {spelling_file_path}\n"
                " Please file an issue at "
                "https://github.com/jxmorris12/language_tool_python/issues"
            )
            raise FileNotFoundError(err)
        return spelling_file_path

    def _register_spellings(self) -> None:
        """
        Registers new spellings by adding them to the spelling file.
        This method reads the existing spellings from the spelling file,
        filters out the new spellings that are already present, and appends
        the remaining new spellings to the file. If the DEBUG_MODE is enabled,
        it prints a message indicating the file where the new spellings were registered.
        """

        if self._new_spellings is None:
            return

        spelling_file_path = self._get_valid_spelling_file_path()
        logger.debug("Registering new spellings at %s", spelling_file_path)
        with open(spelling_file_path, "r+", encoding="utf-8") as spellings_file:
            existing_spellings = {line.strip() for line in spellings_file.readlines()}
            new_spellings = [
                word for word in self._new_spellings if word not in existing_spellings
            ]
            self._new_spellings = new_spellings
            if new_spellings:
                if len(existing_spellings) > 0:
                    spellings_file.write("\n")
                spellings_file.write("\n".join(new_spellings))

    def _unregister_spellings(self) -> None:
        """
        Unregister new spellings from the spelling file.
        This method reads the current spellings from the spelling file, removes any
        spellings that are present in the ``_new_spellings`` attribute, and writes the
        updated list back to the file.
        """
        if self._new_spellings is None:
            return

        spelling_file_path = self._get_valid_spelling_file_path()
        logger.debug("Unregistering new spellings at %s", spelling_file_path)

        with open(spelling_file_path, "r", encoding="utf-8") as spellings_file:
            lines = spellings_file.readlines()

        updated_lines = [
            line for line in lines if line.strip() not in self._new_spellings
        ]
        if updated_lines and updated_lines[-1].endswith("\n"):
            updated_lines[-1] = updated_lines[-1].strip()

        with open(
            spelling_file_path,
            "w",
            encoding="utf-8",
            newline="\n",
        ) as spellings_file:
            spellings_file.writelines(updated_lines)

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
        url = urllib.parse.urljoin(self._url, "languages")
        languages: Set[str] = set()
        for e in self._query_server(url, num_tries=1):
            languages.add(e.get("code"))
            languages.add(e.get("longCode"))
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
        self,
        url: str,
        params: Optional[Dict[str, str]] = None,
        num_tries: int = 2,
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
        logger.debug("_query_server url: %s", url)
        for n in range(num_tries):
            try:
                with requests.get(
                    url,
                    params=params,
                    timeout=self._TIMEOUT,
                ) as response:
                    try:
                        return response.json()
                    except json.decoder.JSONDecodeError as e:
                        logger.debug(
                            "URL %s returned invalid JSON response: %s",
                            url,
                            e,
                        )
                        logger.debug("Status code: %s", response.status_code)
                        if response.status_code == 426:
                            err = (
                                "You have exceeded the rate limit for the free "
                                "LanguageTool API. Please try again later."
                            )
                            raise RateLimitError(err) from e
                        raise LanguageToolError(response.content.decode()) from e
            except (IOError, http.client.HTTPException) as e:
                if self._remote is False:
                    self._terminate_server()
                    self._start_local_server()
                if n + 1 >= num_tries:
                    err2 = f"{self._url}: {e}"
                    raise LanguageToolError(err2) from e
        return None

    def _start_server_on_free_port(self) -> None:
        """
        Attempt to start the server on a free port within the specified range.
        This method continuously tries to start the local server on the current host and port.
        If the port is already in use, it increments the port number and tries again until a free port is found
        or the maximum port number is reached.

        :raises ServerError: If the server cannot be started and the maximum port number is reached.
        """
        while True:
            try:
                self._start_local_server()
                break
            except ServerError:
                if len(self._available_ports) > 0:
                    old_port = self._port
                    self._port = self._available_ports.pop()
                    logger.debug("Port %s failed, trying port %s", old_port, self._port)
                else:
                    raise

    def _start_local_server(self) -> None:
        """
        Start the local LanguageTool server.
        This method starts a local instance of the LanguageTool server. If the
        LanguageTool is not already downloaded, it will download the specified
        version. It handles the server initialization, including setting up
        the server command and managing the server process.

        :raises PathError: If the path to LanguageTool cannot be found.
        :raises ServerError: If the server fails to start or exits early.
        """
        # Before starting local server, download language tool if needed.
        download_lt(self.language_tool_download_version)
        try:
            if self._port:
                logger.info(
                    "language_tool_python initializing with port: %s", self._port
                )
            server_cmd = get_server_cmd(self._port, self.config)
        except PathError as e:
            err = (
                "Failed to find LanguageTool. Please ensure it is downloaded correctly."
            )
            raise PathError(err) from e
        else:
            self._server = subprocess.Popen(  # noqa: S603  # server_cmd is constructed internally -> trusted
                server_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                text=True,
                startupinfo=startupinfo,
            )
            global RUNNING_SERVER_PROCESSES
            RUNNING_SERVER_PROCESSES.append(self._server)

            self._wait_for_server_ready()

        if not self._server:
            err = "Failed to start LanguageTool server."
            raise ServerError(err)

    def _wait_for_server_ready(self, timeout: int = 15) -> None:
        """
        Wait for the LanguageTool server to become ready and responsive.
        This method polls the server's ``/healthcheck`` endpoint until it responds
        successfully or until the timeout is reached. It also monitors the server
        process to detect early exits.

        :param timeout: Maximum time in seconds to wait for the server to become ready.
                        Defaults to 15 seconds.
        :type timeout: int
        :raises ServerError: If the server process exits early with a non-zero code,
                             or if the server does not become ready within the specified
                             timeout period or if the server process is not initialized.
        """
        if self._server is None:
            err = "Server process is not initialized."
            raise ServerError(err)
        url = urllib.parse.urljoin(self._url, "healthcheck")
        start = time.time()

        logger.debug("Waiting for LanguageTool server readiness at %s", url)

        while time.time() - start < timeout:
            # Early exit check
            ret = self._server.poll()
            if ret is not None:
                err = f"LanguageTool server exited early with code {ret}"
                raise ServerError(err)

            # Attempt to connect
            with contextlib.suppress(requests.RequestException):
                r = requests.get(url, timeout=2)
                if r.ok:
                    return

            time.sleep(0.2)

        # Timeout without response
        err = (
            f"LanguageTool server did not become ready on {self._host}:{self._port} "
            f"within {timeout} seconds"
        )
        raise ServerError(err)

    def _server_is_alive(self) -> bool:
        """
        Check if the server is alive.
        This method checks if the server instance exists and is currently running.

        :return: True if the server is alive (exists and running), False otherwise.
        :rtype: bool
        """
        return bool(self._server and self._server.poll() is None)

    def _terminate_server(self) -> None:
        """
        Terminates the server process.
        This method performs the following steps:
        1. Attempts to terminate the server process gracefully.
        2. Closes associated file descriptor (stdin).
        """
        if self._server:
            logger.info("Terminating LanguageTool server on port %s", self._port)
            _kill_processes([self._server])
            RUNNING_SERVER_PROCESSES.remove(self._server)

            if self._server.stdin:
                self._server.stdin.close()

            # Release the server process object
            self._server = None


class LanguageToolPublicAPI(LanguageTool):
    """
    A class to interact with the public LanguageTool API.
    This class extends the ``LanguageTool`` class and initializes it with the
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
        kwargs.setdefault("remote_server", "https://languagetool.org/api/")
        super().__init__(*args, **kwargs)


@atexit.register
def terminate_server() -> None:
    """
    Terminates all running server processes.
    This function iterates over the list of running server processes and
    forcefully kills each process by its PID.
    """
    if RUNNING_SERVER_PROCESSES:
        logger.info(
            "Terminating %d LanguageTool server process(es) at exit",
            len(RUNNING_SERVER_PROCESSES),
        )
    _kill_processes(RUNNING_SERVER_PROCESSES)
