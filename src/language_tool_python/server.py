"""LanguageTool server management module."""

from __future__ import annotations

import atexit
import contextlib
import http.client
import json
import logging
import random
import re
import socket
import subprocess
import sys
import time
import urllib.parse
import warnings
from typing import TYPE_CHECKING, ClassVar, Literal

import psutil
import requests

from ._internals.api_types import (
    is_check_response,
    is_language_info,
)
from ._internals.utils import (
    FAILSAFE_LANGUAGE,
    get_locale_language,
    kill_process_force,
    parse_url,
    version_tuple,
)
from .config_file import LanguageToolConfig
from .download_lt import LTP_DOWNLOAD_VERSION, LocalLanguageTool
from .exceptions import (
    LanguageToolError,
    PathError,
    RateLimitError,
    ServerError,
)
from .language_tag import LanguageTag
from .match import Match
from .utils import correct

_startupinfo: object | None = None
if sys.platform == "win32":
    _startupinfo = subprocess.STARTUPINFO()
    _startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path
    from types import TracebackType

    from .config_file import ConfigValue

__all__ = ["LanguageTool", "LanguageToolPublicAPI"]

logger = logging.getLogger(__name__)

_HTTP_STATUS_RATE_LIMIT = 426

# Keep track of running server PIDs in a global list. This way,
# we can ensure they're killed on exit.
_RUNNING_SERVER_PROCESSES: list[subprocess.Popen[str]] = []


def _kill_processes(processes: list[subprocess.Popen[str]]) -> None:
    """Kill all running server processes.

    This function iterates over the list of running server processes and forcefully
    kills each process by its PID.

    :param processes: A list of subprocess.Popen objects representing the running server
        processes.
    :type processes: list[subprocess.Popen[str]]
    """
    for p in processes:
        with contextlib.suppress(psutil.NoSuchProcess):
            kill_process_force(pid=p.pid)
        # Wait to avoid zombies
        with contextlib.suppress(subprocess.TimeoutExpired):
            p.wait(timeout=5)


def _match_offset(match: Match) -> int:
    """Return a match offset for sorting."""
    return match.offset


def _decode_response_content(response: requests.Response) -> str:
    """Decode response content from bytes to text."""
    content: object = response.content
    if isinstance(content, bytes):
        return content.decode()
    return str(content)


class LanguageTool:
    """Interact with the LanguageTool server for text checking and correction.

    :param language: The language to be used by the LanguageTool server. If None, it
        will try to detect the system language.
    :type language: str | None
    :param mother_tongue: The mother tongue of the user.
    :type mother_tongue: str | None
    :param remote_server: URL of a remote LanguageTool server. If provided, the local
        server will not be started.
    :type remote_server: str | None
    :param new_spellings: Custom spellings to be added to the LanguageTool server.
    :type new_spellings: list[str] | None
    :param new_spellings_persist: Whether the new spellings should persist across
        sessions.
    :type new_spellings_persist: bool
    :param host: The host address for the LanguageTool server. Defaults to 'localhost'.
    :type host: str | None
    :param config: Configuration options for the local LanguageTool server.
    :type config: collections.abc.Mapping[str, ConfigValue] | None
    :param language_tool_download_version: The version of LanguageTool to download if
        needed.
    :type language_tool_download_version: str
    :param proxies: A dictionary of proxies to use for server requests (e.g., {'http':
        'http://proxy:port', 'https': 'https://proxy:port'}).
    :type proxies: dict[str, str] | None
    :raises ValueError: If incompatible constructor parameters are combined or the
        language tag is unsupported.
    :raises TypeError: If a config value has an unsupported type.
    :raises PathError: If config paths are invalid, the local LanguageTool
        installation cannot be prepared, or custom spellings are requested without a
        local LanguageTool installation.
    :raises ModuleNotFoundError: If no Java installation is detected for a local
        server.
    :raises SystemError: If the detected Java version is incompatible with the
        requested LanguageTool version.
    :raises TimeoutError: If the LanguageTool download request times out.
    :raises ServerError: If the server does not become ready or returns an invalid
        response while initializing.
    :raises LanguageToolError: If the server cannot be queried while initializing.
    """

    _available_ports: list[int]
    """A list of available ports for the server, shuffled randomly."""

    _TIMEOUT: Literal[300] = 300
    """The timeout for server requests."""

    _SPELL_CHECKING_CATEGORIES: ClassVar[set[str]] = {"TYPOS"}
    """Categories used for spell checking."""

    _remote: bool
    """A flag to indicate if the server is remote."""

    _port: int
    """The port number to use for the server."""

    _server: subprocess.Popen[str] | None
    """The server process."""

    _language_tool_download_version: str
    """The version of LanguageTool to download."""

    _local_language_tool: LocalLanguageTool | None
    """The LocalLanguageTool instance."""

    _new_spellings: list[str] | None
    """A list of new spellings to register."""

    _new_spellings_persist: bool
    """A flag to indicate if new spellings should persist."""

    _host: str
    """The host to use for the server."""

    _config: LanguageToolConfig | None
    """The server configuration options (used when starting the local server)."""

    _url: str
    """The base URL of the LanguageTool server (used in all server requests)."""

    _mother_tongue: str | None
    """The user's mother tongue for better error detection (used in requests to the
    server)."""

    _disabled_rules: set[str]
    """A set of disabled grammar/style rules (used in requests to the server)."""

    _enabled_rules: set[str]
    """A set of explicitly enabled rules (used in requests to the server)."""

    _disabled_categories: set[str]
    """A set of disabled rule categories (used in requests to the server)."""

    _enabled_categories: set[str]
    """A set of explicitly enabled categories (used in requests to the server)."""

    _enabled_rules_only: bool
    """A flag to use only explicitly enabled rules/categories
    (used in requests to the server)."""

    _preferred_variants: set[str]
    """A set of preferred language variants (used in requests to the server)."""

    _picky: bool
    """A flag to enable stricter checking mode (used in requests to the server)."""

    _language: LanguageTag
    """The language to use for text checking (used in requests to the server)."""

    _proxies: dict[str, str] | None
    """A dictionary of proxies for network requests (used in requests to the server)."""

    _session: requests.Session
    """The HTTP session used for all requests, enabling connection reuse across
    calls."""

    _premium_username: str | None
    """The premium API username for the LanguageTool API."""

    _premium_key: str | None
    """The premium API key for the LanguageTool API."""

    def __init__(  # noqa: PLR0913  # Too many arguments, but they are all necessary for configuring the server. Maybe refactor in a future breaking release to use a configuration object instead of individual parameters.
        self,
        language: str | None = None,
        mother_tongue: str | None = None,
        remote_server: str | None = None,
        new_spellings: list[str] | None = None,
        new_spellings_persist: bool = True,
        host: str | None = None,
        config: Mapping[str, ConfigValue] | None = None,
        language_tool_download_version: str = LTP_DOWNLOAD_VERSION,
        proxies: dict[str, str] | None = None,
    ) -> None:
        """Initialize the LanguageTool server.

        :raises ValueError: If incompatible parameters are combined or the language
            tag is unsupported.
        :raises TypeError: If a config value has an unsupported type.
        :raises PathError: If config paths are invalid, the local LanguageTool
            installation cannot be prepared, or custom spellings are requested without
            a local LanguageTool installation.
        :raises ModuleNotFoundError: If no Java installation is detected for a local
            server.
        :raises SystemError: If the detected Java version is incompatible with the
            requested LanguageTool version.
        :raises TimeoutError: If the LanguageTool download request times out.
        :raises ServerError: If the server does not become ready or returns an invalid
            response while initializing.
        :raises LanguageToolError: If the server cannot be queried while initializing.
        """
        self._remote = False
        self._language_tool_download_version = language_tool_download_version
        self._local_language_tool = None
        self._new_spellings = None
        self._new_spellings_persist = new_spellings_persist
        self._host = host or socket.gethostbyname("localhost")
        self._available_ports = random.sample(range(8081, 8999), (8999 - 8081))
        self._port = self._available_ports.pop()
        self._server = None
        self._proxies = proxies
        self._session = requests.Session()
        if proxies:
            self._session.proxies.update(proxies)

        if remote_server and config is not None:
            err = "Cannot use both remote_server and config parameters."
            raise ValueError(err)

        if proxies is not None and remote_server is None:
            err = (
                "Proxies can only be used with a remote server. "
                "Local LanguageTool servers do not require proxy configuration."
            )
            raise ValueError(err)

        self._config = LanguageToolConfig(config) if config else None

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
        self._language = LanguageTag(language, self._get_languages())
        if new_spellings:
            self._new_spellings = new_spellings
            self._register_spellings()
        self._mother_tongue = mother_tongue
        self._disabled_rules = set()
        self._enabled_rules = set()
        self._disabled_categories = set()
        self._enabled_categories = set()
        self._enabled_rules_only = False
        self._preferred_variants = set()
        self._picky = False
        self._premium_username = None
        self._premium_key = None

    def __enter__(self) -> LanguageTool:
        """Enter the runtime context related to this object.

        This method is called when execution flow enters the context of the
        ``with`` statement using this object. It returns the object itself.

        :return: The object itself.
        :rtype: LanguageTool
        """
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Exit the runtime context related to this object.

        This method is called when the runtime context is exited. It can be used to
        clean up any resources that were allocated during the context. The parameters
        describe the exception that caused the context to be exited. If the context was
        exited without an exception, all three arguments will be None.

        :param exc_type: The exception type of the exception that caused the context to
            be exited, or None if no exception occurred.
        :type exc_type: type[BaseException] | None
        :param exc_val: The exception instance that caused the context to be exited, or
            None if no exception occurred.
        :type exc_val: BaseException | None
        :param exc_tb: The traceback object associated with the exception, or None if no
            exception occurred.
        :type exc_tb: TracebackType | None
        """
        self.close()

    def __del__(self) -> None:
        """Destructor method that ensures the server is properly closed.

        This method is called when the instance is about to be destroyed. It ensures
        that the ``close`` method is called to release any resources or perform any
        necessary cleanup.
        """
        if self._server_is_alive():
            warnings.warn("unclosed server", ResourceWarning, stacklevel=2)
            logger.warning(
                "Unclosed server (server still running at %s). Closing it now.",
                getattr(self, "_url", "unknown"),
            )
            self.close()

    def __repr__(self) -> str:
        """Return a string representation of the server instance.

        :return: A string that includes the class name, language, and mother tongue.
        :rtype: str
        """
        return (
            f"{self.__class__.__name__}(language={self._language!r}"
            f", motherTongue={self._mother_tongue!r})"
        )

    def close(self) -> None:
        """Close the server and perform necessary cleanup operations.

        This method performs the following actions:
        1. Closes the HTTP session to release connection pool resources cleanly.
        2. Checks if the server is alive, not remote and terminates it if necessary.
        3. If new spellings are not set to persist and there are new spellings,
        it unregisters the spellings and clears the list of new spellings.
        """
        self._session.close()
        if self._remote is not True and self._server_is_alive():
            self._terminate_server()
        if not self._new_spellings_persist and self._new_spellings:
            self._unregister_spellings()
            self._new_spellings = []

    @property
    def language(self) -> LanguageTag:
        """Get the language tag associated with the server.

        :return: The language tag.
        :rtype: LanguageTag
        """
        return self._language

    @language.setter
    def language(self, language: str) -> None:
        """Set the language for the language tool.

        :param language: The language code to set.
        :type language: str
        :raises ValueError: If the language tag is unsupported.
        :raises LanguageToolError: If supported languages cannot be fetched from the
            server.
        """
        self._language = LanguageTag(language, self._get_languages())
        self._disabled_rules.clear()
        self._enabled_rules.clear()

    @property
    def mother_tongue(self) -> LanguageTag | None:
        """Get the mother tongue language tag.

        :return: The mother tongue language tag if set, otherwise None.
        :rtype: LanguageTag | None
        :raises ValueError: If the mother tongue tag is unsupported.
        :raises LanguageToolError: If supported languages cannot be fetched from the
            server.
        """
        if self._mother_tongue is not None:
            return LanguageTag(self._mother_tongue, self._get_languages())
        return None

    @mother_tongue.setter
    def mother_tongue(self, mother_tongue: str | None) -> None:
        """Set the mother tongue for the language tool.

        The mother tongue helps LanguageTool detect false friends (words that look
        similar between two languages but have different meanings). This feature works
        for specific language pairs (e.g., detecting English-like words used incorrectly
        in German).

        :param mother_tongue: The mother tongue language tag as a string. If None, the
            mother tongue is set to None.
        :type mother_tongue: str | None
        """
        self._mother_tongue = mother_tongue

    @property
    def proxies(self) -> dict[str, str] | None:
        """Get the proxies used for server requests.

        :return: A dictionary of proxies if set, otherwise None.
        :rtype: dict[str, str] | None
        """
        return self._proxies

    @proxies.setter
    def proxies(self, proxies: dict[str, str] | None) -> None:
        """Set the proxies for server requests.

        Proxies can only be used with remote servers. Local LanguageTool servers do not
        support proxy configuration. The underlying HTTP session is updated accordingly.

        :param proxies: A dictionary of proxies (e.g., {'http': 'http://proxy:port'}),
            or None to unset.
        :type proxies: dict[str, str] | None
        :raises ValueError: If trying to set proxies on a local server.
        """
        if proxies is not None and not self._remote:
            err = (
                "Proxies can only be used with a remote server. "
                "Local LanguageTool servers do not require proxy configuration."
            )
            raise ValueError(err)
        self._proxies = proxies
        self._session.proxies.clear()
        if proxies:
            self._session.proxies.update(proxies)

    @property
    def disabled_rules(self) -> set[str]:
        """Get the set of disabled rules.

        :return: A set of disabled rule IDs.
        :rtype: set[str]
        """
        return self._disabled_rules

    @disabled_rules.setter
    def disabled_rules(self, value: set[str]) -> None:
        """Set the rules to disable during text checking.

        :param value: A set of rule IDs to disable.
        :type value: set[str]
        """
        self._disabled_rules = value

    @property
    def enabled_rules(self) -> set[str]:
        """Get the set of enabled rules.

        :return: A set of enabled rule IDs.
        :rtype: set[str]
        """
        return self._enabled_rules

    @enabled_rules.setter
    def enabled_rules(self, value: set[str]) -> None:
        """Set the rules to explicitly enable during text checking.

        :param value: A set of rule IDs to enable.
        :type value: set[str]
        """
        self._enabled_rules = value

    @property
    def disabled_categories(self) -> set[str]:
        """Get the set of disabled rule categories.

        :return: A set of disabled category names.
        :rtype: set[str]
        """
        return self._disabled_categories

    @disabled_categories.setter
    def disabled_categories(self, value: set[str]) -> None:
        """Set the rule categories to disable during text checking.

        :param value: A set of category names to disable.
        :type value: set[str]
        """
        self._disabled_categories = value

    @property
    def enabled_categories(self) -> set[str]:
        """Get the set of enabled rule categories.

        :return: A set of enabled category names.
        :rtype: set[str]
        """
        return self._enabled_categories

    @enabled_categories.setter
    def enabled_categories(self, value: set[str]) -> None:
        """Set the rule categories to explicitly enable during text checking.

        :param value: A set of category names to enable.
        :type value: set[str]
        """
        self._enabled_categories = value

    @property
    def enabled_rules_only(self) -> bool:
        """Get whether only enabled rules/categories should be used.

        :return: True if using only enabled rules, False otherwise.
        :rtype: bool
        """
        return self._enabled_rules_only

    @enabled_rules_only.setter
    def enabled_rules_only(self, value: bool) -> None:
        """Set whether to use only explicitly enabled rules/categories.

        When set to True, only rules in enabled_rules will be applied,
        and categories in enabled_categories will be applied.

        :param value: True to use only enabled rules, False to use default rules.
        :type value: bool
        """
        self._enabled_rules_only = value

    @property
    def preferred_variants(self) -> set[str]:
        """Get the set of preferred language variants.

        :return: A set of preferred variant codes.
        :rtype: set[str]
        """
        return self._preferred_variants

    @preferred_variants.setter
    def preferred_variants(self, value: set[str]) -> None:
        """Set the preferred language variants.

        Preferred variants influence which suggestions LanguageTool provides (e.g., en-
        US vs en-GB).

        :param value: A set of preferred variant codes.
        :type value: set[str]
        """
        self._preferred_variants = value

    @property
    def picky(self) -> bool:
        """Get whether picky mode is enabled.

        :return: True if picky mode is enabled, False otherwise.
        :rtype: bool
        """
        return self._picky

    @picky.setter
    def picky(self, value: bool) -> None:
        """Set whether to enable picky mode for stricter checking.

        Picky mode enables additional style rules that may be too strict for casual
        writing.

        :param value: True to enable picky mode, False for standard checking.
        :type value: bool
        """
        self._picky = value

    @property
    def premium_username(self) -> str | None:
        """Get the premium API username.

        :return: The premium API username if set, otherwise None.
        :rtype: str | None
        """
        return self._premium_username

    @premium_username.setter
    def premium_username(self, value: str | None) -> None:
        """Set the premium API username.

        :param value: The premium API username.
        :type value: str | None
        """
        self._premium_username = value

    @property
    def premium_key(self) -> str | None:
        """Get the premium API key.

        :return: The premium API key if set, otherwise None.
        :rtype: str | None
        """
        return self._premium_key

    @premium_key.setter
    def premium_key(self, value: str | None) -> None:
        """Set the premium API key.

        :param value: The premium API key.
        :type value: str | None
        """
        self._premium_key = value

    @property
    def config(self) -> LanguageToolConfig | None:
        """Get the server configuration.

        This property is read-only as the configuration is set during initialization and
        cannot be changed while the server is running.

        :return: The configuration object if set, otherwise None.
        :rtype: LanguageToolConfig | None
        """
        return self._config

    @property
    def language_tool_download_version(self) -> str:
        """Get the LanguageTool version to download.

        This property is read-only as the version is determined during initialization
        and the server cannot be re-downloaded with a different version at runtime.

        :return: The LanguageTool version string.
        :rtype: str
        """
        return self._language_tool_download_version

    @property
    def url(self) -> str:
        """Get the LanguageTool server URL.

        This property is read-only as the URL is determined during initialization and
        cannot be changed while the server is running.

        :return: The server URL (e.g., 'http://localhost:8081/v2/').
        :rtype: str
        """
        return self._url

    @property
    def is_remote(self) -> bool:
        """Get whether using a remote LanguageTool server.

        This property is read-only as the remote status is determined during
        initialization and cannot be changed while the server is running.

        :return: True if using a remote server, False if using a local server.
        :rtype: bool
        """
        return self._remote

    @property
    def host(self) -> str:
        """Get the local server host address.

        This property is read-only as the host address is determined during
        initialization and cannot be changed while the server is running.

        :return: The host address (e.g., '127.0.0.1').
        :rtype: str
        """
        return self._host

    @property
    def port(self) -> int:
        """Get the local server port number.

        This property is read-only as the port number is determined during
        initialization and cannot be changed while the server is running.

        :return: The port number (e.g., 8081).
        :rtype: int
        """
        return self._port

    def check(self, text: str) -> list[Match]:
        """Check the given text for language issues using the LanguageTool server.

        :param text: The text to be checked for language issues.
        :type text: str
        :return: A list of Match objects representing the issues found in the text.
        :rtype: list[Match]
        :raises ServerError: If no response is received from the LanguageTool server or
            if the response shape is invalid.
        :raises ValueError: If the configured mother tongue tag is unsupported.
        :raises RateLimitError: If the public LanguageTool API rate limit is exceeded.
        :raises LanguageToolError: If the server query fails.
        """
        url = urllib.parse.urljoin(self._url, "check")
        logger.debug("Sending text to LanguageTool server at %s", url)
        response = self._query_server(url, self._create_params(text), method="post")
        if response is None:
            err = "No response received from the LanguageTool server."
            raise ServerError(err)
        if not is_check_response(response):
            err = f"Invalid response received from the LanguageTool server: {response}"
            raise ServerError(err)
        matches = response["matches"]
        return [Match(match, text) for match in matches]

    def check_matching_regions(
        self,
        text: str,
        pattern: str,
        flags: int = 0,
    ) -> list[Match]:
        """Check only the parts of the text that match a regex pattern.

        The returned Match objects can be applied to the original text with
        :func:`language_tool_python.utils.correct`.

        :param text: The full text.
        :param pattern: Regular expression defining the regions to check
        :param flags: Regex flags (re.IGNORECASE, re.MULTILINE, etc.)
        :return: A list of Match objects with offsets adjusted to the original text.
        :rtype: list[Match]
        :raises ValueError: If the configured mother tongue tag is unsupported.
        :raises RateLimitError: If the public LanguageTool API rate limit is exceeded.
        :raises LanguageToolError: If the server query fails.
        """
        # Find all matching regions
        matches_iter = re.finditer(pattern, text, flags)
        regions = [(m.start(), m.group()) for m in matches_iter]

        if not regions:
            return []  # No regions to check

        all_matches: list[Match] = []

        for start_offset, region_text in regions:
            region_matches = self.check(region_text)

            # Adjust offsets for the original text
            for match in region_matches:
                match.offset += start_offset

            all_matches.extend(region_matches)

        return sorted(all_matches, key=_match_offset)

    def _create_params(self, text: str) -> dict[str, str]:  # noqa: C901  # Too complex, but it needs to handle many different parameters for the server request.
        """Create a dictionary of parameters for the language tool server request.

        :param text: The text to be checked.
        :type text: str
        :return: A dictionary containing the parameters for the request.
        :rtype: dict[str, str]

        The dictionary may contain the following keys:
        - 'language': The language code.
        - 'text': The text to be checked.
        - 'motherTongue': The mother tongue language code, if specified.
        - 'disabledRules': A comma-separated list of disabled rules, if specified.
        - 'enabledRules': A comma-separated list of enabled rules, if specified.
        - 'enabledOnly': 'true' if only enabled rules should be used.
        - 'disabledCategories': A comma-separated list of disabled categories,
         if specified.
        - 'enabledCategories': A comma-separated list of enabled categories,
         if specified.
        - 'preferredVariants': A comma-separated list of preferred language variants,
         if specified.
        - 'level': 'picky' if picky mode is enabled.
        """
        params = {"language": str(self._language), "text": text}
        if (
            self.mother_tongue is not None
        ):  # accessing via public attr to get LanguageTag and not str
            params["motherTongue"] = self.mother_tongue.tag
        if self._disabled_rules:
            params["disabledRules"] = ",".join(self._disabled_rules)
        if self._enabled_rules:
            params["enabledRules"] = ",".join(self._enabled_rules)
        if self._enabled_rules_only:
            params["enabledOnly"] = "true"
        if self._disabled_categories:
            params["disabledCategories"] = ",".join(self._disabled_categories)
        if self._enabled_categories:
            params["enabledCategories"] = ",".join(self._enabled_categories)
        if self._preferred_variants:
            params["preferredVariants"] = ",".join(self._preferred_variants)
        if self._picky:
            params["level"] = "picky"
        if self._premium_username:
            params["username"] = self._premium_username
        if self._premium_key:
            params["apiKey"] = self._premium_key
        return params

    def correct(self, text: str) -> str:
        """Corrects the given text by applying language tool suggestions.

        Applies only the first suggestion for each issue.

        :param text: The text to be corrected.
        :type text: str
        :return: The corrected text.
        :rtype: str
        :raises ValueError: If the configured mother tongue tag is unsupported.
        :raises RateLimitError: If the public LanguageTool API rate limit is exceeded.
        :raises LanguageToolError: If the server query fails.
        """
        return correct(text, self.check(text))

    def enable_spellchecking(self) -> None:
        """Enable spellchecking by removing spellcheck category exclusions.

        This method updates the :attr:`disabled_categories` attribute by removing any
        categories that are related to spell checking, which are defined in the
        ``_SPELL_CHECKING_CATEGORIES`` class constant.
        """
        self._disabled_categories.difference_update(self._SPELL_CHECKING_CATEGORIES)

    def disable_spellchecking(self) -> None:
        """Disable spellchecking by adding spellcheck categories to exclusions."""
        self._disabled_categories.update(self._SPELL_CHECKING_CATEGORIES)

    def _get_valid_spelling_file_path(self) -> Path:
        """Retrieve the valid file path for the spelling file.

        This function constructs the file path for the spelling file used by the
        language tool. It checks if the file exists at the constructed path and raises a
        FileNotFoundError if the file is not found.

        :raises FileNotFoundError: If the spelling file does not exist at the
            constructed path.
        :raises PathError: If the local LanguageTool instance is not initialized.
        :return: The valid file path for the spelling file.
        :rtype: Path
        """
        if self._local_language_tool is None:
            err = "LocalLanguageTool instance is not initialized."
            raise PathError(err)
        library_path = self._local_language_tool.get_directory_path()

        language = self._language.normalized_tag.split("-")[
            0
        ].lower()  # if language is "en-US", we want "en"

        if language == "auto":
            # Default to English if auto is selected, as the spelling file is needed
            # for new spellings
            # The new spellings will only be taken into account if the server detects
            # the language as English
            logger.debug(
                "Language is set to 'auto'. Defaulting to 'en' for spelling file path.",
            )
            language = "en"

        spelling_file_path = (
            library_path
            / "org"
            / "languagetool"
            / "resource"
            / language
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
        """Register new spellings by adding them to the spelling file.

        This method reads the existing spellings from the spelling file, filters out the
        new spellings that are already present, and appends the remaining new spellings
        to the file. If the DEBUG_MODE is enabled, it prints a message indicating the
        file where the new spellings were registered.
        """
        if self._new_spellings is None:
            return

        spelling_file_path = self._get_valid_spelling_file_path()
        logger.debug("Registering new spellings at %s", spelling_file_path)
        with spelling_file_path.open("r+", encoding="utf-8") as spellings_file:
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
        """Unregister new spellings from the spelling file.

        This method reads the current spellings from the spelling file, removes any
        spellings that are present in the ``_new_spellings`` attribute, and writes the
        updated list back to the file.
        """
        if self._new_spellings is None:
            return

        spelling_file_path = self._get_valid_spelling_file_path()
        logger.debug("Unregistering new spellings at %s", spelling_file_path)

        with spelling_file_path.open("r", encoding="utf-8") as spellings_file:
            lines = spellings_file.readlines()

        updated_lines = [
            line for line in lines if line.strip() not in self._new_spellings
        ]
        if updated_lines and updated_lines[-1].endswith("\n"):
            updated_lines[-1] = updated_lines[-1].strip()

        with spelling_file_path.open(
            "w", encoding="utf-8", newline="\n"
        ) as spellings_file:
            spellings_file.writelines(updated_lines)

    def _get_languages(self) -> set[str]:
        """Retrieve the set of supported languages from the server.

        This method starts the server if it is not already running, constructs the URL
        for querying the supported languages, and sends a request to the server. It then
        processes the server's response to extract the language codes and adds them to a
        set. The special code "auto" is also added to the set before returning it.

        :return: A set of language codes supported by the server.
        :rtype: set[str]
        :raises ServerError: If no response is received or if the response shape is
            invalid.
        :raises LanguageToolError: If the server query fails.
        """
        self._start_server_if_needed()
        url = urllib.parse.urljoin(self._url, "languages")
        languages: set[str] = set()
        raw_languages_response = self._query_server(url, num_tries=1)
        if raw_languages_response is None:
            err = (
                "No response received from the LanguageTool server when "
                "fetching languages."
            )
            raise ServerError(err)
        if isinstance(raw_languages_response, list):
            for lang in raw_languages_response:
                if not is_language_info(lang):
                    err = (
                        "Unexpected response format when fetching languages from the "
                        "LanguageTool server."
                    )
                    raise ServerError(err)
                languages.add(lang["code"])
                languages.add(lang["longCode"])
        else:
            err = (
                "Unexpected response format when fetching languages from the "
                "LanguageTool server."
            )
            raise ServerError(err)
        languages.add("auto")
        return languages

    def _start_server_if_needed(self) -> None:
        """Start the server unless it is already running or remote.

        This method checks if the server is alive and if it is not a remote server. If
        the server is not alive and it is not remote, it starts the server on a free
        port.
        """
        if not self._server_is_alive() and self._remote is False:
            self._start_server_on_free_port()

    def _update_remote_server_config(self, url: str) -> None:
        """Update the configuration to use a remote server.

        :param url: The URL of the remote server.
        :type url: str
        """
        self._url = url
        self._remote = True

    def _query_server(
        self,
        url: str,
        params: dict[str, str] | None = None,
        num_tries: int = 2,
        method: Literal["get", "post"] = "get",
    ) -> object | None:
        """Query the server with the given URL and parameters.

        :param url: The URL to query.
        :type url: str
        :param params: The parameters to include in the query, defaults to None.
        :type params: dict[str, str] | None, optional
        :param num_tries: The number of times to retry the query in case of failure,
            defaults to 2.
        :type num_tries: int, optional
        :param method: HTTP method to use for the request. ``post`` sends params in the
            request body.
        :type method: Literal["get", "post"]
        :return: The JSON response from the server.
        :rtype: object | None
        :raises RateLimitError: If the public LanguageTool API rate limit is exceeded.
        :raises LanguageToolError: If the server returns an invalid JSON response or if
            the query fails after the specified number of retries.
        """
        logger.debug("_query_server url: %s", url)
        for n in range(num_tries):
            try:
                if method == "post":
                    response_context = self._session.post(
                        url,
                        data=params,
                        timeout=self._TIMEOUT,
                    )
                else:
                    response_context = self._session.get(
                        url,
                        params=params,
                        timeout=self._TIMEOUT,
                    )
                with response_context as response:
                    if response.status_code == _HTTP_STATUS_RATE_LIMIT:
                        err = (
                            "You have exceeded the rate limit for the free "
                            "LanguageTool API. Please try again later."
                        )
                        raise RateLimitError(err)
                    try:
                        data: object = response.json()
                    except json.decoder.JSONDecodeError as e:
                        logger.debug(
                            "URL %s returned invalid JSON response: %s",
                            url,
                            e,
                        )
                        logger.debug("Status code: %s", response.status_code)
                        raise LanguageToolError(
                            _decode_response_content(response),
                        ) from e
                    else:
                        return data
            except (OSError, http.client.HTTPException) as e:  # noqa: PERF203  # it is intentional to catch exceptions in a loop, to retry the request in case of transient errors
                if self._remote is False:
                    self._terminate_server()
                    self._start_local_server()
                if n + 1 >= num_tries:
                    err2 = f"{self._url}: {e}"
                    raise LanguageToolError(err2) from e
        return None

    def _start_server_on_free_port(self) -> None:
        """Attempt to start the server on a free port within the specified range.

        This method continuously tries to start the local server on the current host and
        port. If the port is already in use, it increments the port number and tries
        again until a free port is found or the maximum port number is reached.

        :raises ServerError: If the server cannot be started and the maximum port number
            is reached.
        """
        while True:
            try:
                self._start_local_server()
                break
            except ServerError:
                if len(self._available_ports) > 0:
                    old_port = self._port
                    self._port = self._available_ports.pop()
                    self._url = f"http://{self._host}:{self._port}/v2/"
                    logger.debug("Port %s failed, trying port %s", old_port, self._port)
                else:
                    raise

    def _start_local_server(self) -> None:
        """Start the local LanguageTool server.

        This method starts a local instance of the LanguageTool server. If the
        LanguageTool is not already downloaded, it will download the specified version.
        It handles the server initialization, including setting up the server command
        and managing the server process.

        :raises ModuleNotFoundError: If no Java installation is detected.
        :raises SystemError: If the detected Java version is incompatible.
        :raises TimeoutError: If the LanguageTool download request times out.
        :raises JavaError: If the Java executable cannot be found.
        :raises PathError: If the path to LanguageTool cannot be found or the download
            cannot be prepared safely.
        :raises ServerError: If the local server process does not become ready.
        """
        # Before starting local server, download language tool if needed.

        self._local_language_tool = LocalLanguageTool.from_version_name(
            self._language_tool_download_version,
        )
        self._local_language_tool.download()
        try:
            if self._port:
                logger.info(
                    "language_tool_python initializing with port: %s",
                    self._port,
                )
            server_cmd = self._local_language_tool.get_server_cmd(
                self._port,
                self._config,
            )
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
                startupinfo=_startupinfo,
            )
            _RUNNING_SERVER_PROCESSES.append(self._server)

            self._wait_for_server_ready()

    def _wait_for_server_ready(self, timeout: int = 15) -> None:
        """Wait for the LanguageTool server to become ready and responsive.

        This method polls the server's ``/healthcheck`` endpoint until it responds
        successfully or until the timeout is reached. It also monitors the server
        process to detect early exits.

        :param timeout: Maximum time in seconds to wait for the server to become ready.
            Defaults to 15 seconds.
        :type timeout: int
        :raises ServerError: If the server process exits early with a non-zero code, or
            if the server does not become ready within the specified timeout period or
            if the server process is not initialized.
        """
        if self._server is None:
            err = "Server process is not initialized."
            raise ServerError(err)
        url = (
            urllib.parse.urljoin(self._url, "check?text=healthcheck&language=en")
            if re.match(r"^\d+\.\d+$", self._language_tool_download_version)
            and version_tuple(self._language_tool_download_version)
            < (4, 2)  # healthcheck endpoint added in 4.2
            else urllib.parse.urljoin(self._url, "healthcheck")
        )
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
                r = self._session.get(url, timeout=2)
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
        """Check if the server is alive.

        This method checks if the server instance exists and is currently running.

        :return: True if the server is alive (exists and running), False otherwise.
        :rtype: bool
        """
        return bool(self._server and self._server.poll() is None)

    def _terminate_server(self) -> None:
        """Terminates the server process.

        This method performs the following steps:
        1. Attempts to terminate the server process gracefully.
        2. Closes associated file descriptor (stdin).
        """
        if self._server:
            logger.info("Terminating LanguageTool server on port %s", self._port)
            _kill_processes([self._server])
            _RUNNING_SERVER_PROCESSES.remove(self._server)

            if self._server.stdin:
                self._server.stdin.close()

            # Release the server process object
            self._server = None


class LanguageToolPublicAPI(LanguageTool):
    """A class to interact with the public LanguageTool API.

    This class extends the :class:`LanguageTool` class and initializes it with the
    remote server set to the public LanguageTool API endpoint.

    :param language: The language code to use for checking text (e.g., 'en-US').
    :type language: str | None
    :param mother_tongue: The mother tongue language code, if specified (e.g., 'en').
    :type mother_tongue: str | None
    :param new_spellings: A list of new spellings to register, if any.
    :type new_spellings: list[str] | None
    :param new_spellings_persist: Whether to persist new spellings across sessions.
    :type new_spellings_persist: bool
    :param proxies: A dictionary of proxies to use for requests to the remote server.
    :type proxies: dict[str, str] | None
    :raises ValueError: If the language tag is unsupported.
    :raises PathError: If custom spellings are requested for the remote public API.
    :raises LanguageToolError: If the public API cannot be queried while initializing.
    """

    def __init__(
        self,
        language: str | None = None,
        mother_tongue: str | None = None,
        new_spellings: list[str] | None = None,
        new_spellings_persist: bool = True,
        proxies: dict[str, str] | None = None,
    ) -> None:
        """Initialize the LanguageToolPublicAPI server."""
        super().__init__(
            language=language,
            mother_tongue=mother_tongue,
            remote_server="https://languagetool.org/api/",
            new_spellings=new_spellings,
            new_spellings_persist=new_spellings_persist,
            proxies=proxies,
        )


@atexit.register
def _terminate_server_at_exit() -> None:
    """Terminates all running server processes.

    This function iterates over the list of running server processes and forcefully
    kills each process by its PID.
    """
    if _RUNNING_SERVER_PROCESSES:
        logger.info(
            "Terminating %d LanguageTool server process(es) at exit",
            len(_RUNNING_SERVER_PROCESSES),
        )
    _kill_processes(_RUNNING_SERVER_PROCESSES)
