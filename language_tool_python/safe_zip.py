"""Safe ZIP extraction utilities."""

from __future__ import annotations

import contextlib
import logging
import re
import shutil
import stat
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING

from .exceptions import PathError
from .utils import get_env_float, get_env_int

if TYPE_CHECKING:
    import zipfile

logger = logging.getLogger(__name__)

CONTROL_CHARACTER_MAX = 32

LTP_SAFE_ZIP_MAX_ARCHIVE_BYTES_ENV_VAR = "LTP_SAFE_ZIP_MAX_ARCHIVE_BYTES"
LTP_SAFE_ZIP_MAX_EXTRACTED_BYTES_ENV_VAR = "LTP_SAFE_ZIP_MAX_EXTRACTED_BYTES"
LTP_SAFE_ZIP_MAX_MEMBERS_ENV_VAR = "LTP_SAFE_ZIP_MAX_MEMBERS"
LTP_SAFE_ZIP_MAX_MEMBER_EXTRACTED_BYTES_ENV_VAR = (
    "LTP_SAFE_ZIP_MAX_MEMBER_EXTRACTED_BYTES"
)
LTP_SAFE_ZIP_MAX_MEMBER_COMPRESSION_RATIO_ENV_VAR = (
    "LTP_SAFE_ZIP_MAX_MEMBER_COMPRESSION_RATIO"
)
LTP_SAFE_ZIP_MAX_TOTAL_COMPRESSION_RATIO_ENV_VAR = (
    "LTP_SAFE_ZIP_MAX_TOTAL_COMPRESSION_RATIO"
)
DEFAULT_MAX_ARCHIVE_BYTES = get_env_int(
    LTP_SAFE_ZIP_MAX_ARCHIVE_BYTES_ENV_VAR,
    512 * 1024 * 1024,
)  # 512 MiB, latest snapshot: 246.15 MiB compressed members
DEFAULT_MAX_EXTRACTED_BYTES = get_env_int(
    LTP_SAFE_ZIP_MAX_EXTRACTED_BYTES_ENV_VAR,
    768 * 1024 * 1024,
)  # 768 MiB, latest snapshot: 394.48 MiB extracted
DEFAULT_MAX_MEMBERS = get_env_int(
    LTP_SAFE_ZIP_MAX_MEMBERS_ENV_VAR,
    5_000,
)  # latest snapshot: 2,051 members
DEFAULT_COPY_CHUNK_BYTES = 1024 * 1024  # I/O chunk size
DEFAULT_MAX_MEMBER_EXTRACTED_BYTES = get_env_int(
    LTP_SAFE_ZIP_MAX_MEMBER_EXTRACTED_BYTES_ENV_VAR,
    128 * 1024 * 1024,
)  # 128 MiB, latest snapshot: 32.91 MiB largest member
DEFAULT_MAX_MEMBER_COMPRESSION_RATIO = get_env_float(
    LTP_SAFE_ZIP_MAX_MEMBER_COMPRESSION_RATIO_ENV_VAR,
    100.0,
)  # latest snapshot: 57.89 max member ratio
DEFAULT_MAX_TOTAL_COMPRESSION_RATIO = get_env_float(
    LTP_SAFE_ZIP_MAX_TOTAL_COMPRESSION_RATIO_ENV_VAR,
    10.0,
)  # latest snapshot: 1.60 total ratio
RESERVED_WINDOWS_FILENAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}


@dataclass(frozen=True)
class SafeZipLimits:
    """Limits applied while validating and extracting a ZIP archive.

    Values are expressed in bytes unless otherwise stated.
    """

    max_archive_bytes: int = DEFAULT_MAX_ARCHIVE_BYTES
    max_extracted_bytes: int = DEFAULT_MAX_EXTRACTED_BYTES
    max_members: int = DEFAULT_MAX_MEMBERS
    copy_chunk_bytes: int = DEFAULT_COPY_CHUNK_BYTES
    max_member_compression_ratio: float = DEFAULT_MAX_MEMBER_COMPRESSION_RATIO
    max_total_compression_ratio: float = DEFAULT_MAX_TOTAL_COMPRESSION_RATIO
    max_member_extracted_bytes: int = DEFAULT_MAX_MEMBER_EXTRACTED_BYTES


class SafeZipExtractor:
    """Extract ZIP archives after validating paths, member types, and size limits."""

    def __init__(self, limits: SafeZipLimits | None = None) -> None:
        """Initialize the safe extractor.

        :param limits: Optional extraction limits. Defaults to SafeZipLimits().
        :type limits: SafeZipLimits | None
        """
        self.limits = limits or SafeZipLimits()

    def extractall(
        self,
        zip_file: zipfile.ZipFile,
        destination: Path,
        work_dir: Path | None = None,
    ) -> None:
        """Safely extract all ZIP members into destination.

        Extraction first happens inside a private directory, then validated top-level
        entries are moved into the final destination.

        :param zip_file: The open ZIP archive to extract.
        :type zip_file: zipfile.ZipFile
        :param destination: Directory where ZIP contents should be placed.
        :type destination: Path
        :param work_dir: Optional parent directory for temporary extraction.
        :type work_dir: Path | None
        :raises PathError: If the archive or destination is unsafe.
        """
        destination = Path(destination)

        logger.debug(
            "Starting safe ZIP extraction to %s (work_dir=%s)",
            destination,
            work_dir,
        )

        if work_dir is None:
            destination.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(dir=destination.parent) as temp_dir:
                self._extractall_to_directory(zip_file, destination, Path(temp_dir))
        else:
            self._extractall_to_directory(zip_file, destination, work_dir)

        logger.debug("Completed safe ZIP extraction to %s", destination)

    def _normalize_member_path(self, filename: str) -> PurePosixPath:
        """Normalize and validate a ZIP member path.

        :param filename: Raw ZIP member filename.
        :type filename: str
        :return: A safe relative POSIX path.
        :rtype: PurePosixPath
        :raises PathError: If the path is absolute, traverses, or is unsafe.
        """
        if not filename or "\x00" in filename:
            err = f"Unsafe ZIP member name: {filename!r}."
            raise PathError(err)

        if any(ord(character) < CONTROL_CHARACTER_MAX for character in filename):
            err = f"Unsafe ZIP member name: {filename!r}."
            raise PathError(err)

        normalized = filename.replace("\\", "/")

        if normalized.startswith("/") or re.match(r"^[A-Za-z]:", normalized):
            err = f"Unsafe ZIP member path: {filename!r}."
            raise PathError(err)

        parts = normalized.split("/")

        if parts[-1] == "":
            parts = parts[:-1]

        if not parts or any(part in {"", ".", ".."} for part in parts):
            err = f"Unsafe ZIP member path: {filename!r}."
            raise PathError(err)

        for part in parts:
            if ":" in part or part.endswith((" ", ".")):
                err = f"Unsafe ZIP member path: {filename!r}."
                raise PathError(err)

            windows_name = part.rstrip(" .").split(".", 1)[0].upper()

            if windows_name in RESERVED_WINDOWS_FILENAMES:
                err = f"Unsafe ZIP member path: {filename!r}."
                raise PathError(err)

        member_path = PurePosixPath(*parts)

        if member_path.is_absolute() or any(part == ".." for part in member_path.parts):
            err = f"Unsafe ZIP member path: {filename!r}."
            raise PathError(err)

        return member_path

    def _validate_member_type(self, member: zipfile.ZipInfo) -> None:
        """Reject symlinks and unsupported ZIP member types.

        :param member: ZIP member metadata.
        :type member: zipfile.ZipInfo
        :raises PathError: If the member is not a regular file or directory.
        """
        mode = member.external_attr >> 16
        file_type = stat.S_IFMT(mode)

        if stat.S_ISLNK(mode):
            err = f"Refusing to extract symlink from ZIP archive: {member.filename!r}."
            raise PathError(err)

        if file_type == 0:
            return

        if member.is_dir():
            if stat.S_ISDIR(mode):
                return
        elif stat.S_ISREG(mode):
            return

        err = f"Refusing to extract unsupported ZIP member type: {member.filename!r}."
        raise PathError(err)

    def _validate_member_compression_ratio(self, member: zipfile.ZipInfo) -> None:
        """Reject a member with a suspicious compression ratio.

        :param member: ZIP member metadata.
        :type member: zipfile.ZipInfo
        :raises PathError: If the compressed size is invalid or the ratio is too high.
        """
        if member.file_size == 0:
            return

        if member.compress_size == 0:
            err = (
                f"Refusing ZIP member with zero compressed size and non-zero "
                f"expanded size: {member.filename!r}."
            )
            raise PathError(err)

        ratio = member.file_size / member.compress_size

        if ratio > self.limits.max_member_compression_ratio:
            err = (
                f"Refusing ZIP member with suspicious compression ratio "
                f"{ratio:.1f}: {member.filename!r}. "
                f"Maximum allowed ratio is "
                f"{self.limits.max_member_compression_ratio:.1f}."
            )
            raise PathError(err)

    def _zip_target(self, destination: Path, member_path: PurePosixPath) -> Path:
        """Resolve a member target and ensure it stays inside destination.

        :param destination: Extraction root directory.
        :type destination: Path
        :param member_path: Normalized ZIP member path.
        :type member_path: PurePosixPath
        :return: The filesystem target for the member.
        :rtype: Path
        :raises PathError: If the target escapes destination.
        """
        target = destination.joinpath(*member_path.parts)
        destination_resolved = destination.resolve(strict=True)
        target_resolved = target.resolve(strict=False)

        if destination_resolved != target_resolved and (
            destination_resolved not in target_resolved.parents
        ):
            err = f"Unsafe ZIP member path: {str(member_path)!r}."
            raise PathError(err)

        return target

    def _member_path_key(self, member_path: PurePosixPath) -> str:
        """Return the normalized key used to detect path conflicts.

        :param member_path: Normalized ZIP member path.
        :type member_path: PurePosixPath
        :return: Case-folded POSIX path key.
        :rtype: str
        """
        return "/".join(part.casefold() for part in member_path.parts)

    def _validate_member_path_conflicts(
        self,
        member: zipfile.ZipInfo,
        member_path: PurePosixPath,
        seen_paths: set[str],
        seen_file_paths: set[str],
    ) -> None:
        """Reject duplicate paths and file/directory path conflicts.

        :param member: ZIP member metadata.
        :type member: zipfile.ZipInfo
        :param member_path: Normalized ZIP member path.
        :type member_path: PurePosixPath
        :param seen_paths: Case-folded paths already seen in the archive.
        :type seen_paths: set[str]
        :param seen_file_paths: Case-folded file paths already seen in the archive.
        :type seen_file_paths: set[str]
        :raises PathError: If the member conflicts with another archive path.
        """
        path_key = self._member_path_key(member_path)

        if path_key in seen_paths:
            err = f"Refusing to extract duplicate ZIP member path: {member.filename!r}."
            raise PathError(err)

        seen_paths.add(path_key)

        ancestor_keys = [
            self._member_path_key(PurePosixPath(*member_path.parts[:index]))
            for index in range(1, len(member_path.parts))
        ]
        if any(ancestor in seen_file_paths for ancestor in ancestor_keys):
            err = (
                f"Refusing to extract ZIP member below file path: {member.filename!r}."
            )
            raise PathError(err)

        if not member.is_dir():
            descendant_prefix = f"{path_key}/"
            if any(existing.startswith(descendant_prefix) for existing in seen_paths):
                err = (
                    f"Refusing to extract ZIP file over directory path: "
                    f"{member.filename!r}."
                )
                raise PathError(err)
            seen_file_paths.add(path_key)

    def _validate_member_sizes(self, member: zipfile.ZipInfo) -> None:
        """Validate a member's declared type, sizes, and compression ratio.

        :param member: ZIP member metadata.
        :type member: zipfile.ZipInfo
        :raises PathError: If the member metadata is unsafe.
        """
        self._validate_member_type(member)

        if member.compress_size < 0 or member.file_size < 0:
            err = f"Invalid ZIP member size: {member.filename!r}."
            raise PathError(err)

        self._validate_member_compression_ratio(member)

    def _validate_archive_size_totals(
        self,
        total_compressed: int,
        total_uncompressed: int,
    ) -> None:
        """Validate accumulated compressed and uncompressed archive sizes.

        :param total_compressed: Sum of compressed member sizes seen so far.
        :type total_compressed: int
        :param total_uncompressed: Sum of uncompressed member sizes seen so far.
        :type total_uncompressed: int
        :raises PathError: If an archive size limit is exceeded.
        """
        if total_compressed > self.limits.max_archive_bytes:
            err = (
                f"Refusing to extract ZIP archive with {total_compressed} "
                f"compressed member bytes. Maximum allowed size is "
                f"{self.limits.max_archive_bytes} bytes."
            )
            raise PathError(err)

        if total_uncompressed > self.limits.max_extracted_bytes:
            err = (
                f"Refusing to extract {total_uncompressed} bytes. "
                f"Maximum allowed extracted size is "
                f"{self.limits.max_extracted_bytes} bytes."
            )
            raise PathError(err)

    def _validate_total_compression_ratio(
        self,
        total_compressed: int,
        total_uncompressed: int,
    ) -> None:
        """Reject an archive with a suspicious total compression ratio.

        :param total_compressed: Sum of compressed member sizes.
        :type total_compressed: int
        :param total_uncompressed: Sum of uncompressed member sizes.
        :type total_uncompressed: int
        :raises PathError: If the total compression ratio is too high.
        """
        if total_compressed == 0:
            return

        total_ratio = total_uncompressed / total_compressed

        if total_ratio > self.limits.max_total_compression_ratio:
            err = (
                f"Refusing ZIP archive with suspicious total compression ratio "
                f"{total_ratio:.1f}. Maximum allowed ratio is "
                f"{self.limits.max_total_compression_ratio:.1f}."
            )
            raise PathError(err)

    def _validate_members(
        self,
        members: list[zipfile.ZipInfo],
    ) -> list[tuple[zipfile.ZipInfo, PurePosixPath]]:
        """Validate all ZIP members before writing any file.

        :param members: ZIP members to validate.
        :type members: list[zipfile.ZipInfo]
        :return: Members paired with normalized safe paths.
        :rtype: list[tuple[zipfile.ZipInfo, PurePosixPath]]
        :raises PathError: If a member is unsafe or archive limits are exceeded.
        """
        if len(members) > self.limits.max_members:
            err = (
                f"Refusing to extract {len(members)} ZIP members. "
                f"Maximum allowed member count is {self.limits.max_members}."
            )
            raise PathError(err)

        total_compressed = 0
        total_uncompressed = 0
        seen_paths: set[str] = set()
        seen_file_paths: set[str] = set()
        validated_members: list[tuple[zipfile.ZipInfo, PurePosixPath]] = []

        for member in members:
            member_path = self._normalize_member_path(member.filename)
            self._validate_member_path_conflicts(
                member,
                member_path,
                seen_paths,
                seen_file_paths,
            )
            self._validate_member_sizes(member)

            total_compressed += member.compress_size
            total_uncompressed += member.file_size

            self._validate_archive_size_totals(total_compressed, total_uncompressed)

            validated_members.append((member, member_path))

        self._validate_total_compression_ratio(total_compressed, total_uncompressed)

        logger.debug(
            "Validated ZIP archive: members=%d, compressed=%d bytes, "
            "uncompressed=%d bytes",
            len(validated_members),
            total_compressed,
            total_uncompressed,
        )

        return validated_members

    def _ensure_safe_parent(self, destination: Path, target: Path) -> None:
        """Ensure the target parent is inside destination and not symlinked.

        :param destination: Extraction root directory.
        :type destination: Path
        :param target: Target path about to be written.
        :type target: Path
        :raises PathError: If a parent directory is unsafe.
        """
        destination_resolved = destination.resolve(strict=True)
        parent_resolved = target.parent.resolve(strict=True)

        if destination_resolved != parent_resolved and (
            destination_resolved not in parent_resolved.parents
        ):
            err = f"Unsafe ZIP extraction parent path: {target.parent}."
            raise PathError(err)

        try:
            relative_parent = target.parent.relative_to(destination)
        except ValueError as e:
            err = f"Unsafe ZIP extraction parent path: {target.parent}."
            raise PathError(err) from e

        current = destination

        for part in relative_parent.parts:
            current = current / part

            if current.is_symlink():
                err = f"Refusing to extract through symlinked directory: {current}."
                raise PathError(err)

            if not current.is_dir():
                err = f"Refusing to extract through non-directory path: {current}."
                raise PathError(err)

            current_resolved = current.resolve(strict=True)

            if destination_resolved != current_resolved and (
                destination_resolved not in current_resolved.parents
            ):
                err = f"Unsafe ZIP extraction directory path: {current}."
                raise PathError(err)

    def _copy_member(
        self,
        zip_file: zipfile.ZipFile,
        member: zipfile.ZipInfo,
        target: Path,
    ) -> None:
        """Copy one validated file member without overwriting existing paths.

        :param zip_file: The open ZIP archive.
        :type zip_file: zipfile.ZipFile
        :param member: ZIP member metadata.
        :type member: zipfile.ZipInfo
        :param target: Destination file path.
        :type target: Path
        :raises PathError: If the target is unsafe or size checks fail.
        """
        if target.exists() or target.is_symlink():
            err = f"Refusing to overwrite existing path while extracting ZIP: {target}."
            raise PathError(err)

        if target.parent.is_symlink():
            err = (
                f"Refusing to extract into symlinked parent directory: {target.parent}."
            )
            raise PathError(err)

        bytes_written = 0

        try:
            with (
                zip_file.open(member, "r") as source,
                target.open("xb") as target_file,
            ):
                while True:
                    chunk = source.read(self.limits.copy_chunk_bytes)

                    if not chunk:
                        break

                    bytes_written += len(chunk)

                    if bytes_written > member.file_size:
                        err = (
                            f"ZIP member expanded beyond declared size: "
                            f"{member.filename!r}."
                        )
                        raise PathError(err)

                    if bytes_written > self.limits.max_member_extracted_bytes:
                        err = (
                            f"Refusing to extract ZIP member larger than "
                            f"{self.limits.max_member_extracted_bytes} bytes: "
                            f"{member.filename!r}."
                        )
                        raise PathError(err)

                    target_file.write(chunk)

        except Exception:
            with contextlib.suppress(OSError):
                target.unlink()
            raise

        if bytes_written != member.file_size:
            with contextlib.suppress(OSError):
                target.unlink()

            err = (
                f"ZIP member extracted size mismatch for {member.filename!r}: "
                f"expected {member.file_size} bytes, wrote {bytes_written} bytes."
            )
            raise PathError(err)

    def _extract_to_private_directory(
        self,
        zip_file: zipfile.ZipFile,
        destination: Path,
    ) -> None:
        """Extract validated members into a private temporary directory.

        :param zip_file: The open ZIP archive.
        :type zip_file: zipfile.ZipFile
        :param destination: Private extraction directory.
        :type destination: Path
        :raises PathError: If validation or extraction fails.
        """
        validated_members = self._validate_members(zip_file.infolist())

        destination.mkdir(parents=True, exist_ok=True)

        if destination.is_symlink():
            err = f"Refusing to extract into symlinked destination: {destination}."
            raise PathError(err)

        destination_resolved = destination.resolve(strict=True)

        if not destination_resolved.is_dir():
            err = f"ZIP extraction destination is not a directory: {destination}."
            raise PathError(err)

        for member, member_path in validated_members:
            target = self._zip_target(destination, member_path)

            if member.is_dir():
                if target.exists() and not target.is_dir():
                    err = (
                        f"Refusing to overwrite existing path while extracting ZIP: "
                        f"{target}."
                    )
                    raise PathError(err)

                target.mkdir(parents=True, exist_ok=True)
                self._ensure_safe_parent(destination, target)

                if target.is_symlink():
                    err = (
                        f"Refusing to create or use symlinked ZIP directory: {target}."
                    )
                    raise PathError(err)

                target_resolved = target.resolve(strict=True)

                if destination_resolved != target_resolved and (
                    destination_resolved not in target_resolved.parents
                ):
                    err = f"Unsafe ZIP directory path after creation: {target}."
                    raise PathError(err)

                continue

            target.parent.mkdir(parents=True, exist_ok=True)
            self._ensure_safe_parent(destination, target)
            self._copy_member(zip_file, member, target)

        logger.debug("Finished extracting ZIP members into %s", destination)

    def _make_private_extract_dir(self, base_dir: Path) -> Path:
        """Create a private temporary directory under base_dir.

        :param base_dir: Parent directory for temporary extraction.
        :type base_dir: Path
        :return: The created private directory.
        :rtype: Path
        :raises PathError: If base_dir is a symlink.
        """
        base_dir.mkdir(parents=True, exist_ok=True)

        if base_dir.is_symlink():
            err = (
                f"Refusing to create private extraction directory inside symlink: "
                f"{base_dir}."
            )
            raise PathError(err)

        extract_dir = Path(
            tempfile.mkdtemp(
                prefix="zip-extract-",
                dir=base_dir,
            ),
        )

        with contextlib.suppress(OSError):
            extract_dir.chmod(0o700)

        logger.debug("Created private ZIP extraction directory: %s", extract_dir)
        return extract_dir

    def _extractall_to_directory(
        self,
        zip_file: zipfile.ZipFile,
        final_directory: Path,
        private_work_dir: Path,
    ) -> None:
        """Extract into a private directory and move safe top-level entries.

        :param zip_file: The open ZIP archive.
        :type zip_file: zipfile.ZipFile
        :param final_directory: Final extraction destination.
        :type final_directory: Path
        :param private_work_dir: Parent directory for private extraction.
        :type private_work_dir: Path
        :raises PathError: If extraction or the final move is unsafe.
        """
        extract_dir = self._make_private_extract_dir(private_work_dir)

        try:
            self._extract_to_private_directory(zip_file, extract_dir)

            final_directory.mkdir(parents=True, exist_ok=True)

            if final_directory.is_symlink():
                err = (
                    f"Refusing to extract into symlinked"
                    f" destination: {final_directory}."
                )
                raise PathError(err)

            final_directory_resolved = final_directory.resolve(strict=True)

            if not final_directory_resolved.is_dir():
                err = (
                    f"ZIP extraction destination is not a directory: {final_directory}."
                )
                raise PathError(err)

            destinations: list[tuple[Path, Path]] = []
            for child in extract_dir.iterdir():
                if child.is_symlink():
                    err = f"Refusing to move symlinked extracted path: {child}."
                    raise PathError(err)

                destination = final_directory / child.name
                destination_resolved = destination.resolve(strict=False)

                if final_directory_resolved != destination_resolved and (
                    final_directory_resolved not in destination_resolved.parents
                ):
                    err = f"Unsafe extracted ZIP destination path: {destination}."
                    raise PathError(err)

                if destination.exists() or destination.is_symlink():
                    err = (
                        f"Refusing to overwrite existing path while extracting ZIP: "
                        f"{destination}."
                    )
                    raise PathError(err)

                destinations.append((child, destination))

            for child, destination in destinations:
                child.rename(destination)

            logger.debug(
                "Moved %d top-level ZIP entries to %s",
                len(destinations),
                final_directory,
            )

        except Exception:
            with contextlib.suppress(OSError):
                shutil.rmtree(extract_dir)
            raise
