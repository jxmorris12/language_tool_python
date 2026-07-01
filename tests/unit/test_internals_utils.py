"""Unit tests for language_tool_python._internals.utils."""

from __future__ import annotations

from typing import TYPE_CHECKING

import psutil
import pytest

from language_tool_python._internals.utils import (
    get_env_float,
    get_env_int,
    get_language_tool_download_path,
    get_locale_language,
    kill_process_force,
    parse_url,
    version_tuple,
)
from language_tool_python.exceptions import PathError

if TYPE_CHECKING:
    from pathlib import Path

_DEFAULT_INT = 42
_ENV_INT_VALUE = 100
_DEFAULT_FLOAT = 1.5


class TestParseUrl:
    """Tests for parse_url() scheme normalisation."""

    def test_full_url_unchanged(self) -> None:
        """A complete http URL is returned as-is."""
        assert parse_url("http://localhost:8081") == "http://localhost:8081"

    def test_https_url_unchanged(self) -> None:
        """A complete https URL is returned as-is."""
        assert parse_url("https://example.com") == "https://example.com"

    def test_adds_http_scheme(self) -> None:
        """A host:port string without a scheme gets http:// prepended."""
        result = parse_url("localhost:8081")
        assert result.startswith("http://")
        assert "localhost" in result

    def test_canonical_form(self) -> None:
        """An already-complete URL with trailing slash is returned unchanged."""
        assert parse_url("http://localhost:8081/") == "http://localhost:8081/"


class TestGetEnvInt:
    """Tests for get_env_int() environment variable reader."""

    def test_returns_default_when_absent(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The default is returned when the variable is not set."""
        monkeypatch.delenv("TEST_INT_VAR", raising=False)
        assert get_env_int("TEST_INT_VAR", _DEFAULT_INT) == _DEFAULT_INT

    def test_reads_valid_value(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A valid integer string in the environment is returned as an int."""
        monkeypatch.setenv("TEST_INT_VAR", str(_ENV_INT_VALUE))
        assert get_env_int("TEST_INT_VAR", 0) == _ENV_INT_VALUE

    def test_raises_on_non_integer(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A non-numeric string raises PathError."""
        monkeypatch.setenv("TEST_INT_VAR", "notanint")
        with pytest.raises(PathError, match="Invalid integer"):
            get_env_int("TEST_INT_VAR", 0)

    def test_raises_on_zero(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Zero is not a valid positive integer and raises PathError."""
        monkeypatch.setenv("TEST_INT_VAR", "0")
        with pytest.raises(PathError, match="Invalid integer"):
            get_env_int("TEST_INT_VAR", 0)

    def test_raises_on_negative(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A negative integer string raises PathError."""
        monkeypatch.setenv("TEST_INT_VAR", "-5")
        with pytest.raises(PathError, match="Invalid integer"):
            get_env_int("TEST_INT_VAR", 0)


class TestGetEnvFloat:
    """Tests for get_env_float() environment variable reader."""

    def test_returns_default_when_absent(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The default is returned when the variable is not set."""
        monkeypatch.delenv("TEST_FLOAT_VAR", raising=False)
        assert get_env_float("TEST_FLOAT_VAR", _DEFAULT_FLOAT) == _DEFAULT_FLOAT

    def test_reads_valid_value(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A valid float string is returned as a float."""
        monkeypatch.setenv("TEST_FLOAT_VAR", "3.14")
        assert get_env_float("TEST_FLOAT_VAR", 0.0) == pytest.approx(3.14)

    def test_raises_on_non_float(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A non-numeric string raises PathError."""
        monkeypatch.setenv("TEST_FLOAT_VAR", "notafloat")
        with pytest.raises(PathError, match="Invalid float"):
            get_env_float("TEST_FLOAT_VAR", 0.0)

    def test_raises_on_zero(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Zero is not a valid positive float and raises PathError."""
        monkeypatch.setenv("TEST_FLOAT_VAR", "0.0")
        with pytest.raises(PathError, match="Invalid float"):
            get_env_float("TEST_FLOAT_VAR", 1.0)

    def test_raises_on_negative(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A negative float string raises PathError."""
        monkeypatch.setenv("TEST_FLOAT_VAR", "-1.0")
        with pytest.raises(PathError, match="Invalid float"):
            get_env_float("TEST_FLOAT_VAR", 1.0)


class TestGetLanguageToolDownloadPath:
    """Tests for get_language_tool_download_path() path resolver."""

    def test_returns_path(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """The returned path exists and is a directory."""
        monkeypatch.setenv("LTP_PATH", str(tmp_path))
        path = get_language_tool_download_path()
        assert path.exists()
        assert path.is_dir()

    def test_creates_directory(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """A non-existent directory under LTP_PATH is created on first use."""
        new_dir = tmp_path / "new_subdir"
        monkeypatch.setenv("LTP_PATH", str(new_dir))
        path = get_language_tool_download_path()
        assert path.exists()

    def test_default_path_in_home(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Without LTP_PATH, the default path contains 'language_tool_python'."""
        monkeypatch.delenv("LTP_PATH", raising=False)
        path = get_language_tool_download_path()
        assert "language_tool_python" in str(path)


class TestGetLocaleLanguage:
    """Tests for get_locale_language() system locale lookup."""

    def test_returns_string(self) -> None:
        """The function returns a non-empty string."""
        result = get_locale_language()
        assert isinstance(result, str)
        assert len(result) > 0


class _MockPsutilProcess:
    """Minimal stand-in for psutil.Process used in kill_process_force tests."""

    def __init__(
        self,
        pid: int,
        children: list[_MockPsutilProcess] | None = None,
        *,
        raise_on_kill: bool = False,
    ) -> None:
        """Initialise with a pid, optional children, and an optional kill() failure."""
        self.pid = pid
        self.killed = False
        self._children = children or []
        self._raise_on_kill = raise_on_kill

    def children(self, *, recursive: bool = False) -> list[_MockPsutilProcess]:  # noqa: ARG002
        """Return the configured child processes."""
        return self._children

    def kill(self) -> None:
        """Mark the process as killed, or raise NoSuchProcess if so configured."""
        if self._raise_on_kill:
            raise psutil.NoSuchProcess(self.pid)
        self.killed = True


class TestKillProcessForce:
    """Tests for kill_process_force() process terminator."""

    def test_raises_when_no_args(self) -> None:
        """Calling with neither pid nor proc raises ValueError."""
        with pytest.raises(ValueError, match="Must pass either pid or proc"):
            kill_process_force()

    def test_kills_by_pid(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A process is terminated when its pid is given."""
        mock_proc = _MockPsutilProcess(pid=123)

        def _fake_process(_pid: int) -> _MockPsutilProcess:
            return mock_proc

        monkeypatch.setattr(psutil, "Process", _fake_process)
        kill_process_force(pid=123)
        assert mock_proc.killed

    def test_kills_by_proc(self) -> None:
        """A process is terminated when a psutil.Process object is given."""
        mock_proc = _MockPsutilProcess(pid=123)
        kill_process_force(proc=mock_proc)  # type: ignore[arg-type]
        assert mock_proc.killed

    def test_kills_process_with_children(self) -> None:
        """A process and its children are all terminated."""
        child = _MockPsutilProcess(pid=456)
        parent = _MockPsutilProcess(pid=123, children=[child])
        kill_process_force(proc=parent)  # type: ignore[arg-type]
        assert child.killed
        assert parent.killed

    def test_nonexistent_pid_is_silent(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A nonexistent pid is silently ignored."""

        def _raise_no_such_process(pid: int) -> _MockPsutilProcess:
            raise psutil.NoSuchProcess(pid)

        monkeypatch.setattr(psutil, "Process", _raise_no_such_process)
        kill_process_force(pid=999999999)  # must not raise

    def test_suppresses_no_such_process_on_child_race(self) -> None:
        """A child that vanishes before kill() (NoSuchProcess) is silently skipped."""
        child = _MockPsutilProcess(pid=456, raise_on_kill=True)
        parent = _MockPsutilProcess(pid=123, children=[child])
        kill_process_force(proc=parent)  # type: ignore[arg-type]  # must not raise
        assert parent.killed

    def test_suppresses_no_such_process_on_parent_race(self) -> None:
        """A parent that vanishes before kill() (NoSuchProcess) is silently skipped."""
        parent = _MockPsutilProcess(pid=123, raise_on_kill=True)
        kill_process_force(proc=parent)  # type: ignore[arg-type]  # must not raise


class TestVersionTuple:
    """Tests for version_tuple() version string parser."""

    def test_parses_version(self) -> None:
        """A 'X.Y' version string is parsed to a (X, Y) int tuple."""
        assert version_tuple("6.8") == (6, 8)

    def test_parses_version_with_zeros(self) -> None:
        """A 'X.0' version string is parsed correctly."""
        assert version_tuple("4.0") == (4, 0)

    def test_raises_on_invalid_format(self) -> None:
        """A version string without a dot raises ValueError."""
        with pytest.raises(ValueError, match="not enough values"):
            version_tuple("invalid")
