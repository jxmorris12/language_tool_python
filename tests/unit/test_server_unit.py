"""Unit tests for server.py — no Java, no network required."""

from __future__ import annotations

import warnings
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
import requests

from language_tool_python.exceptions import (
    LanguageToolError,
    PathError,
    RateLimitError,
    ServerError,
)
from language_tool_python.language_tag import LanguageTag
from language_tool_python.server import (
    LanguageTool,
    LanguageToolPublicAPI,
    _kill_processes,
    _terminate_server_at_exit,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


_LANGUAGES: set[str] = {"en", "en-US", "fr", "auto"}
_DEFAULT_URL = "http://localhost:8081/v2/"
_DEFAULT_PORT = 8081
_NEXT_PORT = 8082

# Typed response stubs used in patch.object calls (avoids dict[Any, Any] errors)
_INVALID_CHECK_SHAPE: dict[str, str] = {"bad": "shape"}
_BAD_LANG_ITEM: dict[str, str] = {"wrong": "keys"}
_NON_LIST_RESPONSE: dict[str, str] = {"not": "a list"}
_VALID_CHECK_EMPTY: dict[str, object] = {"matches": [], "language": {}, "warnings": {}}
_VALID_LANG_LIST: list[dict[str, str]] = [
    {"code": "en", "longCode": "en-US", "name": "English"},
]
_HTTP_RATE_LIMIT_STATUS = 426


class _MockSession(requests.Session):
    """requests.Session subclass with configurable exception and response injection."""

    def __init__(
        self,
        get_exc: Exception | None = None,
        post_exc: Exception | None = None,
        get_response: requests.Response | None = None,
        post_response: requests.Response | None = None,
    ) -> None:
        """Initialise session with optional exception and response stubs."""
        super().__init__()
        self._get_exc = get_exc
        self._post_exc = post_exc
        self._get_response = get_response
        self._post_response = post_response

    def get(  # type: ignore[override]
        self,
        _url: str | bytes,
        **_kw: object,
    ) -> requests.Response:
        """Raise configured exception or return configured/empty response."""
        if self._get_exc is not None:
            raise self._get_exc
        return (
            self._get_response
            if self._get_response is not None
            else requests.Response()
        )

    def post(  # type: ignore[override]
        self,
        _url: str | bytes,
        _data: object = None,
        _json: object = None,
        **_kw: object,
    ) -> requests.Response:
        """Raise configured exception or return configured/empty response."""
        if self._post_exc is not None:
            raise self._post_exc
        return (
            self._post_response
            if self._post_response is not None
            else requests.Response()
        )


class _MockProcess:
    """Minimal stand-in for subprocess.Popen[str] used in server tests."""

    def __init__(self, poll_return: int | None = None) -> None:
        """Initialise with a fixed poll return value."""
        self.pid: int = 12345
        self.stdin: None = None
        self.returncode: int | None = poll_return
        self._poll_return = poll_return

    def poll(self) -> int | None:
        """Return the configured poll value."""
        return self._poll_return

    def wait(self, timeout: float | None = None) -> int:  # noqa: ARG002
        """Pretend to wait and return 0."""
        return 0

    def terminate(self) -> None:
        """No-op terminate."""


class _MockLocalLT:
    """Mock LocalLanguageTool with configurable directory and PathError on cmd."""

    def __init__(self, directory: Path | None = None) -> None:
        """Initialise with an optional directory to return from get_directory_path."""
        self._directory = directory

    def download(self) -> None:
        """No-op download."""

    def get_directory_path(self) -> Path:
        """Return the configured directory or raise RuntimeError if unset."""
        if self._directory is None:
            err = "no directory configured on mock"
            raise RuntimeError(err)
        return self._directory

    def get_server_cmd(
        self,
        _port: int | None,
        _config: object,
    ) -> list[str]:
        """Raise PathError when called."""
        err = "jar not found"
        raise PathError(err)


class _MockLocalLTWithCmd:
    """Mock LocalLanguageTool that returns a working server command."""

    def download(self) -> None:
        """No-op download."""

    def get_directory_path(self) -> None:
        """No-op — not needed for start_local_server tests."""

    def get_server_cmd(self, _port: int | None, _config: object) -> list[str]:
        """Return a fake Java command."""
        return ["java", "-jar", "lt.jar"]


class _MockMatchWithOffset:
    """Minimal stand-in for Match carrying only an offset attribute."""

    def __init__(self, offset: int = 0) -> None:
        """Initialise with an offset."""
        self.offset = offset


def _make_json_response(body: bytes, status_code: int = 200) -> requests.Response:
    """Build a requests.Response with the given body bytes and status code."""
    r = requests.Response()
    r._content = body
    # prevent close() from accessing r.raw (which is None)
    r._content_consumed = True  # type: ignore[attr-defined]
    r.status_code = status_code
    r.encoding = "utf-8"
    return r


def _bare_lt(**attrs: object) -> LanguageTool:
    """Return a LanguageTool instance created without calling __init__."""
    lt: LanguageTool = object.__new__(LanguageTool)
    lt._server = None
    lt._session = _MockSession()
    lt._remote = False
    lt._new_spellings_persist = True
    lt._new_spellings = None
    lt._url = _DEFAULT_URL
    lt._port = _DEFAULT_PORT
    lt._host = "127.0.0.1"
    lt._config = None
    lt._local_language_tool = None
    lt._proxies = None
    lt._mother_tongue = None
    lt._language = LanguageTag("en", _LANGUAGES)
    lt._disabled_rules = set[str]()
    lt._enabled_rules = set[str]()
    lt._disabled_categories = set[str]()
    lt._enabled_categories = set[str]()
    lt._enabled_rules_only = False
    lt._preferred_variants = set[str]()
    lt._picky = False
    lt._premium_username = None
    lt._premium_key = None
    lt._language_tool_download_version = "6.8"
    lt._available_ports = list[int]()
    for k, v in attrs.items():
        setattr(lt, k, v)
    return lt


def _start_fails_once_then_succeeds() -> Callable[[], None]:
    """Return a callable that raises ServerError on the first call only."""
    calls: list[int] = [0]

    def _start() -> None:
        calls[0] += 1
        if calls[0] == 1:
            err = "port busy"
            raise ServerError(err)

    return _start


class TestLanguageToolConstructorValidation:
    """Tests for __init__ parameter validation."""

    def test_raises_when_remote_server_and_config_combined(self) -> None:
        """Combining remote_server and config raises ValueError immediately."""
        with pytest.raises(ValueError, match="Cannot use both"):
            LanguageTool(remote_server="http://fake/", config={"k": "v"})

    def test_raises_when_proxies_used_without_remote_server(self) -> None:
        """Proxies without remote_server raises ValueError immediately."""
        with pytest.raises(ValueError, match="Proxies can only be used"):
            LanguageTool(proxies={"http": "http://proxy/"})

    def test_session_proxies_updated_when_proxies_and_remote_server_given(
        self,
    ) -> None:
        """Session proxies are updated when proxies and remote_server are provided."""
        with (
            patch(
                "language_tool_python.server.get_locale_language",
                return_value="en",
            ),
            patch.object(LanguageTool, "_get_languages", return_value=_LANGUAGES),
            LanguageTool(
                remote_server="http://fake/",
                proxies={"http": "http://proxy/"},
            ) as lt,
        ):
            assert lt._proxies == {"http": "http://proxy/"}

    def test_failsafe_language_used_when_locale_detection_fails(self) -> None:
        """FAILSAFE_LANGUAGE is used when get_locale_language raises ValueError."""
        with (
            patch(
                "language_tool_python.server.get_locale_language",
                side_effect=ValueError("no locale"),
            ),
            patch.object(LanguageTool, "_get_languages", return_value=_LANGUAGES),
            LanguageTool(remote_server="http://fake/") as lt,
        ):
            assert str(lt.language) == "en"


class TestLanguageToolDel:
    """Tests for __del__ resource warning."""

    def test_del_warns_and_calls_close_when_server_still_alive(self) -> None:
        """ResourceWarning is emitted and close() called when server is alive."""
        lt = _bare_lt()
        lt._server = _MockProcess(poll_return=None)  # type: ignore[assignment]
        with (
            warnings.catch_warnings(record=True) as caught,
        ):
            warnings.simplefilter("always")
            with patch.object(lt, "close") as mock_close:
                lt.__del__()
        assert any(issubclass(w.category, ResourceWarning) for w in caught)
        mock_close.assert_called_once()
        lt._server = None  # prevent GC __del__ re-triggering


class TestLanguageToolRepr:
    """Tests for __repr__."""

    def test_repr_contains_language_and_mother_tongue(self) -> None:
        """__repr__ includes the class name, language, and mother tongue."""
        lt = _bare_lt(_mother_tongue="fr")
        r = repr(lt)
        assert "LanguageTool" in r
        assert "en" in r
        assert "fr" in r


class TestLanguageToolProperties:
    """Tests for all property getters and setters."""

    def test_language_getter_returns_language_tag(self) -> None:
        """Language getter returns the stored LanguageTag."""
        lt = _bare_lt()
        assert lt.language == LanguageTag("en", _LANGUAGES)

    def test_language_setter_updates_tag_and_clears_rules(self) -> None:
        """Language setter updates _language and clears rule sets."""
        lt = _bare_lt()
        lt._disabled_rules = {"OLD"}
        lt._enabled_rules = {"ALSO_OLD"}
        with patch.object(lt, "_get_languages", return_value=_LANGUAGES):
            lt.language = "fr"
        assert str(lt.language) == "fr"
        assert lt._disabled_rules == set()
        assert lt._enabled_rules == set()

    def test_mother_tongue_getter_returns_language_tag_when_set(self) -> None:
        """Mother_tongue getter wraps the stored string in a LanguageTag."""
        lt = _bare_lt(_mother_tongue="fr")
        with patch.object(lt, "_get_languages", return_value=_LANGUAGES):
            mt = lt.mother_tongue
        assert mt is not None
        assert str(mt) == "fr"

    def test_mother_tongue_setter_stores_value(self) -> None:
        """Mother_tongue setter stores the provided value."""
        lt = _bare_lt()
        lt.mother_tongue = "fr"
        assert lt._mother_tongue == "fr"

    def test_proxies_getter_returns_stored_value(self) -> None:
        """Proxies getter returns _proxies."""
        lt = _bare_lt(_proxies={"http": "http://p/"})
        assert lt.proxies == {"http": "http://p/"}

    def test_proxies_setter_raises_when_local_server(self) -> None:
        """Proxies setter raises ValueError when server is local."""
        lt = _bare_lt(_remote=False)
        with pytest.raises(ValueError, match="Proxies can only be used"):
            lt.proxies = {"http": "http://proxy/"}

    def test_proxies_setter_updates_session_when_remote(self) -> None:
        """Proxies setter updates session proxies on a remote server."""
        lt = _bare_lt(_remote=True)
        lt.proxies = {"http": "http://proxy/"}
        assert lt._proxies == {"http": "http://proxy/"}

    def test_proxies_setter_clears_proxies_when_set_to_none(self) -> None:
        """Proxies setter clears session proxies when set to None."""
        lt = _bare_lt(_remote=True)
        lt.proxies = None
        assert lt._proxies is None

    def test_disabled_rules_setter(self) -> None:
        """Disabled_rules setter replaces the set."""
        lt = _bare_lt()
        lt.disabled_rules = {"RULE_X"}
        assert lt._disabled_rules == {"RULE_X"}

    def test_disabled_categories_setter(self) -> None:
        """Disabled_categories setter replaces the set."""
        lt = _bare_lt()
        lt.disabled_categories = {"CAT_A"}
        assert lt._disabled_categories == {"CAT_A"}

    def test_enabled_categories_setter(self) -> None:
        """Enabled_categories setter replaces the set."""
        lt = _bare_lt()
        lt.enabled_categories = {"CAT_B"}
        assert lt._enabled_categories == {"CAT_B"}

    def test_enabled_rules_only_getter(self) -> None:
        """Enabled_rules_only getter returns the stored bool."""
        lt = _bare_lt(_enabled_rules_only=True)
        assert lt.enabled_rules_only is True

    def test_preferred_variants_getter(self) -> None:
        """Preferred_variants getter returns the stored set."""
        lt = _bare_lt(_preferred_variants={"en-US"})
        assert lt.preferred_variants == {"en-US"}

    def test_preferred_variants_setter(self) -> None:
        """Preferred_variants setter replaces the set."""
        lt = _bare_lt()
        lt.preferred_variants = {"en-GB"}
        assert lt._preferred_variants == {"en-GB"}

    def test_picky_getter(self) -> None:
        """Picky getter returns the stored bool."""
        lt = _bare_lt(_picky=True)
        assert lt.picky is True

    def test_picky_setter(self) -> None:
        """Picky setter stores the provided bool."""
        lt = _bare_lt()
        lt.picky = True
        assert lt._picky is True

    def test_premium_username_getter(self) -> None:
        """Premium_username getter returns the stored value."""
        lt = _bare_lt(_premium_username="alice")
        assert lt.premium_username == "alice"

    def test_premium_username_setter(self) -> None:
        """Premium_username setter stores the provided value."""
        lt = _bare_lt()
        lt.premium_username = "alice"
        assert lt._premium_username == "alice"

    def test_premium_key_getter(self) -> None:
        """Premium_key getter returns the stored value."""
        lt = _bare_lt(_premium_key="secret")
        assert lt.premium_key == "secret"

    def test_premium_key_setter(self) -> None:
        """Premium_key setter stores the provided value."""
        lt = _bare_lt()
        lt.premium_key = "secret"
        assert lt._premium_key == "secret"

    def test_config_getter(self) -> None:
        """Config getter returns _config."""
        lt = _bare_lt()
        assert lt.config is None

    def test_url_getter(self) -> None:
        """Url getter returns _url."""
        lt = _bare_lt()
        assert lt.url == _DEFAULT_URL

    def test_is_remote_getter(self) -> None:
        """Is_remote getter returns _remote."""
        lt = _bare_lt(_remote=True)
        assert lt.is_remote is True

    def test_host_getter(self) -> None:
        """Host getter returns _host."""
        lt = _bare_lt()
        assert lt.host == "127.0.0.1"

    def test_port_getter(self) -> None:
        """Port getter returns _port."""
        lt = _bare_lt()
        assert lt.port == _DEFAULT_PORT

    def test_disabled_rules_getter(self) -> None:
        """Disabled_rules getter returns the stored set."""
        lt = _bare_lt(_disabled_rules={"R1"})
        assert lt.disabled_rules == {"R1"}

    def test_enabled_rules_getter(self) -> None:
        """Enabled_rules getter returns the stored set."""
        lt = _bare_lt(_enabled_rules={"R2"})
        assert lt.enabled_rules == {"R2"}

    def test_enabled_rules_setter(self) -> None:
        """Enabled_rules setter replaces the set."""
        lt = _bare_lt()
        lt.enabled_rules = {"R3"}
        assert lt._enabled_rules == {"R3"}

    def test_disabled_categories_getter(self) -> None:
        """Disabled_categories getter returns the stored set."""
        lt = _bare_lt(_disabled_categories={"C1"})
        assert lt.disabled_categories == {"C1"}

    def test_enabled_categories_getter(self) -> None:
        """Enabled_categories getter returns the stored set."""
        lt = _bare_lt(_enabled_categories={"C2"})
        assert lt.enabled_categories == {"C2"}

    def test_enabled_rules_only_setter(self) -> None:
        """Enabled_rules_only setter stores the provided bool."""
        lt = _bare_lt()
        lt.enabled_rules_only = True
        assert lt._enabled_rules_only is True

    def test_language_tool_download_version_getter(self) -> None:
        """Language_tool_download_version getter returns the stored version string."""
        lt = _bare_lt()
        assert lt.language_tool_download_version == "6.8"


class TestLanguageToolClose:
    """Tests for close() terminate and unregister paths."""

    def test_close_terminates_server_when_alive_and_local(self) -> None:
        """_terminate_server() is called when the server is alive and not remote."""
        mock_proc = _MockProcess(poll_return=None)
        lt = _bare_lt(_remote=False)
        lt._server = mock_proc  # type: ignore[assignment]
        with patch.object(lt, "_terminate_server") as mock_term:
            lt.close()
        mock_term.assert_called_once()
        lt._server = None

    def test_close_unregisters_spellings_when_not_persisted(self) -> None:
        """_unregister_spellings() is called when new_spellings_persist is False."""
        lt = _bare_lt(_new_spellings_persist=False, _new_spellings=["hello"])
        with patch.object(lt, "_unregister_spellings") as mock_unreg:
            lt.close()
        mock_unreg.assert_called_once()


class TestLanguageToolCheck:
    """Tests for check() error branches."""

    def test_raises_server_error_when_query_returns_none(self) -> None:
        """Check() raises ServerError when _query_server returns None."""
        lt = _bare_lt()
        with (
            patch.object(lt, "_query_server", return_value=None),
            pytest.raises(ServerError, match="No response received"),
        ):
            lt.check("hello")

    def test_raises_server_error_when_response_has_invalid_shape(self) -> None:
        """Check() raises ServerError when the response fails is_check_response."""
        lt = _bare_lt()
        with (
            patch.object(lt, "_query_server", return_value=_INVALID_CHECK_SHAPE),
            pytest.raises(ServerError, match="Invalid response"),
        ):
            lt.check("hello")

    def test_returns_empty_match_list_on_valid_response(self) -> None:
        """Check() returns an empty list when the server returns zero matches."""
        lt = _bare_lt()
        with patch.object(lt, "_query_server", return_value=_VALID_CHECK_EMPTY):
            result = lt.check("hello")
        assert result == []


class TestCheckMatchingRegions:
    """Tests for check_matching_regions()."""

    def test_returns_empty_list_when_pattern_matches_nothing(self) -> None:
        """Returns [] immediately when the pattern produces no regions."""
        lt = _bare_lt()
        result = lt.check_matching_regions("hello world", r"\d+")
        assert result == []

    def test_returns_adjusted_matches_when_pattern_matches(self) -> None:
        """Matches are offset-adjusted and sorted when the pattern finds regions."""
        mock_match = _MockMatchWithOffset(offset=2)
        match_list: list[_MockMatchWithOffset] = [mock_match]
        lt = _bare_lt()
        with patch.object(lt, "check", return_value=match_list):
            results = lt.check_matching_regions("hello world", r"hello")
        expected_offset = 2
        assert len(results) == 1
        assert results[0].offset == expected_offset


class TestCreateParams:
    """Tests for _create_params() optional parameter branches."""

    def test_optional_params_included_when_attributes_set(self) -> None:
        """All optional _create_params branches fire when attributes are set."""
        lt = _bare_lt(
            _mother_tongue="fr",
            _disabled_rules={"RULE1"},
            _preferred_variants={"en-US"},
            _picky=True,
            _premium_username="user@test",
            _premium_key="key123",
        )
        with patch.object(lt, "_get_languages", return_value=_LANGUAGES):
            params = lt._create_params("hello")

        assert params.get("motherTongue") == "fr"
        assert "RULE1" in (params.get("disabledRules") or "")
        assert "en-US" in (params.get("preferredVariants") or "")
        assert params.get("level") == "picky"
        assert params.get("username") == "user@test"
        assert params.get("apiKey") == "key123"

    def test_enabled_rules_categories_and_enabled_only_included(self) -> None:
        """Enabled rules, enabled-only, and category params are included when set."""
        lt = _bare_lt(
            _enabled_rules={"RULE_EN"},
            _enabled_rules_only=True,
            _disabled_categories={"CAT_DIS"},
            _enabled_categories={"CAT_EN"},
        )
        with patch.object(lt, "_get_languages", return_value=_LANGUAGES):
            params = lt._create_params("hello")

        assert "RULE_EN" in (params.get("enabledRules") or "")
        assert params.get("enabledOnly") == "true"
        assert "CAT_DIS" in (params.get("disabledCategories") or "")
        assert "CAT_EN" in (params.get("enabledCategories") or "")


class TestSpellchecking:
    """Tests for enable_spellchecking()."""

    def test_enable_spellchecking_removes_typos_category(self) -> None:
        """Enable_spellchecking() removes TYPOS from disabled_categories."""
        lt = _bare_lt(_disabled_categories={"TYPOS", "OTHER"})
        lt.enable_spellchecking()
        assert "TYPOS" not in lt._disabled_categories
        assert "OTHER" in lt._disabled_categories

    def test_disable_spellchecking_adds_typos_category(self) -> None:
        """Disable_spellchecking() adds TYPOS to disabled_categories."""
        lt = _bare_lt(_disabled_categories=set[str]())
        lt.disable_spellchecking()
        assert "TYPOS" in lt._disabled_categories


class TestCorrect:
    """Tests for correct()."""

    def test_correct_applies_check_results_to_text(self) -> None:
        """Correct() delegates to check() and returns the corrected text."""
        no_matches: list[_MockMatchWithOffset] = []
        lt = _bare_lt()
        with patch.object(lt, "check", return_value=no_matches):
            result = lt.correct("hello")
        assert result == "hello"


class TestGetValidSpellingFilePath:
    """Tests for _get_valid_spelling_file_path() error branches."""

    def test_raises_when_local_language_tool_not_initialized(self) -> None:
        """Raises PathError when _local_language_tool is None."""
        lt = _bare_lt(_local_language_tool=None)
        with pytest.raises(
            PathError, match="LocalLanguageTool instance is not initialized"
        ):
            lt._get_valid_spelling_file_path()

    def test_raises_file_not_found_when_spelling_file_missing(
        self, tmp_path: Path
    ) -> None:
        """Raises FileNotFoundError when the spelling file does not exist."""
        mock_llt = _MockLocalLT(directory=tmp_path)
        lt = _bare_lt()
        lt._local_language_tool = mock_llt  # type: ignore[assignment]
        with pytest.raises(FileNotFoundError, match="Failed to find"):
            lt._get_valid_spelling_file_path()

    def test_auto_language_defaults_to_en_and_raises_file_not_found(
        self, tmp_path: Path
    ) -> None:
        """Auto language logs debug, defaults to en, then raises if file missing."""
        mock_llt = _MockLocalLT(directory=tmp_path)
        lt = _bare_lt()
        lt._language = LanguageTag("auto", {"auto", "en"})
        lt._local_language_tool = mock_llt  # type: ignore[assignment]
        with pytest.raises(FileNotFoundError, match="Failed to find"):
            lt._get_valid_spelling_file_path()

    def test_returns_path_when_spelling_file_exists(self, tmp_path: Path) -> None:
        """Returns the spelling file path when the file exists."""
        spelling_path = (
            tmp_path
            / "org"
            / "languagetool"
            / "resource"
            / "en"
            / "hunspell"
            / "spelling.txt"
        )
        spelling_path.parent.mkdir(parents=True)
        spelling_path.write_text("existing\n", encoding="utf-8")
        mock_llt = _MockLocalLT(directory=tmp_path)
        lt = _bare_lt()
        lt._local_language_tool = mock_llt  # type: ignore[assignment]
        result = lt._get_valid_spelling_file_path()
        assert result == spelling_path


class TestRegisterSpellingsBody:
    """Tests for _register_spellings() body when new spellings are present."""

    def test_writes_new_spellings_to_file(self, tmp_path: Path) -> None:
        """_register_spellings() appends new words not already in the file."""
        spelling_path = (
            tmp_path
            / "org"
            / "languagetool"
            / "resource"
            / "en"
            / "hunspell"
            / "spelling.txt"
        )
        spelling_path.parent.mkdir(parents=True)
        spelling_path.write_text("existing\n", encoding="utf-8")
        lt = _bare_lt(_new_spellings=["newword"])
        lt._local_language_tool = _MockLocalLT(directory=tmp_path)  # type: ignore[assignment]
        lt._register_spellings()
        content = spelling_path.read_text(encoding="utf-8")
        assert "newword" in content


class TestUnregisterSpellingsBody:
    """Tests for _unregister_spellings() body when new spellings are present."""

    def test_removes_spellings_from_file(self, tmp_path: Path) -> None:
        """_unregister_spellings() removes the registered words from the file."""
        spelling_path = (
            tmp_path
            / "org"
            / "languagetool"
            / "resource"
            / "en"
            / "hunspell"
            / "spelling.txt"
        )
        spelling_path.parent.mkdir(parents=True)
        spelling_path.write_text("existing\nnewword\n", encoding="utf-8")
        lt = _bare_lt(_new_spellings=["newword"])
        lt._local_language_tool = _MockLocalLT(directory=tmp_path)  # type: ignore[assignment]
        lt._unregister_spellings()
        content = spelling_path.read_text(encoding="utf-8")
        assert "newword" not in content
        assert "existing" in content


class TestRegisterUnregisterSpellings:
    """Tests for early-return paths in spelling registration methods."""

    def test_register_spellings_returns_early_when_new_spellings_is_none(
        self,
    ) -> None:
        """_register_spellings() returns immediately when _new_spellings is None."""
        lt = _bare_lt(_new_spellings=None)
        lt._register_spellings()  # must not raise

    def test_unregister_spellings_returns_early_when_new_spellings_is_none(
        self,
    ) -> None:
        """_unregister_spellings() returns immediately when _new_spellings is None."""
        lt = _bare_lt(_new_spellings=None)
        lt._unregister_spellings()  # must not raise


class TestGetLanguages:
    """Tests for _get_languages() error branches."""

    def test_raises_when_query_returns_none(self) -> None:
        """Raises ServerError when _query_server returns None."""
        lt = _bare_lt()
        with (
            patch.object(lt, "_start_server_if_needed"),
            patch.object(lt, "_query_server", return_value=None),
            pytest.raises(ServerError, match="No response received"),
        ):
            lt._get_languages()

    def test_raises_when_list_item_fails_is_language_info(self) -> None:
        """Raises ServerError when a list item does not pass is_language_info."""
        lt = _bare_lt()
        bad_items: list[dict[str, str]] = [_BAD_LANG_ITEM]
        with (
            patch.object(lt, "_start_server_if_needed"),
            patch.object(lt, "_query_server", return_value=bad_items),
            pytest.raises(ServerError, match="Unexpected response format"),
        ):
            lt._get_languages()

    def test_raises_when_response_is_not_a_list(self) -> None:
        """Raises ServerError when response is not a list."""
        lt = _bare_lt()
        with (
            patch.object(lt, "_start_server_if_needed"),
            patch.object(lt, "_query_server", return_value=_NON_LIST_RESPONSE),
            pytest.raises(ServerError, match="Unexpected response format"),
        ):
            lt._get_languages()

    def test_returns_language_set_from_valid_list_response(self) -> None:
        """Returns language codes when the server returns a valid language list."""
        lt = _bare_lt()
        with (
            patch.object(lt, "_start_server_if_needed"),
            patch.object(lt, "_query_server", return_value=_VALID_LANG_LIST),
        ):
            langs = lt._get_languages()
        assert "en" in langs
        assert "en-US" in langs
        assert "auto" in langs


class TestStartServerIfNeeded:
    """Tests for _start_server_if_needed()."""

    def test_calls_start_on_free_port_when_server_not_alive_and_not_remote(
        self,
    ) -> None:
        """_start_server_on_free_port() is called when server is dead and local."""
        lt = _bare_lt(_server=None, _remote=False)
        with patch.object(lt, "_start_server_on_free_port") as mock_start:
            lt._start_server_if_needed()
        mock_start.assert_called_once()


class TestQueryServer:
    """Tests for _query_server() network-error handling."""

    def test_raises_language_tool_error_on_oserror_when_remote(self) -> None:
        """Raises LanguageToolError when session.get raises OSError (remote)."""
        lt = _bare_lt(_remote=True)
        lt._session = _MockSession(get_exc=OSError("connection refused"))
        with pytest.raises(LanguageToolError, match="connection refused"):
            lt._query_server("http://fake/", num_tries=1)

    def test_restarts_local_server_before_raising_on_oserror(self) -> None:
        """Terminate and start are called when local server gets OSError."""
        lt = _bare_lt(_remote=False)
        lt._session = _MockSession(get_exc=OSError("connection refused"))
        with (
            patch.object(lt, "_terminate_server") as mock_term,
            patch.object(lt, "_start_local_server") as mock_start,
            pytest.raises(LanguageToolError, match="connection refused"),
        ):
            lt._query_server("http://fake/", num_tries=1)
        mock_term.assert_called_once()
        mock_start.assert_called_once()


class TestStartServerOnFreePort:
    """Tests for _start_server_on_free_port() port-retry logic."""

    def test_retries_with_next_port_when_first_port_busy(self) -> None:
        """Port is incremented and server restarted when first attempt fails."""
        lt = _bare_lt()
        lt._port = _DEFAULT_PORT
        lt._available_ports = [_NEXT_PORT]
        with patch.object(
            lt,
            "_start_local_server",
            side_effect=_start_fails_once_then_succeeds(),
        ):
            lt._start_server_on_free_port()
        assert lt._port == _NEXT_PORT

    def test_raises_when_no_ports_remain(self) -> None:
        """ServerError is re-raised when no more ports are available."""
        lt = _bare_lt()
        lt._available_ports = list[int]()
        err = "all ports exhausted"
        with (
            patch.object(lt, "_start_local_server", side_effect=ServerError(err)),
            pytest.raises(ServerError, match=err),
        ):
            lt._start_server_on_free_port()


class TestQueryServerResponseHandling:
    """Tests for _query_server() JSON-parsing and POST-method paths."""

    def test_returns_parsed_json_on_successful_get(self) -> None:
        """Returns parsed JSON dict when the GET response contains valid JSON."""
        r = _make_json_response(b'{"ok": true}')
        lt = _bare_lt()
        lt._session = _MockSession(get_response=r)
        result = lt._query_server("http://fake/", num_tries=1)
        assert result == {"ok": True}

    def test_post_method_returns_parsed_json(self) -> None:
        """POST method routes through session.post and returns parsed JSON."""
        r = _make_json_response(b'{"key": "value"}')
        lt = _bare_lt()
        lt._session = _MockSession(post_response=r)
        result = lt._query_server("http://fake/", method="post")
        assert result == {"key": "value"}

    def test_raises_language_tool_error_on_invalid_json(self) -> None:
        """LanguageToolError is raised when the response body is not valid JSON."""
        r = _make_json_response(b"not json", status_code=200)
        lt = _bare_lt(_remote=True)
        lt._session = _MockSession(get_response=r)
        with pytest.raises(LanguageToolError):
            lt._query_server("http://fake/", num_tries=1)

    def test_raises_rate_limit_error_on_http_426(self) -> None:
        """RateLimitError is raised on HTTP 426 with non-JSON body."""
        r = _make_json_response(b"rate limited", status_code=_HTTP_RATE_LIMIT_STATUS)
        lt = _bare_lt(_remote=True)
        lt._session = _MockSession(get_response=r)
        with pytest.raises(RateLimitError):
            lt._query_server("http://fake/", num_tries=1)

    def test_raises_rate_limit_error_on_http_426_with_valid_json(self) -> None:
        """RateLimitError is raised on HTTP 426 even when the body is valid JSON."""
        r = _make_json_response(
            b'{"error": "rate limited"}', status_code=_HTTP_RATE_LIMIT_STATUS
        )
        lt = _bare_lt(_remote=True)
        lt._session = _MockSession(get_response=r)
        with pytest.raises(RateLimitError):
            lt._query_server("http://fake/", num_tries=1)

    def test_returns_none_with_zero_tries(self) -> None:
        """Returns None immediately when num_tries=0 (loop never executes)."""
        lt = _bare_lt()
        result = lt._query_server("http://fake/", num_tries=0)
        assert result is None


class TestKillProcesses:
    """Tests for _kill_processes() iteration and wait logic."""

    def test_suppresses_no_such_process_and_calls_wait(self) -> None:
        """_kill_processes() iterates, suppresses NoSuchProcess, and calls p.wait()."""
        mock_proc = _MockProcess()
        _kill_processes([mock_proc])  # type: ignore[list-item]


class TestTerminateServer:
    """Tests for _terminate_server() body."""

    def test_kills_process_removes_from_list_and_clears_server(self) -> None:
        """_terminate_server() kills the process, removes it, and sets _server=None."""
        mock_proc = _MockProcess(poll_return=None)
        running: list[object] = [mock_proc]
        lt = _bare_lt()
        lt._server = mock_proc  # type: ignore[assignment]
        with (
            patch("language_tool_python.server._RUNNING_SERVER_PROCESSES", running),
            patch("language_tool_python.server._kill_processes") as mock_kill,
        ):
            lt._terminate_server()
        assert lt._server is None
        mock_kill.assert_called_once()
        assert mock_proc not in running

    def test_closes_stdin_when_present(self) -> None:
        """_terminate_server() calls stdin.close() when stdin is not None."""

        class _MockStdin:
            def __init__(self) -> None:
                self.closed = False

            def close(self) -> None:
                self.closed = True

        mock_stdin = _MockStdin()
        mock_proc = _MockProcess(poll_return=None)
        mock_proc.stdin = mock_stdin  # type: ignore[assignment]
        running: list[object] = [mock_proc]
        lt = _bare_lt()
        lt._server = mock_proc  # type: ignore[assignment]
        with (
            patch("language_tool_python.server._RUNNING_SERVER_PROCESSES", running),
            patch("language_tool_python.server._kill_processes"),
        ):
            lt._terminate_server()
        assert mock_stdin.closed

    def test_does_not_raise_when_process_not_in_running_list(self) -> None:
        """_terminate_server() does not raise if the process is absent from the list."""
        mock_proc = _MockProcess(poll_return=None)
        lt = _bare_lt()
        lt._server = mock_proc  # type: ignore[assignment]
        with (
            patch("language_tool_python.server._RUNNING_SERVER_PROCESSES", []),
            patch("language_tool_python.server._kill_processes"),
        ):
            lt._terminate_server()
        assert lt._server is None


class TestStartLocalServer:
    """Tests for _start_local_server() PathError branch."""

    def test_raises_path_error_when_get_server_cmd_fails(self) -> None:
        """Wraps get_server_cmd PathError with 'Failed to find LanguageTool'."""
        lt = _bare_lt()
        with (
            patch(
                "language_tool_python.server.LocalLanguageTool.from_version_name",
                return_value=_MockLocalLT(),
            ),
            pytest.raises(PathError, match="Failed to find LanguageTool"),
        ):
            lt._start_local_server()


class TestStartLocalServerSuccess:
    """Tests for _start_local_server() success path."""

    def test_spawns_process_and_schedules_wait_for_ready(self) -> None:
        """_start_local_server() spawns Popen and calls _wait_for_server_ready."""
        mock_proc = _MockProcess(poll_return=None)
        running: list[object] = []
        lt = _bare_lt()
        with (
            patch(
                "language_tool_python.server.LocalLanguageTool.from_version_name",
                return_value=_MockLocalLTWithCmd(),
            ),
            patch(
                "language_tool_python.server.subprocess.Popen", return_value=mock_proc
            ),
            patch("language_tool_python.server._RUNNING_SERVER_PROCESSES", running),
            patch.object(lt, "_wait_for_server_ready"),
        ):
            lt._start_local_server()
        assert mock_proc in running
        lt._server = None


class TestWaitForServerReady:
    """Tests for _wait_for_server_ready() error branches."""

    def test_raises_when_server_is_none(self) -> None:
        """Raises ServerError when _server is None."""
        lt = _bare_lt(_server=None)
        with pytest.raises(ServerError, match="Server process is not initialized"):
            lt._wait_for_server_ready()

    def test_raises_when_server_process_exits_early(self) -> None:
        """Raises ServerError when server poll() returns a non-None exit code."""
        mock_proc = _MockProcess(poll_return=1)
        lt = _bare_lt()
        lt._server = mock_proc  # type: ignore[assignment]
        with pytest.raises(ServerError, match="exited early"):
            lt._wait_for_server_ready()

    def test_raises_when_timeout_expires_before_server_responds(self) -> None:
        """Raises ServerError when the server does not respond within timeout."""
        mock_proc = _MockProcess(poll_return=None)
        lt = _bare_lt()
        lt._server = mock_proc  # type: ignore[assignment]
        with pytest.raises(ServerError, match="did not become ready"):
            lt._wait_for_server_ready(timeout=0)
        lt._server = None  # prevent GC __del__ re-triggering

    def test_returns_when_server_responds_ok(self) -> None:
        """Returns without error when the healthcheck endpoint responds HTTP 200."""
        mock_proc = _MockProcess(poll_return=None)
        r = _make_json_response(b"OK", status_code=200)
        lt = _bare_lt()
        lt._server = mock_proc  # type: ignore[assignment]
        lt._session = _MockSession(get_response=r)
        lt._wait_for_server_ready(timeout=10)
        lt._server = None

    def test_sleeps_when_server_not_ready_yet(self) -> None:
        """time.sleep() is called when server responds but r.ok is False."""
        mock_proc = _MockProcess(poll_return=None)
        r = _make_json_response(b"not ready", status_code=503)
        lt = _bare_lt()
        lt._server = mock_proc  # type: ignore[assignment]
        lt._session = _MockSession(get_response=r)
        times: list[float] = [0.0, 0.0, 2.0]
        with (
            patch("language_tool_python.server.time.time", side_effect=times),
            patch("language_tool_python.server.time.sleep") as mock_sleep,
            pytest.raises(ServerError, match="did not become ready"),
        ):
            lt._wait_for_server_ready(timeout=1)
        mock_sleep.assert_called_once_with(0.2)
        lt._server = None


class TestTerminateServerAtExit:
    """Tests for the atexit handler."""

    def test_logs_and_kills_when_processes_are_running(self) -> None:
        """Logger and _kill_processes are called when processes exist."""
        mock_proc = _MockProcess()
        with (
            patch(
                "language_tool_python.server._RUNNING_SERVER_PROCESSES",
                [mock_proc],
            ),
            patch("language_tool_python.server._kill_processes") as mock_kill,
        ):
            _terminate_server_at_exit()
        mock_kill.assert_called_once()


class TestLanguageToolConstructorLocalServer:
    """Tests for __init__ branches that start a local server or register spellings."""

    def test_constructor_starts_local_server_when_no_remote(self) -> None:
        """Local server startup is triggered when no remote_server is given."""
        with (
            patch("language_tool_python.server.get_locale_language", return_value="en"),
            patch.object(LanguageTool, "_get_languages", return_value=_LANGUAGES),
            patch.object(LanguageTool, "_start_server_on_free_port") as mock_start,
            LanguageTool() as _lt,
        ):
            mock_start.assert_called_once()

    def test_constructor_registers_new_spellings_when_provided(self) -> None:
        """New spellings are registered when the new_spellings arg is non-empty."""
        with (
            patch("language_tool_python.server.get_locale_language", return_value="en"),
            patch.object(LanguageTool, "_get_languages", return_value=_LANGUAGES),
            patch.object(LanguageTool, "_start_server_on_free_port"),
            patch.object(LanguageTool, "_register_spellings") as mock_reg,
            LanguageTool(new_spellings=["hello"]) as _lt,
        ):
            mock_reg.assert_called_once()


class TestLanguageToolPublicAPI:
    """Tests for LanguageToolPublicAPI constructor."""

    def test_initializes_with_public_api_remote_server(self) -> None:
        """LanguageToolPublicAPI sets is_remote=True via the public API URL."""
        with (
            patch("language_tool_python.server.get_locale_language", return_value="en"),
            patch.object(LanguageTool, "_get_languages", return_value=_LANGUAGES),
            LanguageToolPublicAPI() as lt,
        ):
            assert lt.is_remote is True
