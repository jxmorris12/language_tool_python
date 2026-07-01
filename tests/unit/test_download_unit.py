"""Unit tests for download_lt.py helpers (no network, no Java required).

Note: test_download.py calls importlib.reload(download_lt) which invalidates
static class imports. We access classes via the module object (updated in-place
by reload) to ensure isinstance checks work regardless of test ordering.
"""

from __future__ import annotations

import re
import subprocess
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import pytest

import language_tool_python.download_lt as _dl
from language_tool_python.config_file import LanguageToolConfig
from language_tool_python.exceptions import JavaError, PathError

if TYPE_CHECKING:
    from pathlib import Path

_JAVA_8_MINOR = 8
_JAVA_17_MAJOR = 17
_JAVA_21_MAJOR = 21
_SHA256_HEX_LENGTH = 64
_KIBIBYTE = 1024
_SNAPSHOT_TEST_VERSION = "20240315"
_SNAPSHOT_TEST_YEAR = 2024
_SNAPSHOT_TEST_MONTH = 3
_SNAPSHOT_TEST_DAY = 15


def return_42(_: object) -> int:
    """Return 42, used for monkeypatching."""
    return 42


def _which_none(_name: str) -> str | None:
    """Stub for shutil.which that always returns None (Java not found)."""
    return None


def _which_java(_name: str) -> str:
    """Stub for shutil.which that always returns a fake Java path."""
    return "/usr/bin/java"


def _check_output_java8(*_args: object, **_kw: object) -> str:
    """Stub for subprocess.check_output returning a Java 1.8 version string."""
    return 'java version "1.8.0_292"'


def _check_output_java17(*_args: object, **_kw: object) -> str:
    """Stub for subprocess.check_output returning a Java 17 version string."""
    return "openjdk 17.0.1 2021-10-19"


def _check_output_java9(*_args: object, **_kw: object) -> str:
    """Stub for subprocess.check_output returning a Java 9 version string."""
    return 'java version "9.0.4"'


def _noop(_v: object) -> None:
    """No-operation stub for monkeypatching void functions."""


class TestLoadsManifest:
    """Tests for the _loads_manifest() TOML parser."""

    def test_valid_toml_returns_dict(self) -> None:
        """Valid TOML input returns a dict."""
        result = _dl._loads_manifest('[hashes]\n"6.8" = "abc"\n')
        assert isinstance(result, dict)

    def test_empty_toml(self) -> None:
        """Empty TOML input returns an empty dict."""
        result = _dl._loads_manifest("")
        assert result == {}


class TestLoadExpectedDownloadSha256:
    """Tests for _load_expected_download_sha256()."""

    def test_valid_manifest(self) -> None:
        """A well-formed hash entry is parsed to version → hash mapping."""
        sha = "a" * _SHA256_HEX_LENGTH
        result = _dl._load_expected_download_sha256(f'"6.8" = "{sha}"\n')
        assert result["6.8"] == sha

    def test_non_dict_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A manifest that does not parse to a dict raises PathError."""
        monkeypatch.setattr(
            "language_tool_python.download_lt._loads_manifest",
            return_42,
        )
        with pytest.raises(PathError, match="expected a TOML table"):
            _dl._load_expected_download_sha256("anything")

    def test_non_string_value_raises(self) -> None:
        """A non-string hash value in the manifest raises PathError."""
        with pytest.raises(PathError, match="expected string keys and values"):
            _dl._load_expected_download_sha256('"6.8" = 42\n')


class TestValidateDownloadSize:
    """Tests for the _validate_download_size() Content-Length checker."""

    def test_none_returns_none(self) -> None:
        """None input (missing header) returns None."""
        assert _dl._validate_download_size(None) is None

    def test_valid_size(self) -> None:
        """A numeric size string is converted to an int."""
        assert _dl._validate_download_size("1024") == _KIBIBYTE

    def test_zero_is_valid(self) -> None:
        """Zero is a valid content-length."""
        assert _dl._validate_download_size("0") == 0

    def test_invalid_string_raises(self) -> None:
        """A non-numeric string raises PathError."""
        with pytest.raises(PathError, match="Invalid Content-Length"):
            _dl._validate_download_size("notanumber")

    def test_negative_raises(self) -> None:
        """A negative value raises PathError."""
        with pytest.raises(PathError, match="Invalid Content-Length"):
            _dl._validate_download_size("-1")

    def test_too_large_raises(self) -> None:
        """A size exceeding the maximum raises PathError."""
        with pytest.raises(PathError, match="Refusing to download"):
            _dl._validate_download_size(str(512 * 1024 * 1024 + 1))


class TestParseJavaVersion:
    """Tests for _parse_java_version() version string parsing."""

    def test_old_format_quoted(self) -> None:
        """The old 'java version "1.8.0_N"' format is parsed to (1, 8)."""
        text = 'java version "1.8.0_292"'
        major, minor = _dl._parse_java_version(text)
        assert major == 1
        assert minor == _JAVA_8_MINOR

    def test_new_format_17(self) -> None:
        """The new 'openjdk N.M.P' format is parsed to (17, 0)."""
        text = "openjdk 17.0.1 2021-10-19"
        major, minor = _dl._parse_java_version(text)
        assert major == _JAVA_17_MAJOR
        assert minor == 0

    def test_new_format_21(self) -> None:
        """The new quoted 'openjdk version "21.0.2"' format is parsed to (21, ...)."""
        text = 'openjdk version "21.0.2" 2024-01-16'
        major, _ = _dl._parse_java_version(text)
        assert major == _JAVA_21_MAJOR

    def test_unparseable_raises(self) -> None:
        """A string that matches no known pattern causes SystemExit."""
        with pytest.raises(SystemExit, match="Could not parse"):
            _dl._parse_java_version("not a java version string")

    def test_multiline_output(self) -> None:
        """Multiline java -version output is parsed from the first line."""
        text = (
            'openjdk version "21.0.2" 2024-01-16\n'
            "OpenJDK Runtime Environment (build 21.0.2+13)\n"
            "OpenJDK 64-Bit Server VM (build 21.0.2+13, mixed mode, sharing)\n"
        )
        major, _ = _dl._parse_java_version(text)
        assert major == _JAVA_21_MAJOR


class TestLocalLanguageToolFromVersionName:
    """Tests for LocalLanguageTool.from_version_name() factory method."""

    def test_release_version(self) -> None:
        """An 'X.Y' string returns a ReleaseLocalLanguageTool instance."""
        lt = _dl.LocalLanguageTool.from_version_name("6.8")
        assert isinstance(lt, _dl.ReleaseLocalLanguageTool)

    def test_snapshot_date_version(self) -> None:
        """A 'YYYYMMDD' string returns a SnapshotLocalLanguageTool instance."""
        lt = _dl.LocalLanguageTool.from_version_name("20240101")
        assert isinstance(lt, _dl.SnapshotLocalLanguageTool)

    def test_snapshot_latest(self) -> None:
        """'latest' returns a SnapshotLocalLanguageTool instance."""
        lt = _dl.LocalLanguageTool.from_version_name("latest")
        assert isinstance(lt, _dl.SnapshotLocalLanguageTool)

    def test_unknown_format_raises(self) -> None:
        """An unrecognized version string raises ValueError."""
        with pytest.raises(ValueError, match="Unknown LanguageTool version"):
            _dl.LocalLanguageTool.from_version_name("unknown-format")

    def test_default_version(self) -> None:
        """Calling without arguments returns the default release version."""
        lt = _dl.LocalLanguageTool.from_version_name()
        assert isinstance(lt, _dl.ReleaseLocalLanguageTool)


class TestLocalLanguageToolFromPath:
    """Tests for LocalLanguageTool.from_path() directory-name parser."""

    def test_valid_release_path(self, tmp_path: Path) -> None:
        """A 'LanguageTool-X.Y' directory name returns a ReleaseLocalLanguageTool."""
        d = tmp_path / "LanguageTool-6.8"
        lt = _dl.LocalLanguageTool.from_path(d)
        assert isinstance(lt, _dl.ReleaseLocalLanguageTool)

    def test_valid_snapshot_path(self, tmp_path: Path) -> None:
        """A 'LanguageTool-YYYYMMDD' directory returns a SnapshotLocalLanguageTool."""
        d = tmp_path / "LanguageTool-20240101"
        lt = _dl.LocalLanguageTool.from_path(d)
        assert isinstance(lt, _dl.SnapshotLocalLanguageTool)

    def test_invalid_path_raises(self, tmp_path: Path) -> None:
        """A directory name without the expected pattern raises ValueError."""
        d = tmp_path / "not-a-lt-dir"
        with pytest.raises(ValueError, match="Could not determine"):
            _dl.LocalLanguageTool.from_path(d)


class TestReleaseLocalLanguageTool:
    """Tests for ReleaseLocalLanguageTool attributes and ordering."""

    def test_version_name(self) -> None:
        """The version_name attribute reflects the version given at construction."""
        lt = _dl.ReleaseLocalLanguageTool("6.8")
        assert lt.version_name == "6.8"

    def test_eq(self) -> None:
        """Two instances with the same version are equal."""
        a = _dl.ReleaseLocalLanguageTool("6.8")
        b = _dl.ReleaseLocalLanguageTool("6.8")
        assert a == b

    def test_neq(self) -> None:
        """Instances with different versions are not equal."""
        a = _dl.ReleaseLocalLanguageTool("6.8")
        b = _dl.ReleaseLocalLanguageTool("6.7")
        assert a != b

    def test_lt(self) -> None:
        """An older version is less than a newer version."""
        old = _dl.ReleaseLocalLanguageTool("6.7")
        new = _dl.ReleaseLocalLanguageTool("6.8")
        assert old < new

    def test_hash(self) -> None:
        """Equal instances produce the same hash."""
        a = _dl.ReleaseLocalLanguageTool("6.8")
        b = _dl.ReleaseLocalLanguageTool("6.8")
        assert hash(a) == hash(b)

    def test_in_set(self) -> None:
        """Duplicate instances collapse to one element in a set."""
        s = {_dl.ReleaseLocalLanguageTool("6.8"), _dl.ReleaseLocalLanguageTool("6.8")}
        assert len(s) == 1

    def test_download_url_new_version(self) -> None:
        """The download URL for a recent version contains the version string."""
        lt = _dl.ReleaseLocalLanguageTool("6.8")
        assert "6.8" in lt.download_url

    def test_download_url_old_version_uses_archive(self) -> None:
        """The download URL for an old version also contains the version string."""
        lt = _dl.ReleaseLocalLanguageTool("4.0")
        assert "4.0" in lt.download_url


class TestSnapshotLocalLanguageTool:
    """Tests for SnapshotLocalLanguageTool attributes and equality."""

    def test_version_name_date(self) -> None:
        """A date-format version name is stored as-is."""
        lt = _dl.SnapshotLocalLanguageTool("20240101")
        assert lt.version_name == "20240101"

    def test_version_name_latest_expands_to_date(self) -> None:
        """'latest' expands to an 8-digit date string."""
        lt = _dl.SnapshotLocalLanguageTool("latest")
        assert re.match(r"^\d{8}$", lt.version_name)

    def test_eq(self) -> None:
        """Two instances with the same date are equal."""
        a = _dl.SnapshotLocalLanguageTool("20240101")
        b = _dl.SnapshotLocalLanguageTool("20240101")
        assert a == b

    def test_neq(self) -> None:
        """Instances with different dates are not equal."""
        a = _dl.SnapshotLocalLanguageTool("20240101")
        b = _dl.SnapshotLocalLanguageTool("20240201")
        assert a != b

    def test_hash(self) -> None:
        """Equal instances produce the same hash."""
        a = _dl.SnapshotLocalLanguageTool("20240101")
        b = _dl.SnapshotLocalLanguageTool("20240101")
        assert hash(a) == hash(b)


class TestGetZipHash:
    """Tests for _get_zip_hash() SHA-256 lookup."""

    def test_bypass_env_returns_none_with_warning(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """LTP_BYPASS_VERIFIED_DOWNLOADS=true skips verification with a warning."""
        monkeypatch.setenv("LTP_BYPASS_VERIFIED_DOWNLOADS", "true")
        with pytest.warns(RuntimeWarning, match="bypassed"):
            result = _dl._get_zip_hash("6.8")
        assert result is None

    def test_known_version_returns_hash(self) -> None:
        """A version present in the integrity manifest returns a 64-char hex hash."""
        if not _dl._EXPECTED_DOWNLOAD_SHA256:
            pytest.skip("No known hashes in manifest")
        version_name = next(iter(_dl._EXPECTED_DOWNLOAD_SHA256))
        result = _dl._get_zip_hash(version_name)
        assert result is not None
        assert len(result) == _SHA256_HEX_LENGTH

    def test_unknown_version_returns_none(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A version absent from the manifest returns None."""
        monkeypatch.delenv("LTP_BYPASS_VERIFIED_DOWNLOADS", raising=False)
        result = _dl._get_zip_hash("0.0")
        assert result is None

    def test_invalid_hash_in_env_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """An invalid SHA-256 value in LTP_DOWNLOAD_SHA256 raises PathError."""
        monkeypatch.setenv("LTP_DOWNLOAD_SHA256", "not-a-valid-sha256")
        with pytest.raises(PathError, match="Invalid SHA-256"):
            _dl._get_zip_hash("6.8")


class TestConfirmJavaCompatibility:
    """Tests for _confirm_java_compatibility() Java version checker."""

    def test_no_java_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Raises ModuleNotFoundError when Java cannot be found on PATH."""
        monkeypatch.setattr("language_tool_python.download_lt.which", _which_none)
        with pytest.raises(ModuleNotFoundError, match="No java install"):
            _dl._confirm_java_compatibility("6.8")

    def test_java_8_fails_for_current_lt(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Java 1.8 raises SystemError when current LT requires Java >= 17."""
        monkeypatch.setattr("language_tool_python.download_lt.which", _which_java)
        monkeypatch.setattr(subprocess, "check_output", _check_output_java8)
        with pytest.raises(SystemError, match="requires"):
            _dl._confirm_java_compatibility("6.8")

    def test_java_8_fails_for_old_lt(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Java 1.8 raises SystemError for an old LT version requiring Java >= 9."""
        monkeypatch.setattr("language_tool_python.download_lt.which", _which_java)
        monkeypatch.setattr(subprocess, "check_output", _check_output_java8)
        with pytest.raises(SystemError, match="requires"):
            _dl._confirm_java_compatibility("5.0")

    def test_java_17_passes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Java 17 satisfies the current LT requirement without error."""
        monkeypatch.setattr("language_tool_python.download_lt.which", _which_java)
        monkeypatch.setattr(subprocess, "check_output", _check_output_java17)
        _dl._confirm_java_compatibility("6.8")

    def test_java_9_passes_for_old_lt(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Java 9 satisfies an old LT version's lower requirement without error."""
        monkeypatch.setattr("language_tool_python.download_lt.which", _which_java)
        monkeypatch.setattr(subprocess, "check_output", _check_output_java9)
        _dl._confirm_java_compatibility("5.0")


class TestGetInstalledVersions:
    """Tests for LocalLanguageTool.get_installed_versions()."""

    def test_returns_empty_when_no_lt_dirs(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Returns an empty list when no LanguageTool directories are present."""
        monkeypatch.setenv("LTP_PATH", str(tmp_path))
        versions = _dl.LocalLanguageTool.get_installed_versions()
        assert versions == []

    def test_returns_installed_versions(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Returns a sorted list of installed LocalLanguageTool instances."""
        (tmp_path / "LanguageTool-6.8").mkdir()
        (tmp_path / "LanguageTool-6.7").mkdir()
        monkeypatch.setenv("LTP_PATH", str(tmp_path))
        versions = _dl.LocalLanguageTool.get_installed_versions()
        version_names = [v.version_name for v in versions]
        assert "6.8" in version_names
        assert "6.7" in version_names

    def test_skips_malformed_version_directory(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """A directory matching 'LanguageTool-*' but with an unparseable version name
        is silently skipped (the ValueError from from_path() is suppressed) rather
        than propagating.
        """  # noqa: D205
        (tmp_path / "LanguageTool-not-a-real-version").mkdir()
        (tmp_path / "LanguageTool-6.8").mkdir()
        monkeypatch.setenv("LTP_PATH", str(tmp_path))
        versions = _dl.LocalLanguageTool.get_installed_versions()
        version_names = [v.version_name for v in versions]
        assert version_names == ["6.8"]


class TestGetLatestInstalledVersion:
    """Tests for LocalLanguageTool.get_latest_installed_version()."""

    def test_returns_none_when_no_versions(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Returns None when no LanguageTool versions are installed."""
        monkeypatch.setenv("LTP_PATH", str(tmp_path))
        result = _dl.LocalLanguageTool.get_latest_installed_version()
        assert result is None

    def test_returns_latest_version(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Returns the highest-ordered installed version."""
        (tmp_path / "LanguageTool-6.7").mkdir()
        (tmp_path / "LanguageTool-6.8").mkdir()
        monkeypatch.setenv("LTP_PATH", str(tmp_path))
        result = _dl.LocalLanguageTool.get_latest_installed_version()
        assert result is not None
        assert result.version_name == "6.8"


class TestGetDirectoryPath:
    """Tests for LocalLanguageTool.get_directory_path()."""

    def test_no_lt_dirs_raises(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Raises FileNotFoundError when no LanguageTool directories exist."""
        monkeypatch.setenv("LTP_PATH", str(tmp_path))
        lt = _dl.ReleaseLocalLanguageTool("6.8")
        with pytest.raises(FileNotFoundError, match="LanguageTool not found"):
            lt.get_directory_path()

    def test_version_not_found_raises(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Raises FileNotFoundError when the requested version is not installed."""
        (tmp_path / "LanguageTool-6.7").mkdir()
        monkeypatch.setenv("LTP_PATH", str(tmp_path))
        lt = _dl.ReleaseLocalLanguageTool("6.8")
        with pytest.raises(FileNotFoundError, match=r"6\.8"):
            lt.get_directory_path()

    def test_returns_matching_directory(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Returns the directory path when the version directory exists."""
        lt_dir = tmp_path / "LanguageTool-6.8"
        lt_dir.mkdir()
        monkeypatch.setenv("LTP_PATH", str(tmp_path))
        lt = _dl.ReleaseLocalLanguageTool("6.8")
        assert lt.get_directory_path() == lt_dir


class TestGetJarPath:
    """Tests for LocalLanguageTool.get_jar_path()."""

    def test_no_jar_raises(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Raises FileNotFoundError when no JAR file exists in the LT directory."""
        (tmp_path / "LanguageTool-6.8").mkdir()
        monkeypatch.setenv("LTP_PATH", str(tmp_path))
        lt = _dl.ReleaseLocalLanguageTool("6.8")
        with pytest.raises(FileNotFoundError, match="JAR not found"):
            lt.get_jar_path()

    def test_finds_server_jar(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Returns the path to languagetool-server.jar when it exists."""
        lt_dir = tmp_path / "LanguageTool-6.8"
        lt_dir.mkdir()
        jar = lt_dir / "languagetool-server.jar"
        jar.touch()
        monkeypatch.setenv("LTP_PATH", str(tmp_path))
        lt = _dl.ReleaseLocalLanguageTool("6.8")
        assert lt.get_jar_path() == jar


class TestGetServerCmd:
    """Tests for LocalLanguageTool.get_server_cmd()."""

    def test_no_java_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Raises JavaError when Java is not found on PATH."""
        monkeypatch.setattr("language_tool_python.download_lt.which", _which_none)
        lt = _dl.ReleaseLocalLanguageTool("6.8")
        with pytest.raises(JavaError, match="can't find Java"):
            lt.get_server_cmd()

    def test_without_port_or_config(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """The command contains java and jar path when no extras are given."""
        lt_dir = tmp_path / "LanguageTool-6.8"
        lt_dir.mkdir()
        (lt_dir / "languagetool-server.jar").touch()
        monkeypatch.setenv("LTP_PATH", str(tmp_path))
        monkeypatch.setattr("language_tool_python.download_lt.which", _which_java)
        lt = _dl.ReleaseLocalLanguageTool("6.8")
        cmd = lt.get_server_cmd()
        assert "java" in cmd[0]
        assert "languagetool-server.jar" in cmd[2]

    def test_with_port(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """The generated command includes -p when a port is specified."""
        lt_dir = tmp_path / "LanguageTool-6.8"
        lt_dir.mkdir()
        (lt_dir / "languagetool-server.jar").touch()
        monkeypatch.setenv("LTP_PATH", str(tmp_path))
        monkeypatch.setattr("language_tool_python.download_lt.which", _which_java)
        lt = _dl.ReleaseLocalLanguageTool("6.8")
        cmd = lt.get_server_cmd(port=8081)
        assert "-p" in cmd
        assert "8081" in cmd

    def test_with_config(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """The generated command includes --config when a config object is given."""
        lt_dir = tmp_path / "LanguageTool-6.8"
        lt_dir.mkdir()
        (lt_dir / "languagetool-server.jar").touch()
        monkeypatch.setenv("LTP_PATH", str(tmp_path))
        monkeypatch.setattr("language_tool_python.download_lt.which", _which_java)
        lt = _dl.ReleaseLocalLanguageTool("6.8")
        config = LanguageToolConfig({"cacheSize": 500})
        cmd = lt.get_server_cmd(config=config)
        assert "--config" in cmd


class TestLocalLanguageToolComparisons:
    """Tests for LocalLanguageTool.__eq__ and __lt__ cross-type behaviours."""

    def test_eq_with_non_lt_returns_not_implemented(self) -> None:
        """__eq__ returns NotImplemented for non-LocalLanguageTool objects."""
        lt = _dl.ReleaseLocalLanguageTool("6.8")
        result = lt.__eq__("not-a-lt")
        assert result is NotImplemented

    def test_snapshot_lt_release_is_false(self) -> None:
        """A Snapshot is never less than a Release (Snapshots are always newer)."""
        snap = _dl.SnapshotLocalLanguageTool("20240101")
        rel = _dl.ReleaseLocalLanguageTool("6.8")
        assert not (snap < rel)

    def test_release_lt_snapshot_is_true(self) -> None:
        """A Release is always less than a Snapshot (Snapshots are always newer)."""
        rel = _dl.ReleaseLocalLanguageTool("6.8")
        snap = _dl.SnapshotLocalLanguageTool("20240101")
        assert rel < snap

    def test_lt_with_third_subclass_returns_not_implemented(self) -> None:
        """__lt__ returns NotImplemented for a third LocalLanguageTool subclass."""

        class _ThirdLT(_dl.LocalLanguageTool):
            @property
            def version_name(self) -> str:
                return "third"

            @property
            def version_into(self) -> tuple[int, int] | datetime:
                return (0, 0)

            @property
            def download_url(self) -> str:
                return ""

            def download(self) -> None:
                pass

        rel = _dl.ReleaseLocalLanguageTool("6.8")
        assert rel.__lt__(_ThirdLT()) is NotImplemented

    def test_lt_same_type_mismatched_version_into_returns_not_implemented(self) -> None:
        """__lt__ returns NotImplemented when version_into types differ."""

        class _MixedLT(_dl.LocalLanguageTool):
            def __init__(self, *, use_dt: bool) -> None:
                self._use_dt = use_dt

            @property
            def version_name(self) -> str:
                return "mixed"

            @property
            def version_into(self) -> tuple[int, int] | datetime:
                if self._use_dt:
                    return datetime(2024, 1, 1, tzinfo=timezone.utc)
                return (0, 0)

            @property
            def download_url(self) -> str:
                return ""

            def download(self) -> None:
                pass

        a = _MixedLT(use_dt=False)
        b = _MixedLT(use_dt=True)
        assert a.__lt__(b) is NotImplemented


class TestSnapshotVersionInto:
    """Tests for SnapshotLocalLanguageTool.version_into property."""

    def test_returns_datetime_for_date_string(self) -> None:
        """A date version string is converted to the correct datetime."""
        lt = _dl.SnapshotLocalLanguageTool(_SNAPSHOT_TEST_VERSION)
        vi = lt.version_into
        assert isinstance(vi, datetime)
        assert vi.year == _SNAPSHOT_TEST_YEAR
        assert vi.month == _SNAPSHOT_TEST_MONTH
        assert vi.day == _SNAPSHOT_TEST_DAY


class TestReleaseDownloadUrlEdgeCases:
    """Tests for ReleaseLocalLanguageTool.download_url edge cases."""

    def test_version_below_4_0_raises(self) -> None:
        """Versions below 4.0 are not supported and raise PathError."""
        lt = _dl.ReleaseLocalLanguageTool("3.9")
        with pytest.raises(PathError, match="no longer supported"):
            _ = lt.download_url

    def test_version_6_0_uses_release_url(self) -> None:
        """Versions 6.0-6.6 use the main release download URL."""
        lt = _dl.ReleaseLocalLanguageTool("6.0")
        assert "6.0" in lt.download_url


class TestDownloadEarlyReturn:
    """Tests for LocalLanguageTool.download() early-return via LTP_JAR_DIR_PATH."""

    def test_release_download_skips_when_jar_dir_set(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """download() exits without network access when LTP_JAR_DIR_PATH is set."""
        monkeypatch.setattr(
            "language_tool_python.download_lt._confirm_java_compatibility",
            _noop,
        )
        monkeypatch.setenv("LTP_PATH", str(tmp_path))
        monkeypatch.setenv("LTP_JAR_DIR_PATH", str(tmp_path))
        _dl.ReleaseLocalLanguageTool("6.8").download()

    def test_snapshot_download_skips_when_jar_dir_set(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Snapshot download() skips the network when LTP_JAR_DIR_PATH is set."""
        monkeypatch.setattr(
            "language_tool_python.download_lt._confirm_java_compatibility",
            _noop,
        )
        monkeypatch.setenv("LTP_PATH", str(tmp_path))
        monkeypatch.setenv("LTP_JAR_DIR_PATH", str(tmp_path))
        _dl.SnapshotLocalLanguageTool("20240101").download()

    def test_release_download_skips_when_already_installed(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """download() skips the network when the release is already installed."""
        monkeypatch.setattr(
            "language_tool_python.download_lt._confirm_java_compatibility",
            _noop,
        )
        monkeypatch.delenv("LTP_JAR_DIR_PATH", raising=False)
        monkeypatch.setenv("LTP_PATH", str(tmp_path))
        (tmp_path / "LanguageTool-6.8").mkdir()
        _dl.ReleaseLocalLanguageTool("6.8").download()
