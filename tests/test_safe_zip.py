"""Tests for safe ZIP extraction."""

import contextlib
import hashlib
import importlib
import io
import os
import shutil
import stat
import uuid
import zipfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest

from language_tool_python import safe_zip, utils
from language_tool_python.exceptions import PathError
from language_tool_python.safe_zip import SafeZipExtractor, SafeZipLimits


def make_zip_payload(files: dict[str, bytes]) -> bytes:
    """
    Create an in-memory ZIP payload for safe extraction tests.
    """
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zip_file:
        for filename, payload in files.items():
            zip_file.writestr(filename, payload)
    return buffer.getvalue()


def make_deflated_zip_payload(files: dict[str, bytes]) -> bytes:
    """
    Create an in-memory ZIP payload using DEFLATE compression.
    """
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as zip_file:
        for filename, payload in files.items():
            zip_file.writestr(filename, payload)
    return buffer.getvalue()


def make_zip_payload_from_info(member: zipfile.ZipInfo, payload: bytes) -> bytes:
    """
    Create an in-memory ZIP payload with explicit member metadata.
    """
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
    """
    Create a symlink, or skip the test if the platform disallows it.
    """
    try:
        os.symlink(target, link, target_is_directory=target_is_directory)
    except (NotImplementedError, OSError) as error:
        pytest.skip(f"Cannot create symlink for this test: {error}")


@contextmanager
def workspace_temp_dir() -> Iterator[Path]:
    """
    Create a temporary directory inside the repository workspace.
    """
    root = Path.cwd() / ".test_safe_zip_tmp"
    path = root / uuid.uuid4().hex
    path.mkdir(parents=True)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)
        with contextlib.suppress(OSError):
            root.rmdir()


def test_safe_extract_allows_regular_zip() -> None:
    """
    Test that a regular ZIP is extracted by the safe extractor.
    """
    payload = make_zip_payload(
        {
            "LanguageTool-6.9-SNAPSHOT/": b"",
            "LanguageTool-6.9-SNAPSHOT/languagetool-server.jar": b"jar",
        }
    )

    with (
        workspace_temp_dir() as temp_dir,
        zipfile.ZipFile(io.BytesIO(payload)) as zip_file,
    ):
        SafeZipExtractor().extractall(zip_file, temp_dir)
        assert (
            temp_dir / "LanguageTool-6.9-SNAPSHOT" / "languagetool-server.jar"
        ).read_bytes() == b"jar"


def test_safe_zip_limits_use_env_overrides(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Test that safe ZIP limits can be configured from the environment.
    """
    try:
        with monkeypatch.context() as env:
            env.setenv(safe_zip.LTP_SAFE_ZIP_MAX_ARCHIVE_BYTES_ENV_VAR, "11")
            env.setenv(safe_zip.LTP_SAFE_ZIP_MAX_EXTRACTED_BYTES_ENV_VAR, "22")
            env.setenv(safe_zip.LTP_SAFE_ZIP_MAX_MEMBERS_ENV_VAR, "33")
            env.setenv(
                safe_zip.LTP_SAFE_ZIP_MAX_MEMBER_EXTRACTED_BYTES_ENV_VAR,
                "44",
            )
            env.setenv(
                safe_zip.LTP_SAFE_ZIP_MAX_MEMBER_COMPRESSION_RATIO_ENV_VAR,
                "55.5",
            )
            env.setenv(
                safe_zip.LTP_SAFE_ZIP_MAX_TOTAL_COMPRESSION_RATIO_ENV_VAR,
                "66.5",
            )

            reloaded_safe_zip = importlib.reload(safe_zip)
            limits = reloaded_safe_zip.SafeZipLimits()

            assert limits.max_archive_bytes == 11
            assert limits.max_extracted_bytes == 22
            assert limits.max_members == 33
            assert limits.max_member_extracted_bytes == 44
            assert limits.max_member_compression_ratio == 55.5
            assert limits.max_total_compression_ratio == 66.5
    finally:
        importlib.reload(safe_zip)


@pytest.mark.parametrize("configured", ["nan", "inf"])  # type: ignore[untyped-decorator]
def test_safe_zip_float_env_rejects_non_finite_values(
    monkeypatch: pytest.MonkeyPatch,
    configured: str,
) -> None:
    """
    Test that non-finite ratio limits are rejected.
    """
    env_var = "LTP_TEST_SAFE_ZIP_FLOAT"
    monkeypatch.setenv(env_var, configured)

    with pytest.raises(PathError, match="Invalid float configured"):
        utils.get_env_float(env_var, 1.0)


@pytest.mark.parametrize(  # type: ignore[untyped-decorator]
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
) -> None:
    """
    Test that unsafe ZIP member names are rejected.
    """
    payload = make_zip_payload({filename: b"nope"})

    with (
        workspace_temp_dir() as temp_dir,
        zipfile.ZipFile(io.BytesIO(payload)) as zip_file,
        pytest.raises(PathError, match="Unsafe ZIP member"),
    ):
        SafeZipExtractor().extractall(zip_file, temp_dir)


def test_safe_extract_rejects_duplicate_member_paths() -> None:
    """
    Test that duplicate ZIP member paths are rejected before extraction.
    """
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zip_file:
        zip_file.writestr("LanguageTool/file.txt", b"one")
        zip_file.writestr("LanguageTool/FILE.txt", b"two")
    buffer.seek(0)

    with (
        workspace_temp_dir() as temp_dir,
        zipfile.ZipFile(buffer) as zip_file,
        pytest.raises(PathError, match="duplicate ZIP member path"),
    ):
        SafeZipExtractor().extractall(zip_file, temp_dir)


def test_safe_extract_rejects_file_directory_conflict() -> None:
    """
    Test that archives cannot contain both a file and children below that file path.
    """
    payload = make_zip_payload(
        {
            "LanguageTool/path": b"file",
            "LanguageTool/path/child.txt": b"child",
        }
    )

    with (
        workspace_temp_dir() as temp_dir,
        zipfile.ZipFile(io.BytesIO(payload)) as zip_file,
        pytest.raises(PathError, match="below file path|file over directory path"),
    ):
        SafeZipExtractor().extractall(zip_file, temp_dir)


def test_safe_extract_rejects_file_directory_conflict_in_reverse_order() -> None:
    """
    Test that archives cannot replace a directory path with a file path.
    """
    payload = make_zip_payload(
        {
            "LanguageTool/path/child.txt": b"child",
            "LanguageTool/path": b"file",
        }
    )

    with (
        workspace_temp_dir() as temp_dir,
        zipfile.ZipFile(io.BytesIO(payload)) as zip_file,
        pytest.raises(PathError, match="below file path|file over directory path"),
    ):
        SafeZipExtractor().extractall(zip_file, temp_dir)


def test_safe_extract_rejects_zip_symlink() -> None:
    """
    Test that ZIP symlink entries are rejected.
    """
    member = zipfile.ZipInfo("LanguageTool/link")
    member.create_system = 3
    member.external_attr = (stat.S_IFLNK | 0o777) << 16
    payload = make_zip_payload_from_info(member, b"target")

    with (
        workspace_temp_dir() as temp_dir,
        zipfile.ZipFile(io.BytesIO(payload)) as zip_file,
        pytest.raises(PathError, match="symlink"),
    ):
        SafeZipExtractor().extractall(zip_file, temp_dir)


def test_safe_extract_rejects_symlinked_destination() -> None:
    """
    Test that the final destination itself cannot be a symlink.
    """
    payload = make_zip_payload({"LanguageTool/file.txt": b"jar"})

    with (
        workspace_temp_dir() as temp_dir,
        zipfile.ZipFile(io.BytesIO(payload)) as zip_file,
    ):
        real_destination = temp_dir / "real-destination"
        real_destination.mkdir()
        destination_link = temp_dir / "destination-link"
        make_symlink_or_skip(
            real_destination,
            destination_link,
            target_is_directory=True,
        )

        with pytest.raises(PathError, match="symlinked destination"):
            SafeZipExtractor().extractall(
                zip_file,
                destination_link,
                work_dir=temp_dir / "work",
            )

        assert not (real_destination / "LanguageTool").exists()


def test_safe_extract_rejects_existing_symlink_in_destination() -> None:
    """
    Test that an existing destination symlink cannot redirect extracted content.
    """
    payload = make_zip_payload({"LanguageTool/file.txt": b"jar"})

    with (
        workspace_temp_dir() as temp_dir,
        zipfile.ZipFile(io.BytesIO(payload)) as zip_file,
    ):
        destination = temp_dir / "destination"
        destination.mkdir()
        outside = temp_dir / "outside"
        outside.mkdir()
        make_symlink_or_skip(
            outside,
            destination / "LanguageTool",
            target_is_directory=True,
        )

        with pytest.raises(
            PathError,
            match="Unsafe extracted ZIP destination path|overwrite existing path",
        ):
            SafeZipExtractor().extractall(
                zip_file,
                destination,
                work_dir=temp_dir / "work",
            )

        assert not (outside / "file.txt").exists()


def test_safe_extract_rejects_symlinked_work_dir() -> None:
    """
    Test that the private extraction work directory cannot be a symlink.
    """
    payload = make_zip_payload({"LanguageTool/file.txt": b"jar"})

    with (
        workspace_temp_dir() as temp_dir,
        zipfile.ZipFile(io.BytesIO(payload)) as zip_file,
    ):
        work_target = temp_dir / "work-target"
        work_target.mkdir()
        work_link = temp_dir / "work-link"
        make_symlink_or_skip(work_target, work_link, target_is_directory=True)

        with pytest.raises(PathError, match="private extraction directory"):
            SafeZipExtractor().extractall(
                zip_file,
                temp_dir / "destination",
                work_dir=work_link,
            )


def test_safe_extract_rejects_special_zip_member_type() -> None:
    """
    Test that non-file, non-directory ZIP entries are rejected.
    """
    member = zipfile.ZipInfo("LanguageTool/fifo")
    member.create_system = 3
    member.external_attr = (stat.S_IFIFO | 0o644) << 16
    payload = make_zip_payload_from_info(member, b"")

    with (
        workspace_temp_dir() as temp_dir,
        zipfile.ZipFile(io.BytesIO(payload)) as zip_file,
        pytest.raises(PathError, match="unsupported ZIP member type"),
    ):
        SafeZipExtractor().extractall(zip_file, temp_dir)


def test_safe_extract_allows_multiple_safe_roots() -> None:
    """
    Test that safe extraction does not require a LanguageTool-specific root.
    """
    payload = make_zip_payload(
        {
            "first/file.txt": b"one",
            "second/file.txt": b"two",
        }
    )

    with (
        workspace_temp_dir() as temp_dir,
        zipfile.ZipFile(io.BytesIO(payload)) as zip_file,
    ):
        destination = temp_dir / "destination"
        work_dir = temp_dir / "work"
        SafeZipExtractor().extractall(zip_file, destination, work_dir=work_dir)

        assert (destination / "first" / "file.txt").read_bytes() == b"one"
        assert (destination / "second" / "file.txt").read_bytes() == b"two"


def test_safe_extract_rejects_existing_destination_path() -> None:
    """
    Test that extraction never overwrites an existing final destination path.
    """
    payload = make_zip_payload({"file.txt": b"new"})

    with (
        workspace_temp_dir() as temp_dir,
        zipfile.ZipFile(io.BytesIO(payload)) as zip_file,
    ):
        destination = temp_dir / "destination"
        destination.mkdir()
        existing_file = destination / "file.txt"
        existing_file.write_bytes(b"old")

        with pytest.raises(PathError, match="overwrite existing path"):
            SafeZipExtractor().extractall(
                zip_file,
                destination,
                work_dir=temp_dir / "work",
            )

        assert existing_file.read_bytes() == b"old"


def test_safe_extract_rejects_too_many_members() -> None:
    """
    Test that ZIP archives with too many entries are rejected.
    """
    payload = make_zip_payload(
        {
            "LanguageTool/one.txt": b"one",
            "LanguageTool/two.txt": b"two",
        }
    )
    extractor = SafeZipExtractor(SafeZipLimits(max_members=1))

    with (
        workspace_temp_dir() as temp_dir,
        zipfile.ZipFile(io.BytesIO(payload)) as zip_file,
        pytest.raises(PathError, match="Maximum allowed member count"),
    ):
        extractor.extractall(zip_file, temp_dir)


def test_safe_extract_rejects_too_much_uncompressed_data() -> None:
    """
    Test that ZIP archives with too much uncompressed data are rejected.
    """
    payload = make_zip_payload({"LanguageTool/file.txt": b"four"})
    extractor = SafeZipExtractor(SafeZipLimits(max_extracted_bytes=3))

    with (
        workspace_temp_dir() as temp_dir,
        zipfile.ZipFile(io.BytesIO(payload)) as zip_file,
        pytest.raises(PathError, match="Maximum allowed extracted size"),
    ):
        extractor.extractall(zip_file, temp_dir)


def test_safe_extract_rejects_oversized_member_during_copy() -> None:
    """
    Test that per-member extracted size limits are enforced while copying.
    """
    payload = make_zip_payload({"LanguageTool/file.txt": b"four"})
    extractor = SafeZipExtractor(
        SafeZipLimits(
            max_extracted_bytes=100,
            max_member_extracted_bytes=3,
        )
    )

    with (
        workspace_temp_dir() as temp_dir,
        zipfile.ZipFile(io.BytesIO(payload)) as zip_file,
        pytest.raises(PathError, match="ZIP member larger"),
    ):
        extractor.extractall(zip_file, temp_dir)


def test_safe_extract_rejects_too_much_compressed_data() -> None:
    """
    Test that local ZIP extraction also applies the compressed-size limit.
    """
    payload = make_zip_payload({"LanguageTool/file.txt": b"data"})
    extractor = SafeZipExtractor(SafeZipLimits(max_archive_bytes=1))

    with (
        workspace_temp_dir() as temp_dir,
        zipfile.ZipFile(io.BytesIO(payload)) as zip_file,
        pytest.raises(PathError, match="compressed member bytes"),
    ):
        extractor.extractall(zip_file, temp_dir)


def test_safe_extract_rejects_suspicious_member_compression_ratio() -> None:
    """
    Test that a single member with an abusive compression ratio is rejected.
    """
    payload = make_deflated_zip_payload({"LanguageTool/file.txt": b"A" * 4096})
    extractor = SafeZipExtractor(
        SafeZipLimits(
            max_member_compression_ratio=2.0,
            max_total_compression_ratio=10_000.0,
        )
    )

    with (
        workspace_temp_dir() as temp_dir,
        zipfile.ZipFile(io.BytesIO(payload)) as zip_file,
        pytest.raises(PathError, match="suspicious compression ratio"),
    ):
        extractor.extractall(zip_file, temp_dir)


def test_safe_extract_rejects_suspicious_total_compression_ratio() -> None:
    """
    Test that an archive with an abusive total compression ratio is rejected.
    """
    payload = make_deflated_zip_payload({"LanguageTool/file.txt": b"A" * 4096})
    extractor = SafeZipExtractor(
        SafeZipLimits(
            max_member_compression_ratio=10_000.0,
            max_total_compression_ratio=2.0,
        )
    )

    with (
        workspace_temp_dir() as temp_dir,
        zipfile.ZipFile(io.BytesIO(payload)) as zip_file,
        pytest.raises(PathError, match="suspicious total compression ratio"),
    ):
        extractor.extractall(zip_file, temp_dir)


def test_safe_extract_checks_total_compression_ratio_after_all_members() -> None:
    """
    Test that total ratio checks are based on the final archive ratio.
    """
    already_compressed = b"".join(
        hashlib.sha256(index.to_bytes(4, "big")).digest() for index in range(2048)
    )
    payload = make_deflated_zip_payload(
        {
            "LanguageTool/compressible.txt": b"A" * 4096,
            "LanguageTool/already-compressed.bin": already_compressed,
        }
    )
    extractor = SafeZipExtractor(
        SafeZipLimits(
            max_member_compression_ratio=1_000.0,
            max_total_compression_ratio=5.0,
        )
    )

    with (
        workspace_temp_dir() as temp_dir,
        zipfile.ZipFile(io.BytesIO(payload)) as zip_file,
    ):
        extractor.extractall(zip_file, temp_dir)

        assert (
            temp_dir / "LanguageTool" / "compressible.txt"
        ).read_bytes() == b"A" * 4096
        assert (
            temp_dir / "LanguageTool" / "already-compressed.bin"
        ).read_bytes() == already_compressed
