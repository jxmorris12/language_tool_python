"""Unit tests for download_lt.py helpers (no network, no Java required).

Note: test_download.py calls importlib.reload(download_lt) which invalidates
static class imports. We access classes via the module object (updated in-place
by reload) to ensure isinstance checks work regardless of test ordering.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest

import language_tool_python.download_lt as _dl
from language_tool_python.exceptions import PathError

if TYPE_CHECKING:
    from pathlib import Path

_JAVA_8_MINOR = 8
_JAVA_17_MAJOR = 17
_JAVA_21_MAJOR = 21
_SHA256_HEX_LENGTH = 64
_KIBIBYTE = 1024


def return_42(_: object) -> int:
    """Return 42, used for monkeypatching."""
    return 42


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
