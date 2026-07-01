"""Unit tests for safe ZIP extraction."""

import hashlib
import io
import stat
import unittest.mock
import zipfile
from pathlib import Path

import pytest

from language_tool_python._internals import safe_zip, utils
from language_tool_python._internals.safe_zip import SafeZipExtractor, SafeZipLimits
from language_tool_python.exceptions import PathError

EXPECTED_MAX_ARCHIVE_BYTES = 11
EXPECTED_MAX_EXTRACTED_BYTES = 22
EXPECTED_MAX_MEMBERS = 33
EXPECTED_MAX_MEMBER_EXTRACTED_BYTES = 44
EXPECTED_MAX_MEMBER_COMPRESSION_RATIO = 55.5
EXPECTED_MAX_TOTAL_COMPRESSION_RATIO = 66.5


def make_zip_payload(files: dict[str, bytes]) -> bytes:
    """Create an in-memory ZIP payload for safe extraction tests."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zip_file:
        for filename, payload in files.items():
            zip_file.writestr(filename, payload)
    return buffer.getvalue()


def make_deflated_zip_payload(files: dict[str, bytes]) -> bytes:
    """Create an in-memory ZIP payload using DEFLATE compression."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as zip_file:
        for filename, payload in files.items():
            zip_file.writestr(filename, payload)
    return buffer.getvalue()


def make_zip_payload_from_info(member: zipfile.ZipInfo, payload: bytes) -> bytes:
    """Create an in-memory ZIP payload with explicit member metadata."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zip_file:
        zip_file.writestr(member, payload)
    return buffer.getvalue()


def make_symlink_or_skip(
    target: Path,
    link: Path,
    *,
    target_is_directory: bool = False,
) -> None:
    """Create a symlink, or skip the test if the platform disallows it."""
    try:
        link.symlink_to(target, target_is_directory=target_is_directory)
    except (NotImplementedError, OSError) as error:
        pytest.skip(f"Cannot create symlink for this test: {error}")


def test_safe_extract_allows_regular_zip(tmp_path: Path) -> None:
    """Test that a regular ZIP is extracted by the safe extractor."""
    payload = make_zip_payload(
        {
            "LanguageTool-6.9-SNAPSHOT/": b"",
            "LanguageTool-6.9-SNAPSHOT/languagetool-server.jar": b"jar",
        },
    )

    with zipfile.ZipFile(io.BytesIO(payload)) as zip_file:
        SafeZipExtractor().extractall(zip_file, tmp_path)
        assert (
            tmp_path / "LanguageTool-6.9-SNAPSHOT" / "languagetool-server.jar"
        ).read_bytes() == b"jar"


def test_safe_zip_limits_defaults_wired_to_module_constants() -> None:
    """Test that SafeZipLimits() defaults are wired to the module DEFAULT_* constants.

    The module-level ``DEFAULT_*`` constants are computed once at import time via
    :func:`get_env_int`/:func:`get_env_float` (whose environment-variable-override
    branch is covered directly by ``TestGetEnvInt``/``TestGetEnvFloat`` in
    ``test_internals_utils.py``, and by
    ``test_safe_zip_float_env_rejects_non_finite_values`` below). This test instead
    verifies the downstream wiring: that each ``SafeZipLimits`` field default is the
    corresponding module constant, without needing to reload the module (which would
    leak state across tests and require careful cleanup).
    """
    limits = SafeZipLimits()
    assert limits.max_archive_bytes == safe_zip.DEFAULT_MAX_ARCHIVE_BYTES
    assert limits.max_extracted_bytes == safe_zip.DEFAULT_MAX_EXTRACTED_BYTES
    assert limits.max_members == safe_zip.DEFAULT_MAX_MEMBERS
    assert (
        limits.max_member_extracted_bytes == safe_zip.DEFAULT_MAX_MEMBER_EXTRACTED_BYTES
    )
    assert (
        limits.max_member_compression_ratio
        == safe_zip.DEFAULT_MAX_MEMBER_COMPRESSION_RATIO
    )
    assert (
        limits.max_total_compression_ratio
        == safe_zip.DEFAULT_MAX_TOTAL_COMPRESSION_RATIO
    )


@pytest.mark.parametrize("configured", ["nan", "inf"])
def test_safe_zip_float_env_rejects_non_finite_values(
    monkeypatch: pytest.MonkeyPatch,
    configured: str,
) -> None:
    """Test that non-finite ratio limits are rejected."""
    env_var = "LTP_TEST_SAFE_ZIP_FLOAT"
    monkeypatch.setenv(env_var, configured)

    with pytest.raises(PathError, match="Invalid float configured"):
        utils.get_env_float(env_var, 1.0)


@pytest.mark.parametrize(
    "filename",
    [
        "../outside.txt",
        "LanguageTool/../../outside.txt",
        "/absolute.txt",
        "C:/absolute.txt",
        "D:\\somewhere\\file",
        "\\\\server\\share\\outside.txt",
        "..\\outside.txt",
        "LanguageTool\\..\\outside.txt",
        "....\\evil",
        "foo....\\evil",
        "LanguageTool//file.txt",
        "LanguageTool/./file.txt",
        "LanguageTool/file.txt:stream",
        "LanguageTool/CON",
        "LanguageTool/NUL.txt",
        "LanguageTool/com1",
        "LanguageTool/LPT1.log",
        "LanguageTool/AUX/report.txt",
        "LanguageTool/trailing-space ",
        "LanguageTool/trailing-dot.",
    ],
)
def test_safe_extract_rejects_unsafe_member_names(
    filename: str,
    tmp_path: Path,
) -> None:
    """Test that unsafe ZIP member names are rejected."""
    payload = make_zip_payload({filename: b"nope"})

    with (
        zipfile.ZipFile(io.BytesIO(payload)) as zip_file,
        pytest.raises(PathError, match="Unsafe ZIP member"),
    ):
        SafeZipExtractor().extractall(zip_file, tmp_path)


def test_safe_extract_rejects_duplicate_member_paths(tmp_path: Path) -> None:
    """Test that duplicate ZIP member paths are rejected before extraction."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zip_file:
        zip_file.writestr("LanguageTool/file.txt", b"one")
        zip_file.writestr("LanguageTool/FILE.txt", b"two")
    buffer.seek(0)

    with (
        zipfile.ZipFile(buffer) as zip_file,
        pytest.raises(PathError, match="duplicate ZIP member path"),
    ):
        SafeZipExtractor().extractall(zip_file, tmp_path)


def test_safe_extract_rejects_file_directory_conflict(tmp_path: Path) -> None:
    """Test that archives reject file-and-child path conflicts."""
    payload = make_zip_payload(
        {
            "LanguageTool/path": b"file",
            "LanguageTool/path/child.txt": b"child",
        },
    )

    with (
        zipfile.ZipFile(io.BytesIO(payload)) as zip_file,
        pytest.raises(PathError, match=r"below file path|file over directory path"),
    ):
        SafeZipExtractor().extractall(zip_file, tmp_path)


def test_safe_extract_rejects_file_directory_conflict_in_reverse_order(
    tmp_path: Path,
) -> None:
    """Test that archives cannot replace a directory path with a file path."""
    payload = make_zip_payload(
        {
            "LanguageTool/path/child.txt": b"child",
            "LanguageTool/path": b"file",
        },
    )

    with (
        zipfile.ZipFile(io.BytesIO(payload)) as zip_file,
        pytest.raises(PathError, match=r"below file path|file over directory path"),
    ):
        SafeZipExtractor().extractall(zip_file, tmp_path)


def test_safe_extract_rejects_zip_symlink(tmp_path: Path) -> None:
    """Test that ZIP symlink entries are rejected."""
    member = zipfile.ZipInfo("LanguageTool/link")
    member.create_system = 3
    member.external_attr = (stat.S_IFLNK | 0o777) << 16
    payload = make_zip_payload_from_info(member, b"target")

    with (
        zipfile.ZipFile(io.BytesIO(payload)) as zip_file,
        pytest.raises(PathError, match="symlink"),
    ):
        SafeZipExtractor().extractall(zip_file, tmp_path)


def test_safe_extract_rejects_symlinked_destination(tmp_path: Path) -> None:
    """Test that the final destination itself cannot be a symlink."""
    payload = make_zip_payload({"LanguageTool/file.txt": b"jar"})

    with zipfile.ZipFile(io.BytesIO(payload)) as zip_file:
        real_destination = tmp_path / "real-destination"
        real_destination.mkdir()
        destination_link = tmp_path / "destination-link"
        make_symlink_or_skip(
            real_destination,
            destination_link,
            target_is_directory=True,
        )

        with pytest.raises(PathError, match="symlinked destination"):
            SafeZipExtractor().extractall(
                zip_file,
                destination_link,
                work_dir=tmp_path / "work",
            )

        assert not (real_destination / "LanguageTool").exists()


def test_safe_extract_rejects_existing_symlink_in_destination(tmp_path: Path) -> None:
    """Test that an existing destination symlink cannot redirect extracted content."""
    payload = make_zip_payload({"LanguageTool/file.txt": b"jar"})

    with zipfile.ZipFile(io.BytesIO(payload)) as zip_file:
        destination = tmp_path / "destination"
        destination.mkdir()
        outside = tmp_path / "outside"
        outside.mkdir()
        make_symlink_or_skip(
            outside,
            destination / "LanguageTool",
            target_is_directory=True,
        )

        with pytest.raises(
            PathError,
            match=r"Unsafe extracted ZIP destination path|overwrite existing path",
        ):
            SafeZipExtractor().extractall(
                zip_file,
                destination,
                work_dir=tmp_path / "work",
            )

        assert not (outside / "file.txt").exists()


def test_safe_extract_rejects_symlinked_work_dir(tmp_path: Path) -> None:
    """Test that the private extraction work directory cannot be a symlink."""
    payload = make_zip_payload({"LanguageTool/file.txt": b"jar"})

    with zipfile.ZipFile(io.BytesIO(payload)) as zip_file:
        work_target = tmp_path / "work-target"
        work_target.mkdir()
        work_link = tmp_path / "work-link"
        make_symlink_or_skip(work_target, work_link, target_is_directory=True)

        with pytest.raises(PathError, match="private extraction directory"):
            SafeZipExtractor().extractall(
                zip_file,
                tmp_path / "destination",
                work_dir=work_link,
            )


def test_safe_extract_rejects_special_zip_member_type(tmp_path: Path) -> None:
    """Test that non-file, non-directory ZIP entries are rejected."""
    member = zipfile.ZipInfo("LanguageTool/fifo")
    member.create_system = 3
    member.external_attr = (stat.S_IFIFO | 0o644) << 16
    payload = make_zip_payload_from_info(member, b"")

    with (
        zipfile.ZipFile(io.BytesIO(payload)) as zip_file,
        pytest.raises(PathError, match="unsupported ZIP member type"),
    ):
        SafeZipExtractor().extractall(zip_file, tmp_path)


def test_safe_extract_allows_multiple_safe_roots(tmp_path: Path) -> None:
    """Test that safe extraction does not require a LanguageTool-specific root."""
    payload = make_zip_payload(
        {
            "first/file.txt": b"one",
            "second/file.txt": b"two",
        },
    )

    with zipfile.ZipFile(io.BytesIO(payload)) as zip_file:
        destination = tmp_path / "destination"
        work_dir = tmp_path / "work"
        SafeZipExtractor().extractall(zip_file, destination, work_dir=work_dir)

        assert (destination / "first" / "file.txt").read_bytes() == b"one"
        assert (destination / "second" / "file.txt").read_bytes() == b"two"


def test_safe_extract_rejects_existing_destination_path(tmp_path: Path) -> None:
    """Test that extraction never overwrites an existing final destination path."""
    payload = make_zip_payload({"file.txt": b"new"})

    with zipfile.ZipFile(io.BytesIO(payload)) as zip_file:
        destination = tmp_path / "destination"
        destination.mkdir()
        existing_file = destination / "file.txt"
        existing_file.write_bytes(b"old")

        with pytest.raises(PathError, match="overwrite existing path"):
            SafeZipExtractor().extractall(
                zip_file,
                destination,
                work_dir=tmp_path / "work",
            )

        assert existing_file.read_bytes() == b"old"


def test_safe_extract_rejects_too_many_members(tmp_path: Path) -> None:
    """Test that ZIP archives with too many entries are rejected."""
    payload = make_zip_payload(
        {
            "LanguageTool/one.txt": b"one",
            "LanguageTool/two.txt": b"two",
        },
    )
    extractor = SafeZipExtractor(SafeZipLimits(max_members=1))

    with (
        zipfile.ZipFile(io.BytesIO(payload)) as zip_file,
        pytest.raises(PathError, match="Maximum allowed member count"),
    ):
        extractor.extractall(zip_file, tmp_path)


def test_safe_extract_rejects_too_much_uncompressed_data(tmp_path: Path) -> None:
    """Test that ZIP archives with too much uncompressed data are rejected."""
    payload = make_zip_payload({"LanguageTool/file.txt": b"four"})
    extractor = SafeZipExtractor(SafeZipLimits(max_extracted_bytes=3))

    with (
        zipfile.ZipFile(io.BytesIO(payload)) as zip_file,
        pytest.raises(PathError, match="Maximum allowed extracted size"),
    ):
        extractor.extractall(zip_file, tmp_path)


def test_safe_extract_rejects_oversized_member_during_copy(tmp_path: Path) -> None:
    """Test that per-member extracted size limits are enforced while copying."""
    payload = make_zip_payload({"LanguageTool/file.txt": b"four"})
    extractor = SafeZipExtractor(
        SafeZipLimits(
            max_extracted_bytes=100,
            max_member_extracted_bytes=3,
        ),
    )

    with (
        zipfile.ZipFile(io.BytesIO(payload)) as zip_file,
        pytest.raises(PathError, match="ZIP member larger"),
    ):
        extractor.extractall(zip_file, tmp_path)


def test_safe_extract_rejects_too_much_compressed_data(tmp_path: Path) -> None:
    """Test that local ZIP extraction also applies the compressed-size limit."""
    payload = make_zip_payload({"LanguageTool/file.txt": b"data"})
    extractor = SafeZipExtractor(SafeZipLimits(max_archive_bytes=1))

    with (
        zipfile.ZipFile(io.BytesIO(payload)) as zip_file,
        pytest.raises(PathError, match="compressed member bytes"),
    ):
        extractor.extractall(zip_file, tmp_path)


def test_safe_extract_rejects_suspicious_member_compression_ratio(
    tmp_path: Path,
) -> None:
    """Test that a single member with an abusive compression ratio is rejected."""
    payload = make_deflated_zip_payload({"LanguageTool/file.txt": b"A" * 4096})
    extractor = SafeZipExtractor(
        SafeZipLimits(
            max_member_compression_ratio=2.0,
            max_total_compression_ratio=10_000.0,
        ),
    )

    with (
        zipfile.ZipFile(io.BytesIO(payload)) as zip_file,
        pytest.raises(PathError, match="suspicious compression ratio"),
    ):
        extractor.extractall(zip_file, tmp_path)


def test_safe_extract_rejects_suspicious_total_compression_ratio(
    tmp_path: Path,
) -> None:
    """Test that an archive with an abusive total compression ratio is rejected."""
    payload = make_deflated_zip_payload({"LanguageTool/file.txt": b"A" * 4096})
    extractor = SafeZipExtractor(
        SafeZipLimits(
            max_member_compression_ratio=10_000.0,
            max_total_compression_ratio=2.0,
        ),
    )

    with (
        zipfile.ZipFile(io.BytesIO(payload)) as zip_file,
        pytest.raises(PathError, match="suspicious total compression ratio"),
    ):
        extractor.extractall(zip_file, tmp_path)


def test_safe_extract_checks_total_compression_ratio_after_all_members(
    tmp_path: Path,
) -> None:
    """Test that total ratio checks are based on the final archive ratio."""
    already_compressed = b"".join(
        hashlib.sha256(index.to_bytes(4, "big")).digest() for index in range(2048)
    )
    payload = make_deflated_zip_payload(
        {
            "LanguageTool/compressible.txt": b"A" * 4096,
            "LanguageTool/already-compressed.bin": already_compressed,
        },
    )
    extractor = SafeZipExtractor(
        SafeZipLimits(
            max_member_compression_ratio=1_000.0,
            max_total_compression_ratio=5.0,
        ),
    )

    with zipfile.ZipFile(io.BytesIO(payload)) as zip_file:
        extractor.extractall(zip_file, tmp_path)

        assert (
            tmp_path / "LanguageTool" / "compressible.txt"
        ).read_bytes() == b"A" * 4096
        assert (
            tmp_path / "LanguageTool" / "already-compressed.bin"
        ).read_bytes() == already_compressed


def test_normalize_member_path_empty_name_raises() -> None:
    """_normalize_member_path rejects an empty filename."""
    with pytest.raises(PathError, match="Unsafe ZIP member name"):
        SafeZipExtractor()._normalize_member_path("")


def test_normalize_member_path_control_char_raises() -> None:
    """_normalize_member_path rejects a filename containing a control character."""
    with pytest.raises(PathError, match="Unsafe ZIP member name"):
        SafeZipExtractor()._normalize_member_path("foo\x01bar")


def test_validate_member_type_explicit_regular_file_passes() -> None:
    """_validate_member_type accepts a ZipInfo with an explicit S_IFREG mode."""
    member = zipfile.ZipInfo("LanguageTool/file.txt")
    member.external_attr = stat.S_IFREG << 16
    SafeZipExtractor()._validate_member_type(member)


def test_validate_member_compression_ratio_zero_compress_size_raises() -> None:
    """_validate_member_compression_ratio rejects a member with zero compressed size."""
    member = zipfile.ZipInfo("LanguageTool/file.txt")
    member.compress_size = 0
    member.file_size = 100
    with pytest.raises(PathError, match="zero compressed size"):
        SafeZipExtractor()._validate_member_compression_ratio(member)


def test_validate_total_compression_ratio_zero_compressed_skips() -> None:
    """_validate_total_compression_ratio returns early when total_compressed is zero."""
    SafeZipExtractor()._validate_total_compression_ratio(0, 0)


def test_validate_member_sizes_negative_compress_size_raises() -> None:
    """_validate_member_sizes rejects a member with a negative compressed size."""
    member = zipfile.ZipInfo("LanguageTool/file.txt")
    member.compress_size = -1
    member.file_size = 100
    with pytest.raises(PathError, match="Invalid ZIP member size"):
        SafeZipExtractor()._validate_member_sizes(member)


def test_validate_member_sizes_negative_file_size_raises() -> None:
    """_validate_member_sizes rejects a member with a negative uncompressed size."""
    member = zipfile.ZipInfo("LanguageTool/file.txt")
    member.compress_size = 100
    member.file_size = -1
    with pytest.raises(PathError, match="Invalid ZIP member size"):
        SafeZipExtractor()._validate_member_sizes(member)


def _open_returning_large(_m: object, _mode: str = "r") -> io.BytesIO:
    """Fake ZipFile.open that yields more bytes than any small declared file_size."""
    return io.BytesIO(b"hello world - content longer than 3 bytes")


def _open_returning_small(_m: object, _mode: str = "r") -> io.BytesIO:
    """Fake ZipFile.open that yields only 2 bytes regardless of declared size."""
    return io.BytesIO(b"hi")


def test_copy_member_raises_when_content_exceeds_declared_size(tmp_path: Path) -> None:
    """_copy_member raises when decompressed bytes exceed the declared file_size."""
    payload = make_zip_payload({"LanguageTool/file.txt": b"hello world"})
    with zipfile.ZipFile(io.BytesIO(payload)) as zf:
        member = zf.infolist()[0]
        member.file_size = 3
        with (
            unittest.mock.patch.object(zf, "open", new=_open_returning_large),
            pytest.raises(PathError, match="expanded beyond declared size"),
        ):
            SafeZipExtractor()._copy_member(zf, member, tmp_path / "file.txt")


def test_copy_member_raises_when_content_is_less_than_declared_size(
    tmp_path: Path,
) -> None:
    """_copy_member raises when fewer bytes are read than the declared file_size."""
    payload = make_zip_payload({"LanguageTool/file.txt": b"hello world"})
    with zipfile.ZipFile(io.BytesIO(payload)) as zf:
        member = zf.infolist()[0]
        member.file_size = 1000
        with (
            unittest.mock.patch.object(zf, "open", new=_open_returning_small),
            pytest.raises(PathError, match="extracted size mismatch"),
        ):
            SafeZipExtractor()._copy_member(zf, member, tmp_path / "file.txt")
