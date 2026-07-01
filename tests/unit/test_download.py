"""Unit tests for download logic, URL construction, HTTP handling, and integrity checks.

These tests use mocks and monkeypatching to avoid real network requests.
"""

import hashlib
import io
import re
import zipfile
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest
import requests

import language_tool_python
from language_tool_python._internals.utils import get_env_int
from language_tool_python.download_lt import (
    _LTP_BYPASS_VERIFIED_DOWNLOADS_ENV_VAR,
    _LTP_DOWNLOAD_SHA256_ENV_VAR,
    _LTP_MAX_DOWNLOAD_BYTES_ENV_VAR,
    LocalLanguageTool,
)
from language_tool_python.exceptions import PathError

EXPECTED_DOWNLOAD_BYTES_OVERRIDE = 123


class MockDownloadResponse:
    """Minimal requests.Response replacement for download tests."""

    def __init__(self, payload: bytes, status_code: int = 200) -> None:
        """Initialize the mock response with the given payload and status code."""
        self.payload = payload
        self.status_code = status_code
        self.headers = {"Content-Length": str(len(payload))}

    def iter_content(self, chunk_size: int) -> Iterator[bytes]:
        """Simulate streaming content by yielding chunks of the payload.

        :param chunk_size: The size of each chunk to yield.
        :type chunk_size: int
        :return: An iterator that yields chunks of the payload.
        :rtype: Iterator[bytes]
        """
        for index in range(0, len(self.payload), chunk_size):
            yield self.payload[index : index + chunk_size]


class FixedDatetime:
    """Datetime replacement returning a configurable UTC datetime."""

    current_datetime = datetime(2024, 5, 14, tzinfo=timezone.utc)

    @classmethod
    def now(cls, _tz: timezone) -> datetime:
        """Return the configured test datetime."""
        return cls.current_datetime


def make_zip_payload(files: dict[str, bytes]) -> bytes:
    """Create an in-memory ZIP payload for download tests."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zip_file:
        for filename, payload in files.items():
            zip_file.writestr(filename, payload)
    return buffer.getvalue()


def skip_java_compatibility_check(_language_tool_version: str) -> None:
    """Skip Java compatibility checks in download-only tests."""


def test_http_get_403_forbidden() -> None:
    """Test that http_get raises PathError on a 403 Forbidden status code."""
    mock_response = MockDownloadResponse(b"", status_code=403)
    mock_response.headers = {}

    out_file = io.BytesIO()
    local_language_tool = LocalLanguageTool.from_version_name()
    with (
        patch(
            "language_tool_python.download_lt.requests.get",
            return_value=mock_response,
        ),
        pytest.raises(PathError, match="Access forbidden to URL"),
    ):
        local_language_tool._get_remote_zip(out_file)


@pytest.mark.parametrize("error_code", [500, 502, 503, 504])
def test_http_get_other_error_codes(error_code: int) -> None:
    """Test PathError handling for unexpected HTTP status codes."""
    mock_response = MockDownloadResponse(b"", status_code=error_code)
    mock_response.headers = {}

    out_file = io.BytesIO()
    local_language_tool = LocalLanguageTool.from_version_name()
    with (
        patch(
            "language_tool_python.download_lt.requests.get",
            return_value=mock_response,
        ),
        pytest.raises(PathError, match=f"Failed to download.*{error_code}"),
    ):
        local_language_tool._get_remote_zip(out_file)


def test_http_get_rejects_oversized_content_length(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that oversized ZIP downloads are rejected before streaming."""
    payload = make_zip_payload(
        {"LanguageTool-6.9-SNAPSHOT/languagetool-server.jar": b"jar"},
    )
    response = MockDownloadResponse(payload)
    response.headers["Content-Length"] = "2"
    monkeypatch.setattr(language_tool_python.download_lt, "_MAX_DOWNLOAD_BYTES", 1)

    with (
        patch(
            "language_tool_python.download_lt.requests.get",
            return_value=response,
        ),
        pytest.raises(PathError, match="Maximum allowed download size"),
    ):
        LocalLanguageTool.from_version_name()._get_remote_zip(io.BytesIO())


def test_max_download_bytes_uses_env_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that the download size limit can be configured from the environment."""
    monkeypatch.setenv(
        _LTP_MAX_DOWNLOAD_BYTES_ENV_VAR, str(EXPECTED_DOWNLOAD_BYTES_OVERRIDE)
    )

    result = get_env_int(_LTP_MAX_DOWNLOAD_BYTES_ENV_VAR, 1)
    assert result == EXPECTED_DOWNLOAD_BYTES_OVERRIDE


def test_http_get_rejects_oversized_stream(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that downloads are still size-limited when Content-Length is missing."""
    payload = make_zip_payload(
        {"LanguageTool-6.9-SNAPSHOT/languagetool-server.jar": b"jar"},
    )
    response = MockDownloadResponse(payload)
    response.headers = {}
    monkeypatch.setattr(
        language_tool_python.download_lt, "_MAX_DOWNLOAD_BYTES", len(payload) - 1
    )

    with (
        patch(
            "language_tool_python.download_lt.requests.get",
            return_value=response,
        ),
        pytest.raises(PathError, match="Refusing to download more than"),
    ):
        LocalLanguageTool.from_version_name()._get_remote_zip(io.BytesIO())


def test_http_get_rejects_oversized_stream_with_small_content_length(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that a lying Content-Length cannot bypass the streamed download limit."""
    payload = make_zip_payload(
        {"LanguageTool-6.9-SNAPSHOT/languagetool-server.jar": b"jar"},
    )
    response = MockDownloadResponse(payload)
    response.headers["Content-Length"] = "1"
    monkeypatch.setattr(
        language_tool_python.download_lt, "_MAX_DOWNLOAD_BYTES", len(payload) - 1
    )

    with (
        patch(
            "language_tool_python.download_lt.requests.get",
            return_value=response,
        ),
        pytest.raises(PathError, match="Refusing to download more than"),
    ):
        LocalLanguageTool.from_version_name()._get_remote_zip(io.BytesIO())


@pytest.mark.parametrize("content_length", ["not-a-number", "-1"])
def test_http_get_rejects_invalid_content_length(
    content_length: str,
) -> None:
    """Test that invalid Content-Length values are rejected before streaming."""
    response = MockDownloadResponse(b"")
    response.headers["Content-Length"] = content_length

    with (
        patch(
            "language_tool_python.download_lt.requests.get",
            return_value=response,
        ),
        pytest.raises(PathError, match="Invalid Content-Length"),
    ):
        LocalLanguageTool.from_version_name()._get_remote_zip(io.BytesIO())


def test_latest_snapshot_uses_latest_download_url_and_current_date(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that latest remains a snapshot alias installed under the current date."""
    monkeypatch.setattr(
        language_tool_python.download_lt,
        "_BASE_URL_SNAPSHOT",
        "https://example.test/snapshots/",
    )

    monkeypatch.setattr(
        FixedDatetime, "current_datetime", datetime(2024, 5, 14, tzinfo=timezone.utc)
    )
    monkeypatch.setattr(language_tool_python.download_lt, "datetime", FixedDatetime)
    local_language_tool = LocalLanguageTool.from_version_name("latest")

    assert local_language_tool.version_name == "20240514"
    assert (
        local_language_tool.download_url
        == "https://example.test/snapshots/LanguageTool-latest-snapshot.zip"
    )


@pytest.mark.parametrize("release_version", ["6.7", "6.8"])
def test_release_download_url_uses_new_release_base_from_6_7(
    release_version: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that releases 6.7 and newer include the version in the base URL."""
    monkeypatch.setattr(
        language_tool_python.download_lt,
        "_BASE_URL_NEW_RELEASES",
        "https://example.test/releases/LanguageTool-{version}/",
    )

    local_language_tool = LocalLanguageTool.from_version_name(release_version)

    expected_url = (
        f"https://example.test/releases/LanguageTool-{release_version}/"
        f"LanguageTool-{release_version}.zip"
    )

    assert local_language_tool.download_url == expected_url


def test_release_download_url_keeps_main_release_base_for_6_6(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that release 6.6 keeps using the versioned filename."""
    monkeypatch.setattr(
        language_tool_python.download_lt,
        "_BASE_URL_RELEASE",
        "https://example.test/download/",
    )

    local_language_tool = LocalLanguageTool.from_version_name("6.6")

    assert (
        local_language_tool.download_url
        == "https://example.test/download/LanguageTool-6.6.zip"
    )


def test_release_download_url_keeps_main_release_base_before_6_7(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that earlier 6.x releases keep using the versioned filename."""
    monkeypatch.setattr(
        language_tool_python.download_lt,
        "_BASE_URL_RELEASE",
        "https://example.test/download/",
    )

    local_language_tool = LocalLanguageTool.from_version_name("6.5")

    assert (
        local_language_tool.download_url
        == "https://example.test/download/LanguageTool-6.5.zip"
    )


def test_release_download_url_keeps_archive_base_before_6_0(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that older supported releases keep using the archive base URL."""
    monkeypatch.setattr(
        language_tool_python.download_lt,
        "_BASE_URL_ARCHIVE",
        "https://example.test/archive/",
    )

    local_language_tool = LocalLanguageTool.from_version_name("5.9")

    assert (
        local_language_tool.download_url
        == "https://example.test/archive/LanguageTool-5.9.zip"
    )


def test_http_get_verifies_configured_sha256(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that downloads are accepted when the configured SHA-256 matches."""
    payload = make_zip_payload(
        {"LanguageTool-6.9-SNAPSHOT/languagetool-server.jar": b"jar"},
    )
    local_language_tool = LocalLanguageTool.from_version_name()
    suffix = (
        re.sub(r"[^A-Za-z0-9]+", "_", local_language_tool.version_name)
        .strip("_")
        .upper()
    )
    version_env_var = f"LTP_DOWNLOAD_SHA256_{suffix}"
    monkeypatch.setenv(
        version_env_var,
        hashlib.sha256(payload).hexdigest(),
    )

    with patch(
        "language_tool_python.download_lt.requests.get",
        return_value=MockDownloadResponse(payload),
    ):
        out_file = io.BytesIO()
        with local_language_tool._get_remote_zip(out_file) as zip_file:
            assert zip_file.namelist() == [
                "LanguageTool-6.9-SNAPSHOT/languagetool-server.jar",
            ]


def test_http_get_uses_integrity_manifest_sha256(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that bundled integrity.toml checksums are used when no env var is set."""
    payload = make_zip_payload({"LanguageTool-4.0/languagetool-server.jar": b"jar"})
    local_language_tool = LocalLanguageTool.from_version_name("4.0")
    monkeypatch.delenv(_LTP_BYPASS_VERIFIED_DOWNLOADS_ENV_VAR, raising=False)
    monkeypatch.delenv(_LTP_DOWNLOAD_SHA256_ENV_VAR, raising=False)
    monkeypatch.delenv("LTP_DOWNLOAD_SHA256_4_0", raising=False)

    with (
        patch(
            "language_tool_python.download_lt.requests.get",
            return_value=MockDownloadResponse(payload),
        ),
        pytest.raises(PathError, match="checksum mismatch"),
    ):
        local_language_tool._get_remote_zip(io.BytesIO())


def test_http_get_rejects_sha256_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that downloads are rejected when the configured SHA-256 mismatches."""
    payload = make_zip_payload(
        {"LanguageTool-6.9-SNAPSHOT/languagetool-server.jar": b"jar"},
    )
    local_language_tool = LocalLanguageTool.from_version_name()
    suffix = (
        re.sub(r"[^A-Za-z0-9]+", "_", local_language_tool.version_name)
        .strip("_")
        .upper()
    )
    version_env_var = f"LTP_DOWNLOAD_SHA256_{suffix}"
    monkeypatch.setenv(
        version_env_var,
        "0" * 64,
    )

    out_file = io.BytesIO()
    with (
        patch(
            "language_tool_python.download_lt.requests.get",
            return_value=MockDownloadResponse(payload),
        ),
        pytest.raises(PathError, match="checksum mismatch"),
    ):
        local_language_tool._get_remote_zip(out_file)


def test_http_get_bypass_skips_sha256_verification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that the bypass disables SHA-256 verification."""
    payload = make_zip_payload(
        {"LanguageTool-6.9-SNAPSHOT/languagetool-server.jar": b"jar"},
    )
    local_language_tool = LocalLanguageTool.from_version_name()
    monkeypatch.setenv(_LTP_BYPASS_VERIFIED_DOWNLOADS_ENV_VAR, "true")
    monkeypatch.setenv(_LTP_DOWNLOAD_SHA256_ENV_VAR, "0" * 64)

    out_file = io.BytesIO()
    with (
        patch(
            "language_tool_python.download_lt.requests.get",
            return_value=MockDownloadResponse(payload),
        ),
        pytest.warns(RuntimeWarning, match="Verified downloads are bypassed"),
        local_language_tool._get_remote_zip(out_file) as zip_file,
    ):
        assert zip_file.namelist() == [
            "LanguageTool-6.9-SNAPSHOT/languagetool-server.jar",
        ]


def test_snapshot_download_renames_archive_root_to_requested_date(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Test that date-pinned snapshots are installed under the requested date name."""
    requested_snapshot = "20240101"
    payload = make_zip_payload(
        {"LanguageTool-6.9-SNAPSHOT/languagetool-server.jar": b"jar"},
    )
    local_language_tool = LocalLanguageTool.from_version_name(requested_snapshot)
    monkeypatch.setattr(
        language_tool_python.download_lt,
        "_confirm_java_compatibility",
        skip_java_compatibility_check,
    )
    monkeypatch.setattr(
        language_tool_python.download_lt,
        "get_language_tool_download_path",
        lambda: tmp_path,
    )

    with patch(
        "language_tool_python.download_lt.requests.get",
        return_value=MockDownloadResponse(payload),
    ):
        local_language_tool.download()

        expected_dir = tmp_path / f"LanguageTool-{requested_snapshot}"
        assert (expected_dir / "languagetool-server.jar").read_bytes() == b"jar"
        assert not (tmp_path / "LanguageTool-6.9-SNAPSHOT").exists()
        assert local_language_tool.get_directory_path() == expected_dir

        with patch("language_tool_python.download_lt.requests.get") as get_mock:
            local_language_tool.download()

        get_mock.assert_not_called()


def test_http_get_404_raises_path_error() -> None:
    """_do_download raises PathError when the server returns 404 Not Found."""
    mock_response = MockDownloadResponse(b"", status_code=404)
    mock_response.headers = {}
    out_file = io.BytesIO()
    local_language_tool = LocalLanguageTool.from_version_name()
    with (
        patch(
            "language_tool_python.download_lt.requests.get",
            return_value=mock_response,
        ),
        pytest.raises(PathError, match="Could not find at URL"),
    ):
        local_language_tool._get_remote_zip(out_file)


def test_http_get_timeout_raises_timeout_error() -> None:
    """_do_download raises TimeoutError when the HTTP request times out."""
    out_file = io.BytesIO()
    local_language_tool = LocalLanguageTool.from_version_name()
    with (
        patch(
            "language_tool_python.download_lt.requests.get",
            side_effect=requests.exceptions.Timeout("timed out"),
        ),
        pytest.raises(TimeoutError, match="timed out"),
    ):
        local_language_tool._get_remote_zip(out_file)


def test_snapshot_download_raises_when_archive_has_multiple_root_dirs(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """download() raises PathError when the snapshot archive has multiple root dirs."""
    payload = make_zip_payload(
        {
            "Dir1/file.txt": b"content1",
            "Dir2/file.txt": b"content2",
        }
    )
    local_language_tool = LocalLanguageTool.from_version_name("20240102")
    monkeypatch.setattr(
        language_tool_python.download_lt,
        "_confirm_java_compatibility",
        skip_java_compatibility_check,
    )
    monkeypatch.setattr(
        language_tool_python.download_lt,
        "get_language_tool_download_path",
        lambda: tmp_path,
    )
    with (
        patch(
            "language_tool_python.download_lt.requests.get",
            return_value=MockDownloadResponse(payload),
        ),
        pytest.raises(PathError, match="Expected snapshot archive"),
    ):
        local_language_tool.download()


def test_latest_snapshot_download_renames_archive_root_to_current_date(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Test that latest snapshots are installed under the current date name."""
    current_snapshot_date = "20240514"
    payload = make_zip_payload(
        {"LanguageTool-6.9-SNAPSHOT/languagetool-server.jar": b"jar"},
    )
    monkeypatch.setattr(
        FixedDatetime, "current_datetime", datetime(2024, 5, 14, tzinfo=timezone.utc)
    )
    monkeypatch.setattr(language_tool_python.download_lt, "datetime", FixedDatetime)
    local_language_tool = LocalLanguageTool.from_version_name("latest")
    monkeypatch.setattr(
        language_tool_python.download_lt,
        "_confirm_java_compatibility",
        skip_java_compatibility_check,
    )
    monkeypatch.setattr(
        language_tool_python.download_lt,
        "get_language_tool_download_path",
        lambda: tmp_path,
    )

    with patch(
        "language_tool_python.download_lt.requests.get",
        return_value=MockDownloadResponse(payload),
    ):
        local_language_tool.download()

        expected_dir = tmp_path / f"LanguageTool-{current_snapshot_date}"
        assert (expected_dir / "languagetool-server.jar").read_bytes() == b"jar"
        assert not (tmp_path / "LanguageTool-6.9-SNAPSHOT").exists()
        assert local_language_tool.get_directory_path() == expected_dir

        with patch("language_tool_python.download_lt.requests.get") as get_mock:
            local_language_tool.download()

        get_mock.assert_not_called()
