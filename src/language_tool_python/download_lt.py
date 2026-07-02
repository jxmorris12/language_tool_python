"""LanguageTool download module."""

from __future__ import annotations

import contextlib
import hashlib
import importlib.resources
import logging
import os
import re
import subprocess
import tempfile
import zipfile
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from functools import total_ordering
from pathlib import Path
from shutil import which
from typing import IO, TYPE_CHECKING, cast
from urllib.parse import urljoin
from warnings import warn

import requests
import tqdm

from ._internals.compat import toml_loads
from ._internals.safe_zip import SafeZipExtractor
from ._internals.utils import (
    get_env_int,
    get_language_tool_download_path,
    version_tuple,
)
from .exceptions import JavaError, PathError

if TYPE_CHECKING:
    from collections.abc import Mapping
    from types import NotImplementedType

    from .config_file import LanguageToolConfig

__all__ = [
    "LTP_DOWNLOAD_VERSION",
    "LocalLanguageTool",
    "ReleaseLocalLanguageTool",
    "SnapshotLocalLanguageTool",
]

logger = logging.getLogger(__name__)

_MIN_JAVA_VERSION_FOR_OLD_LANGUAGE_TOOL = 9
_MIN_JAVA_VERSION_FOR_CURRENT_LANGUAGE_TOOL = 17
_HTTP_STATUS_NOT_FOUND = 404
_HTTP_STATUS_FORBIDDEN = 403
_HTTP_STATUS_OK = 200


# Get download host from environment or default.
_BASE_URL_SNAPSHOT = os.environ.get(
    "LTP_DOWNLOAD_HOST_SNAPSHOT",
    "https://internal1.languagetool.org/snapshots/",
)
_FILENAME_SNAPSHOT = "LanguageTool-{version}-snapshot.zip"
_BASE_URL_NEW_RELEASES = os.environ.get(
    "LTP_DOWNLOAD_HOST_NEW_RELEASES",
    "https://github.com/jxmorris12/language_tool_python/releases/download/LanguageTool-{version}/",
)
_BASE_URL_RELEASE = os.environ.get(
    "LTP_DOWNLOAD_HOST_RELEASE",
    "https://languagetool.org/download/",
)
_BASE_URL_ARCHIVE = os.environ.get(
    "LTP_DOWNLOAD_HOST_ARCHIVE",
    "https://languagetool.org/download/archive/",
)
_FILENAME_RELEASE = "LanguageTool-{version}.zip"

LTP_DOWNLOAD_VERSION: str = "6.8"
"""Default LanguageTool version downloaded and used by the library."""
_LT_SNAPSHOT_LATEST_VERSION = "latest"
_LTP_DOWNLOAD_SHA256_ENV_VAR = "LTP_DOWNLOAD_SHA256"
_LTP_BYPASS_VERIFIED_DOWNLOADS_ENV_VAR = "LTP_BYPASS_VERIFIED_DOWNLOADS"
_LTP_MAX_DOWNLOAD_BYTES_ENV_VAR = "LTP_MAX_DOWNLOAD_BYTES"
_LTP_JAR_DIR_PATH_ENV_VAR = "LTP_JAR_DIR_PATH"
_DOWNLOAD_CHUNK_BYTES = 1024 * 1024
_SAFE_ZIP_EXTRACTOR = SafeZipExtractor()


def _loads_manifest(raw_manifest: str) -> object:
    """Load the integrity manifest from a raw TOML string.

    :param raw_manifest: The raw TOML string containing the integrity manifest.
    :type raw_manifest: str
    :return: The parsed manifest as a Python object.
    :rtype: object
    """
    return cast("object", toml_loads(raw_manifest))


def _load_expected_download_sha256(raw_manifest: str) -> dict[str, str]:
    """Load and validate the bundled download checksum manifest.

    :param raw_manifest: The raw TOML string containing the integrity manifest.
    :type raw_manifest: str
    :return: A dictionary mapping version names to their expected SHA-256 hashes.
    :rtype: dict[str, str]
    """
    parsed = _loads_manifest(raw_manifest)
    if not isinstance(parsed, dict):
        err = "Invalid integrity manifest: expected a TOML table."
        raise PathError(err)

    manifest = cast("Mapping[object, object]", parsed)
    expected_hashes: dict[str, str] = {}
    for version_name, checksum in manifest.items():
        if not isinstance(version_name, str) or not isinstance(checksum, str):
            err = "Invalid integrity manifest: expected string keys and values."
            raise PathError(err)
        expected_hashes[version_name] = checksum
    return expected_hashes


with (
    importlib.resources.as_file(
        importlib.resources.files("language_tool_python")
        .joinpath("_ressources")
        .joinpath("integrity.toml"),
    ) as hashes_path,
    hashes_path.open("rb") as f,
):
    _EXPECTED_DOWNLOAD_SHA256 = _load_expected_download_sha256(
        f.read().decode("utf-8"),
    )

_JAVA_VERSION_REGEX = re.compile(
    r'^(?:java|openjdk) version "(?P<major1>\d+)(|\.(?P<major2>\d+)\.[^"]+)"',
    re.MULTILINE,
)

# Updated for later versions of java
_JAVA_VERSION_REGEX_UPDATED = re.compile(
    r"^(?:java|openjdk) [version ]?(?P<major1>\d+)\.(?P<major2>\d+)",
    re.MULTILINE,
)


_MAX_DOWNLOAD_BYTES = get_env_int(
    _LTP_MAX_DOWNLOAD_BYTES_ENV_VAR,
    512 * 1024 * 1024,
)  # 512 MiB, latest snapshot: 246.58 MiB archive


def _get_zip_hash(version_name: str) -> str | None:
    """Get the expected SHA-256 hash for a given version of LanguageTool.

    This function checks for environment variables that may specify the expected hash
    for the given version. It normalizes the version name to construct the environment
    variable name. If no specific environment variable is found for the version, it
    falls back to a general environment variable or a manifest lookup. If the bypass
    environment variable is set, it will skip verification and return None.

    :param version_name: The version name of LanguageTool (e.g., '6.0', '20240101', or
        'latest').
    :type version_name: str
    :return: The expected SHA-256 hash for the given version, or None if verification is
        bypassed or no hash is configured.
    :rtype: str | None
    :raises PathError: If a configured checksum is not a valid SHA-256 value.
    """
    if os.environ.get(_LTP_BYPASS_VERIFIED_DOWNLOADS_ENV_VAR, "").lower() == "true":
        err = (
            f"Verified downloads are bypassed. No SHA-256 checksum will be used for "
            f"LanguageTool {version_name}. Set "
            f"{_LTP_BYPASS_VERIFIED_DOWNLOADS_ENV_VAR}="
            f"false to re-enable verification."
        )
        warn(err, RuntimeWarning, stacklevel=2)
        return None
    suffix = re.sub(r"[^A-Za-z0-9]+", "_", version_name).strip("_").upper()
    version_env_var = f"LTP_DOWNLOAD_SHA256_{suffix}"
    configured = (
        (os.environ.get(version_env_var), version_env_var),
        (os.environ.get(_LTP_DOWNLOAD_SHA256_ENV_VAR), _LTP_DOWNLOAD_SHA256_ENV_VAR),
        (_EXPECTED_DOWNLOAD_SHA256.get(version_name), f"manifest:{version_name}"),
    )
    for checksum, source in configured:
        if checksum:
            normalized = checksum.strip().lower()
            if not re.fullmatch(r"[0-9a-f]{64}", normalized):
                err = f"Invalid SHA-256 checksum configured by {source}."
                raise PathError(err)
            return normalized
    return None


def _validate_download_size(content_length: str | None) -> int | None:
    """Validate the HTTP Content-Length header before downloading a ZIP file.

    :param content_length: The Content-Length header value, if present.
    :type content_length: str | None
    :return: The parsed content length, or None when the header is missing.
    :rtype: int | None
    :raises PathError: If the header is invalid or exceeds the download size limit.
    """
    if content_length is None:
        return None

    try:
        total = int(content_length)
    except ValueError as e:
        err = f"Invalid Content-Length header: {content_length!r}."
        raise PathError(err) from e

    if total < 0:
        err = f"Invalid Content-Length header: {content_length!r}."
        raise PathError(err)

    if total > _MAX_DOWNLOAD_BYTES:
        err = (
            f"Refusing to download {total} bytes. "
            f"Maximum allowed download size is {_MAX_DOWNLOAD_BYTES} bytes."
        )
        raise PathError(err)

    return total


def _parse_java_version(version_text: str) -> tuple[int, int]:
    """Parse the Java version from a given version text.

    This function attempts to extract the major version numbers from the provided Java
    version string using regular expressions. It supports two different version formats
    defined by _JAVA_VERSION_REGEX and _JAVA_VERSION_REGEX_UPDATED.

    :param version_text: The Java version string to parse.
    :type version_text: str
    :return: A tuple containing the major version numbers.
    :rtype: tuple[int, int]
    :raises SystemExit: If the version string cannot be parsed.
    """
    match = re.search(_JAVA_VERSION_REGEX, version_text) or re.search(
        _JAVA_VERSION_REGEX_UPDATED,
        version_text,
    )
    if not match:
        err = f"Could not parse Java version from '{version_text}'."
        raise SystemExit(err)
    major1 = int(match.group("major1"))
    major2 = int(match.group("major2")) if match.group("major2") else 0
    return (major1, major2)


def _confirm_java_compatibility(
    language_tool_version: str = LTP_DOWNLOAD_VERSION,
) -> None:
    """Confirm that the installed Java version is compatible with language-tool-python.

    This function checks if Java is installed and verifies that the major version is at
    least 9 or 17 (depending on the LanguageTool version). It raises an error if Java is
    not installed or if the version is incompatible.

    :param language_tool_version: The version of LanguageTool to check compatibility
        for.
    :type language_tool_version: str
    :raises ModuleNotFoundError: If no Java installation is detected.
    :raises SystemError: If the detected Java version is less than the required version.
    """
    java_path = which("java")
    if not java_path:
        err = (
            "No java install detected. Please install java to use language-tool-python."
        )
        raise ModuleNotFoundError(err)

    logger.debug("Found java executable at %s", java_path)

    output = subprocess.check_output(  # noqa: S603  # java_path come from shutil.which -> trusted
        [java_path, "-version"],
        stderr=subprocess.STDOUT,
        universal_newlines=True,
    )

    logger.debug("java -version output: %s", output.strip())

    major_version, minor_version = _parse_java_version(output)

    is_old_version = language_tool_version != LTP_DOWNLOAD_VERSION and (
        re.match(r"^\d+\.\d+$", language_tool_version)
        and version_tuple(language_tool_version) < (6, 6)  # 6.6
    )

    # Some installs of java show the version number like '14.0.1'
    # and others show '1.14.0.1'
    # (with a leading 1). We want to support both.
    # (See https://softwareengineering.stackexchange.com/questions/175075/why-is-java-version-1-x-referred-to-as-java-x)
    if is_old_version:
        if (
            major_version == 1
            and minor_version < _MIN_JAVA_VERSION_FOR_OLD_LANGUAGE_TOOL
        ) or (
            major_version != 1
            and major_version < _MIN_JAVA_VERSION_FOR_OLD_LANGUAGE_TOOL
        ):
            err = (
                f"Detected java {major_version}.{minor_version}. LanguageTool "
                f"requires Java >= 9 for version {language_tool_version}."
            )
            raise SystemError(err)
    elif (
        major_version == 1
        and minor_version < _MIN_JAVA_VERSION_FOR_CURRENT_LANGUAGE_TOOL
    ) or (
        major_version != 1
        and major_version < _MIN_JAVA_VERSION_FOR_CURRENT_LANGUAGE_TOOL
    ):
        err = (
            f"Detected java {major_version}.{minor_version}. LanguageTool "
            f"requiresJava >= 17 for version {language_tool_version}."
        )
        raise SystemError(err)


@total_ordering
class LocalLanguageTool(ABC):
    """Abstract base class for managing local LanguageTool installations.

    This class provides common functionality for handling LanguageTool downloads,
    installations, and server command generation. It supports both release versions and
    snapshot versions through its subclasses.
    """

    @classmethod
    def from_version_name(
        cls,
        version_name: str = LTP_DOWNLOAD_VERSION,
    ) -> LocalLanguageTool:
        """Create a LocalLanguageTool instance from a version name.

        This factory method determines the appropriate subclass
        (ReleaseLocalLanguageTool or SnapshotLocalLanguageTool) based on the version
        name format.

        :param version_name: The version name (e.g., '6.8', '20240101', or 'latest').
        :type version_name: str
        :return: An instance of the appropriate LocalLanguageTool subclass.
        :rtype: LocalLanguageTool
        :raises ValueError: If the version name format is not recognized.
        """
        if (
            re.match(r"^\d{8}$", version_name)
            or version_name == _LT_SNAPSHOT_LATEST_VERSION
        ):
            return SnapshotLocalLanguageTool(version_name)
        if re.match(r"^\d+\.\d+$", version_name):
            return ReleaseLocalLanguageTool(version_name)
        err = f"Unknown LanguageTool version name: {version_name}"
        raise ValueError(err)

    @classmethod
    def from_path(cls, path: Path) -> LocalLanguageTool:
        """Create a LocalLanguageTool instance from a directory path.

        This factory method extracts the version name from a LanguageTool directory path
        and creates the appropriate instance.

        :param path: The path to a LanguageTool installation directory.
        :type path: pathlib.Path
        :return: An instance of the appropriate LocalLanguageTool subclass.
        :rtype: LocalLanguageTool
        :raises ValueError: If the version cannot be determined from the path or the
            extracted version name is unsupported.
        """
        match = re.search(r"LanguageTool-(.+)", path.name)
        if not match:
            err = f"Could not determine LanguageTool version from path: {path}"
            raise ValueError(err)
        version_name = match.group(1)
        return cls.from_version_name(version_name)

    @abstractmethod
    def download(self) -> None:
        """Download and install the LanguageTool version.

        This abstract method must be implemented by subclasses to handle version-
        specific download logic.

        :raises NotImplementedError: Always, unless implemented by a subclass.
        """
        # Unreachable: ABC prevents direct instantiation of this abstract method.
        raise NotImplementedError  # pragma: no cover

    def _get_remote_zip(
        self,
        downloaded_file: IO[bytes],
        proxies: dict[str, str] | None = None,
    ) -> zipfile.ZipFile:
        """Download a LanguageTool ZIP file from a remote URL.

        This method handles the HTTP request, progress tracking, and error handling for
        downloading LanguageTool ZIP files.

        :param downloaded_file: A file-like object to write the downloaded content to.
        :type downloaded_file: IO[bytes]
        :param proxies: Optional proxy configuration for the HTTP request.
        :type proxies: dict[str, str] | None
        :return: A ZipFile object of the downloaded archive.
        :rtype: zipfile.ZipFile
        :raises TimeoutError: If the download request times out.
        :raises PathError: If the download fails due to HTTP errors (404, 403, etc.),
            if the checksum configuration is invalid, if the checksum does not match,
            or if the archive exceeds the configured download size limit.
        """
        logger.info("Starting download from %s", self.download_url)
        expected_sha256 = _get_zip_hash(self.version_name)
        sha256 = hashlib.sha256()
        try:
            req = requests.get(
                self.download_url,
                stream=True,
                proxies=proxies,
                timeout=60,
            )
        except requests.exceptions.Timeout as e:
            err = f"Request to {self.download_url} timed out."
            raise TimeoutError(err) from e
        if req.status_code == _HTTP_STATUS_NOT_FOUND:
            err = (
                f"Could not find at URL {self.download_url}. "
                f"The given version may not exist or is no longer available."
            )
            raise PathError(err)
        if req.status_code == _HTTP_STATUS_FORBIDDEN:
            err = (
                f"Access forbidden to URL {self.download_url}. "
                f"You may not have permission to access this resource. "
                f"It may be related to network restrictions (e.g., firewall, "
                f"proxy settings)."
            )
            raise PathError(err)
        if req.status_code != _HTTP_STATUS_OK:
            err = (
                f"Failed to download from {self.download_url}. "
                f"HTTP status code: {req.status_code}."
            )
            raise PathError(err)
        content_length = req.headers.get("Content-Length")
        total = _validate_download_size(content_length)
        progress = tqdm.tqdm(
            unit="B",
            unit_scale=True,
            total=total,
            desc=f"Downloading LanguageTool {self.version_name}",
        )
        downloaded_bytes = 0
        for chunk in req.iter_content(chunk_size=_DOWNLOAD_CHUNK_BYTES):
            if chunk:  # filter out keep-alive new chunks
                downloaded_bytes += len(chunk)
                if downloaded_bytes > _MAX_DOWNLOAD_BYTES:
                    progress.close()
                    err = (
                        f"Refusing to download more than {_MAX_DOWNLOAD_BYTES} bytes "
                        f"from {self.download_url}."
                    )
                    raise PathError(err)
                sha256.update(chunk)
                progress.update(len(chunk))
                downloaded_file.write(chunk)
        progress.close()
        actual_sha256 = sha256.hexdigest()
        logger.debug("Download completed. SHA-256: %s", actual_sha256)
        if expected_sha256 is not None and actual_sha256 != expected_sha256:
            err = (
                f"Downloaded LanguageTool archive checksum mismatch. "
                f"Expected {expected_sha256}, got {actual_sha256}."
            )
            raise PathError(err)
        downloaded_file.seek(0)
        return zipfile.ZipFile(downloaded_file)

    @classmethod
    def get_installed_versions(cls) -> list[LocalLanguageTool]:
        """Get a list of all installed LanguageTool versions.

        This method scans the download directory for LanguageTool installations and
        returns a list of LocalLanguageTool instances representing each version.

        :return: A list of installed LocalLanguageTool instances.
        :rtype: list[LocalLanguageTool]
        """
        download_folder = get_language_tool_download_path()
        language_tool_path_list = [
            path for path in download_folder.glob("LanguageTool*") if path.is_dir()
        ]

        versions: list[LocalLanguageTool] = []
        for path in language_tool_path_list:
            match = re.search(r"LanguageTool-(.+)", path.name)
            if match:
                with contextlib.suppress(ValueError):
                    versions.append(cls.from_path(path))
        return versions

    @classmethod
    def get_latest_installed_version(cls) -> LocalLanguageTool | None:
        """Get the latest installed LanguageTool version.

        This method finds all installed versions and returns the most recent one
        according to version ordering.

        :return: The latest installed LocalLanguageTool instance, or None if no versions
            are installed.
        :rtype: LocalLanguageTool | None
        """
        versions = cls.get_installed_versions()
        if not versions:
            return None
        return max(versions)

    def get_directory_path(self) -> Path:
        """Get the installation directory path for this LanguageTool version.

        This method searches the download folder for the directory matching this
        version's name.

        :return: The path to the LanguageTool installation directory.
        :rtype: pathlib.Path
        :raises FileNotFoundError: If the LanguageTool version directory is not found.
        """
        download_folder = get_language_tool_download_path()
        language_tool_path_list = [
            path for path in download_folder.glob("LanguageTool*") if path.is_dir()
        ]

        if not language_tool_path_list:
            err = f"LanguageTool not found in {download_folder}."
            raise FileNotFoundError(err)

        for path in language_tool_path_list:
            if path.name == f"LanguageTool-{self.version_name}":
                logger.debug("Using LanguageTool directory: %s", path)
                return path

        err = (
            f"LanguageTool version {self.version_name} not found in {download_folder}."
        )
        raise FileNotFoundError(err)

    def get_jar_path(self) -> Path:
        """Get the path to the LanguageTool JAR file.

        This method locates the main JAR file (languagetool-server.jar or
        languagetool.jar) within the installation directory.

        :return: The path to the LanguageTool JAR file.
        :rtype: pathlib.Path
        :raises FileNotFoundError: If no LanguageTool JAR file is found.
        """
        directory_path = self.get_directory_path()
        for jar_name in [
            "languagetool-server.jar",
            "languagetool.jar",
        ]:
            jar_path = directory_path / jar_name
            if jar_path.exists():
                logger.debug("Using LanguageTool JAR: %s", jar_path)
                return jar_path
        err = f"LanguageTool JAR not found in {directory_path}."
        raise FileNotFoundError(err)

    def get_server_cmd(
        self,
        port: int | None = None,
        config: LanguageToolConfig | None = None,
    ) -> list[str]:
        """Generate the command to start the LanguageTool HTTP server.

        :param port: Optional; The port number on which the server should run. If not
            provided, the default port will be used.
        :type port: int | None
        :param config: Optional; The configuration for the LanguageTool server. If not
            provided, default configuration will be used.
        :type config: LanguageToolConfig | None
        :return: A list of command line arguments to start the LanguageTool HTTP server.
        :rtype: list[str]
        :raises JavaError: If the Java executable cannot be found.
        :raises FileNotFoundError: If the LanguageTool installation directory or JAR
            file cannot be found.
        """
        java_path_str = which("java")
        if not java_path_str:
            err = "can't find Java"
            raise JavaError(err)
        java_path = Path(java_path_str)
        jar_path = self.get_jar_path()
        cmd = [
            str(java_path),
            "-cp",
            str(jar_path),
            "org.languagetool.server.HTTPServer",
        ]

        if port is not None:
            cmd += ["-p", str(port)]

        if config is not None:
            cmd += ["--config", config.path]

        logger.debug("LanguageTool server command: %r", cmd)
        return cmd

    @property
    @abstractmethod
    def version_name(self) -> str:
        """Get the version name string.

        This abstract property must be implemented by subclasses to return the version
        identifier.

        :return: The version name.
        :rtype: str
        :raises NotImplementedError: Always, unless implemented by a subclass.
        """
        raise NotImplementedError  # pragma: no cover  # abstract body

    @property
    @abstractmethod
    def version_into(self) -> tuple[int, int] | datetime:
        """Get the version as a comparable object.

        This abstract property must be implemented by subclasses to return the version
        as either a tuple of integers (for releases) or datetime object (for snapshots)
        for comparison purposes.

        :return: A tuple of integers for releases or datetime for snapshots.
        :rtype: tuple[int, int] | datetime.datetime
        :raises NotImplementedError: Always, unless implemented by a subclass.
        """
        raise NotImplementedError  # pragma: no cover  # abstract body

    @property
    @abstractmethod
    def download_url(self) -> str:
        """Get the download URL for this LanguageTool version.

        This abstract property must be implemented by subclasses to return the
        appropriate download URL.

        :return: The download URL.
        :rtype: str
        :raises NotImplementedError: Always, unless implemented by a subclass.
        """
        raise NotImplementedError  # pragma: no cover  # abstract body

    def __eq__(self, other: object) -> bool:
        """Check equality between two LocalLanguageTool instances.

        Two instances are considered equal if they have the same version name.

        :param other: The object to compare with.
        :type other: object
        :return: True if equal, False otherwise, NotImplemented for non-
            LocalLanguageTool objects.
        :rtype: bool
        """
        if not isinstance(other, LocalLanguageTool):
            return NotImplemented
        return self.version_name == other.version_name

    def __lt__(self, other: object) -> bool:
        """Compare two LocalLanguageTool instances for ordering.

        Snapshot versions are always considered newer than release versions. Within the
        same type, versions are compared using their version_into property.

        :param other: The object to compare with.
        :type other: object
        :return: True if self is less than other, False otherwise, NotImplemented for
            incompatible types.
        :rtype: bool
        """
        res: bool | NotImplementedType = NotImplemented
        if isinstance(other, LocalLanguageTool):
            if isinstance(self, SnapshotLocalLanguageTool) and isinstance(
                other, ReleaseLocalLanguageTool
            ):
                res = False
            elif isinstance(self, ReleaseLocalLanguageTool) and isinstance(
                other, SnapshotLocalLanguageTool
            ):
                res = True
            elif type(self) is not type(other):
                res = NotImplemented
            else:
                self_version = self.version_into
                other_version = other.version_into
                if (
                    isinstance(self_version, tuple) and isinstance(other_version, tuple)
                ) or (
                    isinstance(self_version, datetime)
                    and isinstance(other_version, datetime)
                ):
                    res = self_version < other_version  # type: ignore[operator]  # mypy doesn't get that the types are the same here
                else:
                    res = NotImplemented
        return res

    def __hash__(self) -> int:
        """Return the hash of the LocalLanguageTool instance.

        If the version name is modified, the hash will change.

        :return: The hash of the version name.
        :rtype: int
        """
        return hash(self.version_name)


class ReleaseLocalLanguageTool(LocalLanguageTool):
    """Represents a release version of LanguageTool.

    This class handles release versions of LanguageTool (e.g., '6.0', '5.9') which are
    downloaded from the official release pages.

    Releases are the old way of downloading LanguageTool.

    :param version: The release version string (e.g., '6.0').
    :type version: str
    """

    def __init__(self, version: str) -> None:
        """Initialize a ReleaseLocalLanguageTool instance."""
        self._version_name = version

    def download(self) -> None:
        """Download and install this release version of LanguageTool.

        This method checks Java compatibility, downloads the release ZIP file, and
        extracts it to the download folder if not already installed.

        :raises ModuleNotFoundError: If no Java installation is detected.
        :raises SystemError: If the detected Java version is incompatible.
        :raises TimeoutError: If the download request times out.
        :raises PathError: If the version is unsupported, the download fails, checksum
            validation fails, or ZIP extraction is unsafe.
        """
        _confirm_java_compatibility(self._version_name)

        download_folder = get_language_tool_download_path()

        # Use the env var to the jar directory if it is defined
        # otherwise look in the download directory
        if os.environ.get(_LTP_JAR_DIR_PATH_ENV_VAR):
            return

        if self not in self.get_installed_versions():
            with (  # pragma: no cover  # integration: HTTP download + extraction
                tempfile.TemporaryDirectory(dir=download_folder) as temp_dir,
                tempfile.NamedTemporaryFile(
                    suffix=".zip",
                    dir=temp_dir,
                ) as downloaded_file,
                self._get_remote_zip(downloaded_file) as zip_file,
            ):
                _SAFE_ZIP_EXTRACTOR.extractall(
                    zip_file,
                    download_folder,
                    work_dir=Path(temp_dir),
                )

    @property
    def version_name(self) -> str:
        """Get the release version name.

        :return: The release version string.
        :rtype: str
        """
        return self._version_name

    @property
    def version_into(self) -> tuple[int, int]:
        """Get the version as a tuple of integers for comparison.

        :return: A tuple of integers representing the version.
        :rtype: tuple[int, int]
        """
        return version_tuple(self._version_name)

    @property
    def download_url(self) -> str:
        """Get the download URL for this release version.

        URLs are constructed based on version:
        - Versions >= 6.7 are downloaded from the new release page
        - Versions 6.0 - 6.6 are downloaded from the main release page
        - Versions 4.0 - 5.9 are downloaded from the archive
        - Versions < 4.0 are not supported

        :return: The download URL for this version.
        :rtype: str
        :raises PathError: If the version is below 4.0 (unsupported).
        """
        version_num = version_tuple(self._version_name)
        filename = _FILENAME_RELEASE.format(version=self._version_name)
        # Versions >= 6.7 from new release page
        if version_num >= (6, 7):  # 6.7
            base_url = _BASE_URL_NEW_RELEASES.format(version=self._version_name)
            return urljoin(base_url, filename)
        # Versions >= 6.0 from main download page
        if version_num >= (6, 0):  # 6.0
            return urljoin(_BASE_URL_RELEASE, filename)
        if version_num < (4, 0):  # 4.0
            err = (
                "LanguageTool versions below 4.0 are no longer supported for download."
                " Below version 4.0, the API changed significantly and is "
                "not compatible."
            )
            raise PathError(err)
        # Versions < 6.0 from archive
        return urljoin(_BASE_URL_ARCHIVE, filename)

    def __eq__(self, other: object) -> bool:
        """Check equality between two ReleaseLocalLanguageTool instances.

        Two instances are considered equal if they have the same version name.

        :param other: The object to compare with.
        :type other: object
        :return: True if the instances are equal, False otherwise.
        :rtype: bool
        """
        return super().__eq__(other)

    def __hash__(self) -> int:
        """Return the hash of the ReleaseLocalLanguageTool instance.

        If the version name is modified, the hash will change.

        :return: The hash of the version name.
        :rtype: int
        """
        return super().__hash__()


class SnapshotLocalLanguageTool(LocalLanguageTool):
    """Represents a snapshot (development) version of LanguageTool.

    This class handles snapshot versions of LanguageTool, which are nightly builds
    identified by date strings (e.g., '20240101') or 'latest'.

    Snapshots are the new common way of downloading LanguageTool.

    :param version_name: The snapshot version (date string or 'latest').
    :type version_name: str
    """

    def __init__(self, version_name: str) -> None:
        """Initialize a SnapshotLocalLanguageTool instance."""
        self._version_name = version_name
        self._install_version_name = (
            datetime.now(timezone.utc).strftime("%Y%m%d")
            if version_name == _LT_SNAPSHOT_LATEST_VERSION
            else version_name
        )

    def download(self) -> None:
        """Download and install this snapshot version of LanguageTool.

        This method checks Java compatibility, downloads the snapshot ZIP file, and
        extracts it to the download folder using the requested snapshot name.

        :raises ModuleNotFoundError: If no Java installation is detected.
        :raises SystemError: If the detected Java version is incompatible.
        :raises TimeoutError: If the download request times out.
        :raises PathError: If the download fails, checksum validation fails, ZIP
            extraction is unsafe, or the extracted snapshot layout is invalid.
        """
        _confirm_java_compatibility(self._version_name)

        download_folder = get_language_tool_download_path()

        # Use the env var to the jar directory if it is defined
        # otherwise look in the download directory
        if os.environ.get(_LTP_JAR_DIR_PATH_ENV_VAR):
            return

        if self not in self.get_installed_versions():
            with (
                tempfile.TemporaryDirectory(dir=download_folder) as temp_dir,
                tempfile.NamedTemporaryFile(
                    suffix=".zip",
                    dir=temp_dir,
                ) as downloaded_file,
                self._get_remote_zip(downloaded_file) as zip_file,
            ):
                snapshot_extract_dir = Path(temp_dir) / "snapshot"
                _SAFE_ZIP_EXTRACTOR.extractall(
                    zip_file,
                    snapshot_extract_dir,
                    work_dir=Path(temp_dir),
                )
                extracted_roots = list(snapshot_extract_dir.iterdir())
                if len(extracted_roots) != 1 or not extracted_roots[0].is_dir():
                    err = (
                        "Expected snapshot archive to contain exactly one "
                        "root directory."
                    )
                    raise PathError(err)

                expected_dir = download_folder / f"LanguageTool-{self.version_name}"
                if (  # pragma: no cover  # TOCTOU: dir appears between check and rename
                    expected_dir.exists() or expected_dir.is_symlink()
                ):
                    err = (
                        "Refusing to overwrite existing LanguageTool snapshot "
                        f"directory: {expected_dir}."
                    )
                    raise PathError(err)

                logger.debug(
                    "Renaming extracted snapshot directory %s to %s",
                    extracted_roots[0],
                    expected_dir,
                )
                extracted_roots[0].rename(expected_dir)

    @property
    def version_name(self) -> str:
        """Get the snapshot version name.

        Returns the current date if 'latest' was specified, otherwise returns the
        specified date string.

        :return: The snapshot version string.
        :rtype: str
        """
        return self._install_version_name

    @property
    def version_into(self) -> datetime:
        """Get the snapshot version as a datetime object for comparison.

        Converts the version date string to a datetime object. For 'latest', uses the
        current date.

        :return: A datetime object representing the snapshot date.
        :rtype: datetime.datetime
        :raises ValueError: If the snapshot version is not a valid ``YYYYMMDD`` date.
        """
        return datetime.strptime(self.version_name, "%Y%m%d")  # noqa: DTZ007  # Constructing a datetime without timezone because it is the format of the version string

    @property
    def download_url(self) -> str:
        """Get the download URL for this snapshot version.

        Constructs the URL to download the snapshot from the snapshot server.

        :return: The download URL for this snapshot.
        :rtype: str
        """
        filename = _FILENAME_SNAPSHOT.format(version=self._version_name)
        return urljoin(_BASE_URL_SNAPSHOT, filename)

    def __eq__(self, other: object) -> bool:
        """Check equality between two SnapshotLocalLanguageTool instances.

        Two instances are considered equal if they have the same version name.

        :param other: The object to compare with.
        :type other: object
        :return: True if the instances are equal, False otherwise.
        :rtype: bool
        """
        return super().__eq__(other)

    def __hash__(self) -> int:
        """Return the hash of the SnapshotLocalLanguageTool instance.

        If the version name is modified, the hash will change.

        :return: The hash of the version name.
        :rtype: int
        """
        return super().__hash__()
