"""LanguageTool download module."""

import contextlib
import logging
import os
import re
import subprocess
import tempfile
import zipfile
from abc import ABC, abstractmethod
from datetime import datetime
from functools import total_ordering
from pathlib import Path
from shutil import which
from typing import IO, Dict, List, Optional, Tuple, Union
from urllib.parse import urljoin

import requests
import tqdm
from packaging import version
from packaging.version import Version

from ._deprecated import deprecated
from .config_file import LanguageToolConfig
from .exceptions import JavaError, PathError
from .utils import (
    LTP_JAR_DIR_PATH_ENV_VAR,
    get_language_tool_download_path,
)

logger = logging.getLogger(__name__)


# Get download host from environment or default.
BASE_URL_SNAPSHOT = os.environ.get(
    "LTP_DOWNLOAD_HOST_SNAPSHOT",
    "https://internal1.languagetool.org/snapshots/",
)
FILENAME_SNAPSHOT = "LanguageTool-{version}-snapshot.zip"
BASE_URL_RELEASE = os.environ.get(
    "LTP_DOWNLOAD_HOST_RELEASE",
    "https://languagetool.org/download/",
)
BASE_URL_ARCHIVE = os.environ.get(
    "LTP_DOWNLOAD_HOST_ARCHIVE",
    "https://languagetool.org/download/archive/",
)
FILENAME_RELEASE = "LanguageTool-{version}.zip"

LTP_DOWNLOAD_VERSION = "latest"
LT_SNAPSHOT_CURRENT_VERSION = "6.8-SNAPSHOT"

JAVA_VERSION_REGEX = re.compile(
    r'^(?:java|openjdk) version "(?P<major1>\d+)(|\.(?P<major2>\d+)\.[^"]+)"',
    re.MULTILINE,
)

# Updated for later versions of java
JAVA_VERSION_REGEX_UPDATED = re.compile(
    r"^(?:java|openjdk) [version ]?(?P<major1>\d+)\.(?P<major2>\d+)",
    re.MULTILINE,
)


def parse_java_version(version_text: str) -> Tuple[int, int]:
    """
    Parse the Java version from a given version text.

    This function attempts to extract the major version numbers from the provided
    Java version string using regular expressions. It supports two different
    version formats defined by JAVA_VERSION_REGEX and JAVA_VERSION_REGEX_UPDATED.

    :param version_text: The Java version string to parse.
    :type version_text: str
    :return: A tuple containing the major version numbers.
    :rtype: Tuple[int, int]
    :raises SystemExit: If the version string cannot be parsed.
    """
    match = re.search(JAVA_VERSION_REGEX, version_text) or re.search(
        JAVA_VERSION_REGEX_UPDATED,
        version_text,
    )
    if not match:
        err = f"Could not parse Java version from '{version_text}'."
        raise SystemExit(err)
    major1 = int(match.group("major1"))
    major2 = int(match.group("major2")) if match.group("major2") else 0
    return (major1, major2)


def confirm_java_compatibility(
    language_tool_version: str = LTP_DOWNLOAD_VERSION,
) -> None:
    """
    Confirms if the installed Java version is compatible with language-tool-python.
    This function checks if Java is installed and verifies that the major version is at least 9 or 17 (depending on the LanguageTool version).
    It raises an error if Java is not installed or if the version is incompatible.

    :param language_tool_version: The version of LanguageTool to check compatibility for.
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

    major_version, minor_version = parse_java_version(output)

    is_old_version = language_tool_version != LTP_DOWNLOAD_VERSION and (
        re.match(r"^\d+\.\d+$", language_tool_version)
        and Version(language_tool_version) < Version("6.6")
    )

    # Some installs of java show the version number like '14.0.1'
    # and others show '1.14.0.1'
    # (with a leading 1). We want to support both.
    # (See softwareengineering.stackexchange.com/questions/175075/why-is-java-version-1-x-referred-to-as-java-x)
    if is_old_version:
        if (major_version == 1 and minor_version < 9) or (
            major_version != 1 and major_version < 9
        ):
            err = f"Detected java {major_version}.{minor_version}. LanguageTool requires Java >= 9 for version {language_tool_version}."
            raise SystemError(err)
    else:
        if (major_version == 1 and minor_version < 17) or (
            major_version != 1 and major_version < 17
        ):
            err = f"Detected java {major_version}.{minor_version}. LanguageTool requires Java >= 17 for version {language_tool_version}."
            raise SystemError(err)


@deprecated(
    "This function is no longer used internally and will be removed in 4.0.",
    stacklevel=2,
)  # type: ignore
def get_common_prefix(z: zipfile.ZipFile) -> Optional[str]:
    """
    Determine the common prefix of all file names in a zip archive.

    :param z: A ZipFile object representing the zip archive.
    :type z: zipfile.ZipFile
    :return: The common prefix of all file names in the zip archive, or None if there is no common prefix.
    :rtype: Optional[str]

    .. deprecated:: 3.3.0
        This function is no longer used internally and will be removed in 4.0.
    """

    name_list = z.namelist()
    if name_list and all(n.startswith(name_list[0]) for n in name_list[1:]):
        return name_list[0]
    return None


@deprecated(
    "This function is no longer used internally and will be removed in 4.0.",
    stacklevel=2,
)  # type: ignore
def http_get(
    url: str,
    out_file: IO[bytes],
    proxies: Optional[Dict[str, str]] = None,
) -> None:
    """
    .. deprecated:: 3.3.0
        This function is no longer used internally and will be removed in 4.0.
    """
    version_match = re.search(r"LanguageTool-(.+)\.zip", url)
    version_name = version_match.group(1) if version_match else LTP_DOWNLOAD_VERSION

    # Normalize snapshot-style version names (e.g. "6.8-SNAPSHOT", "latest-snapshot")
    if version_name.lower().endswith("-snapshot"):
        version_name = version_name[: -len("-snapshot")]
    try:
        local_lt = LocalLanguageTool.from_version_name(version_name)
    except ValueError:
        # Fallback to default behavior if the extracted version is not supported
        local_lt = LocalLanguageTool.from_version_name(LTP_DOWNLOAD_VERSION)

    with local_lt._get_remote_zip(out_file, proxies=proxies):  #  type: ignore
        pass


@deprecated(
    "This function is no longer used internally and will be removed in 4.0.",
    stacklevel=2,
)  # type: ignore
def unzip_file(temp_file_name: str, directory_to_extract_to: Path) -> None:
    """
    Unzips a zip file to a specified directory.

    :param temp_file_name: A temporary file object representing the zip file to be extracted.
    :type temp_file_name: str
    :param directory_to_extract_to: The directory where the contents of the zip file will be extracted.
    :type directory_to_extract_to: Path

    .. deprecated:: 3.3.0
        This function is no longer used internally and will be removed in 4.0.
    """

    logger.info("Unzipping %s to %s", temp_file_name, directory_to_extract_to)
    with zipfile.ZipFile(temp_file_name, "r") as zip_ref:
        zip_ref.extractall(directory_to_extract_to)


@deprecated(
    "This function is no longer used internally and will be removed in 4.0.",
    stacklevel=2,
)  # type: ignore
def download_zip(url: str, directory: Path) -> None:
    """
    Downloads a ZIP file from the given URL and extracts it to the specified directory.

    :param url: The URL of the ZIP file to download.
    :type url: str
    :param directory: The directory where the ZIP file should be extracted.
    :type directory: Path

    .. deprecated:: 3.3.0
        This function is no longer used internally and will be removed in 4.0.
    """
    logger.info("Downloading from %s to %s", url, directory)
    # Download file using a context manager.
    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as downloaded_file:
        http_get(url, downloaded_file)  # type: ignore
        temp_name = downloaded_file.name
    # Extract zip file to path.
    unzip_file(temp_name, directory)  # type: ignore
    # Remove the temporary file.
    Path(temp_name).unlink(missing_ok=True)


@deprecated(
    "This function is no longer used internally and will be removed in 4.0.\nUse instead language_tool_python.download_lt.LocalLanguageTool.download.",
    stacklevel=2,
)  # type: ignore
def download_lt(language_tool_version: str = LTP_DOWNLOAD_VERSION) -> None:
    """
    Downloads and extracts the specified version of LanguageTool.
    This function checks for Java compatibility, and downloads the specified version of
    LanguageTool if it is not already present.

    :param language_tool_version: The version of LanguageTool to download. If not
                                  specified, the default version defined by
                                  LTP_DOWNLOAD_VERSION is used.
    :type language_tool_version: str
    :raises PathError: If the download folder is not a directory.
    :raises ValueError: If the specified version format is invalid.

    .. deprecated:: 3.3.0
        This function is no longer used internally and will be removed in 4.0.
    """
    # Use the env var to the jar directory if it is defined
    # otherwise look in the download directory
    if os.environ.get(LTP_JAR_DIR_PATH_ENV_VAR):
        return

    local_lt = LocalLanguageTool.from_version_name(language_tool_version)

    if local_lt not in local_lt.get_installed_versions():
        local_lt.download()


@total_ordering
class LocalLanguageTool(ABC):
    """
    Abstract base class for managing local LanguageTool installations.

    This class provides common functionality for handling LanguageTool downloads,
    installations, and server command generation. It supports both release versions
    and snapshot versions through its subclasses.
    """

    @classmethod
    def from_version_name(
        cls,
        version_name: str = LTP_DOWNLOAD_VERSION,
    ) -> "LocalLanguageTool":
        """
        Create a LocalLanguageTool instance from a version name.

        This factory method determines the appropriate subclass (ReleaseLocalLanguageTool
        or SnapshotLocalLanguageTool) based on the version name format.

        :param version_name: The version name (e.g., '6.0', '20240101', or 'latest').
        :type version_name: str
        :return: An instance of the appropriate LocalLanguageTool subclass.
        :rtype: LocalLanguageTool
        :raises ValueError: If the version name format is not recognized.
        """
        if re.match(r"^\d{8}$", version_name) or version_name == LTP_DOWNLOAD_VERSION:
            return SnapshotLocalLanguageTool(version_name)
        if re.match(r"^\d+\.\d+$", version_name):
            return ReleaseLocalLanguageTool(version_name)
        raise ValueError(f"Unknown LanguageTool version name: {version_name}")

    @classmethod
    def from_path(cls, path: Path) -> "LocalLanguageTool":
        """
        Create a LocalLanguageTool instance from a directory path.

        This factory method extracts the version name from a LanguageTool directory
        path and creates the appropriate instance.

        :param path: The path to a LanguageTool installation directory.
        :type path: Path
        :return: An instance of the appropriate LocalLanguageTool subclass.
        :rtype: LocalLanguageTool
        :raises ValueError: If the version cannot be determined from the path.
        """
        match = re.search(r"LanguageTool-(.+)", path.name)
        if not match:
            err = f"Could not determine LanguageTool version from path: {path}"
            raise ValueError(err)
        version_name = match.group(1)
        return cls.from_version_name(
            version_name
            if version_name != LT_SNAPSHOT_CURRENT_VERSION
            else LTP_DOWNLOAD_VERSION
        )

    @abstractmethod
    def download(self) -> None:
        """
        Download and install the LanguageTool version.

        This abstract method must be implemented by subclasses to handle
        version-specific download logic.
        """
        pass

    def _get_remote_zip(
        self, downloaded_file: IO[bytes], proxies: Optional[Dict[str, str]] = None
    ) -> zipfile.ZipFile:
        """
        Download a LanguageTool ZIP file from a remote URL.

        This method handles the HTTP request, progress tracking, and error handling
        for downloading LanguageTool ZIP files.

        :param downloaded_file: A file-like object to write the downloaded content to.
        :type downloaded_file: IO[bytes]
        :param proxies: Optional proxy configuration for the HTTP request.
        :type proxies: Optional[Dict[str, str]]
        :return: A ZipFile object of the downloaded archive.
        :rtype: zipfile.ZipFile
        :raises TimeoutError: If the download request times out.
        :raises PathError: If the download fails due to HTTP errors (404, 403, etc.).
        """
        logger.info("Starting download from %s", self.download_url)
        try:
            req = requests.get(
                self.download_url, stream=True, proxies=proxies, timeout=60
            )
        except requests.exceptions.Timeout as e:
            err = f"Request to {self.download_url} timed out."
            raise TimeoutError(err) from e
        content_length = req.headers.get("Content-Length")
        total = int(content_length) if content_length is not None else None
        if req.status_code == 404:
            err = f"Could not find at URL {self.download_url}. The given version may not exist or is no longer available."
            raise PathError(err)
        if req.status_code == 403:
            err = f"Access forbidden to URL {self.download_url}. You may not have permission to access this resource. It may be related to network restrictions (e.g., firewall, proxy settings)."
            raise PathError(err)
        if req.status_code != 200:
            err = f"Failed to download from {self.download_url}. HTTP status code: {req.status_code}."
            raise PathError(err)
        progress = tqdm.tqdm(
            unit="B",
            unit_scale=True,
            total=total,
            desc=f"Downloading LanguageTool {self.version_name}",
        )
        for chunk in req.iter_content(chunk_size=1024):
            if chunk:  # filter out keep-alive new chunks
                progress.update(len(chunk))
                downloaded_file.write(chunk)
        progress.close()
        return zipfile.ZipFile(downloaded_file)

    @classmethod
    def get_installed_versions(cls) -> List["LocalLanguageTool"]:
        """
        Get a list of all installed LanguageTool versions.

        This method scans the download directory for LanguageTool installations
        and returns a list of LocalLanguageTool instances representing each version.

        :return: A list of installed LocalLanguageTool instances.
        :rtype: List[LocalLanguageTool]
        """
        download_folder = get_language_tool_download_path()
        language_tool_path_list = [
            path for path in download_folder.glob("LanguageTool*") if path.is_dir()
        ]

        versions: List["LocalLanguageTool"] = []
        for path in language_tool_path_list:
            match = re.search(r"LanguageTool-(.+)", path.name)
            if match:
                with contextlib.suppress(ValueError):
                    versions.append(cls.from_path(path))
        return versions

    @classmethod
    def get_latest_installed_version(cls) -> Optional["LocalLanguageTool"]:
        """
        Get the latest installed LanguageTool version.

        This method finds all installed versions and returns the most recent one
        according to version ordering.

        :return: The latest installed LocalLanguageTool instance, or None if no versions are installed.
        :rtype: Optional[LocalLanguageTool]
        """
        versions = cls.get_installed_versions()
        if not versions:
            return None
        return max(versions)

    def get_directory_path(self) -> Path:
        """
        Get the installation directory path for this LanguageTool version.

        This method searches the download folder for the directory matching
        this version's name.

        :return: The path to the LanguageTool installation directory.
        :rtype: Path
        :raises FileNotFoundError: If the LanguageTool version directory is not found.
        """
        download_folder = get_language_tool_download_path()
        language_tool_path_list = [
            path for path in download_folder.glob("LanguageTool*") if path.is_dir()
        ]

        if not len(language_tool_path_list):
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
        """
        Get the path to the LanguageTool JAR file.

        This method locates the main JAR file (languagetool-server.jar or
        languagetool.jar) within the installation directory.

        :return: The path to the LanguageTool JAR file.
        :rtype: Path
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
        port: Optional[int] = None,
        config: Optional[LanguageToolConfig] = None,
    ) -> List[str]:
        """
        Generate the command to start the LanguageTool HTTP server.

        :param port: Optional; The port number on which the server should run. If not provided, the default port will be used.
        :type port: Optional[int]
        :param config: Optional; The configuration for the LanguageTool server. If not provided, default configuration will be used.
        :type config: Optional[LanguageToolConfig]
        :return: A list of command line arguments to start the LanguageTool HTTP server.
        :rtype: List[str]
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
        """
        Get the version name string.

        This abstract property must be implemented by subclasses to return
        the version identifier.

        :return: The version name.
        :rtype: str
        """
        pass

    @property
    @abstractmethod
    def version_into(self) -> Union[Version, datetime]:
        """
        Get the version as a comparable object.

        This abstract property must be implemented by subclasses to return
        the version as either a Version object (for releases) or datetime
        object (for snapshots) for comparison purposes.

        :return: A Version object for releases or datetime for snapshots.
        :rtype: Union[Version, datetime]
        """
        pass

    @property
    @abstractmethod
    def download_url(self) -> str:
        """
        Get the download URL for this LanguageTool version.

        This abstract property must be implemented by subclasses to return
        the appropriate download URL.

        :return: The download URL.
        :rtype: str
        """
        pass

    def __eq__(self, other: object) -> bool:
        """
        Check equality between two LocalLanguageTool instances.

        Two instances are considered equal if they have the same version name.

        :param other: The object to compare with.
        :type other: object
        :return: True if equal, False otherwise, NotImplemented for non-LocalLanguageTool objects.
        :rtype: bool
        """
        if not isinstance(other, LocalLanguageTool):
            return NotImplemented
        return self.version_name == other.version_name

    def __lt__(self, other: object) -> bool:
        """
        Compare two LocalLanguageTool instances for ordering.

        Snapshot versions are always considered newer than release versions.
        Within the same type, versions are compared using their version_into property.

        :param other: The object to compare with.
        :type other: object
        :return: True if self is less than other, False otherwise, NotImplemented for incompatible types.
        :rtype: bool
        """
        if not isinstance(other, LocalLanguageTool):
            return NotImplemented
        if isinstance(self, SnapshotLocalLanguageTool) and isinstance(
            other, ReleaseLocalLanguageTool
        ):
            return False
        if isinstance(self, ReleaseLocalLanguageTool) and isinstance(
            other, SnapshotLocalLanguageTool
        ):
            return True
        if type(self) != type(other):
            return NotImplemented
        # At this point, both objects are the same type, so version_into will be the same type
        self_version = self.version_into
        other_version = other.version_into
        return self_version < other_version  # type: ignore


class ReleaseLocalLanguageTool(LocalLanguageTool):
    """
    Represents a release version of LanguageTool.

    This class handles release versions of LanguageTool (e.g., '6.0', '5.9')
    which are downloaded from the official release pages.

    Releases are the old way of downloading LanguageTool.

    :param version: The release version string (e.g., '6.0').
    :type version: str
    """

    def __init__(self, version: str) -> None:
        """
        Initialize a ReleaseLocalLanguageTool instance.
        """
        self._version_name = version

    def download(self) -> None:
        """
        Download and install this release version of LanguageTool.

        This method checks Java compatibility, downloads the release ZIP file,
        and extracts it to the download folder if not already installed.
        """
        confirm_java_compatibility(self._version_name)

        download_folder = get_language_tool_download_path()

        # Use the env var to the jar directory if it is defined
        # otherwise look in the download directory
        if os.environ.get(LTP_JAR_DIR_PATH_ENV_VAR):
            return

        if self not in self.get_installed_versions():
            with (
                tempfile.TemporaryDirectory() as temp_dir,
                tempfile.NamedTemporaryFile(
                    suffix=".zip", dir=temp_dir
                ) as downloaded_file,
                self._get_remote_zip(downloaded_file) as zip_file,
            ):
                zip_file.extractall(download_folder)

    @property
    def version_name(self) -> str:
        """
        Get the release version name.

        :return: The release version string.
        :rtype: str
        """
        return self._version_name

    @property
    def version_into(self) -> Version:
        """
        Get the version as a Version object for comparison.

        :return: A parsed Version object from the version string.
        :rtype: Version
        """
        return version.parse(self._version_name)

    @property
    def download_url(self) -> str:
        """
        Get the download URL for this release version.

        URLs are constructed based on version:
        - Versions >= 6.0 are downloaded from the main release page
        - Versions 4.0 - 5.9 are downloaded from the archive
        - Versions < 4.0 are not supported

        :return: The download URL for this version.
        :rtype: str
        :raises PathError: If the version is below 4.0 (unsupported).
        """
        version_num = Version(self._version_name)
        # Versions >= 6.0 from main download page
        if version_num >= Version("6.0"):
            filename = FILENAME_RELEASE.format(version=self._version_name)
            return urljoin(BASE_URL_RELEASE, filename)
        if version_num < Version("4.0"):
            err = (
                "LanguageTool versions below 4.0 are no longer supported for download."
                " Below version 4.0, the API changed significantly and is not compatible."
            )
            raise PathError(err)
        # Versions < 6.0 from archive
        filename = FILENAME_RELEASE.format(version=self._version_name)
        return urljoin(BASE_URL_ARCHIVE, filename)


class SnapshotLocalLanguageTool(LocalLanguageTool):
    """
    Represents a snapshot (development) version of LanguageTool.

    This class handles snapshot versions of LanguageTool, which are nightly
    builds identified by date strings (e.g., '20240101') or 'latest'.

    Snapshots are the new common way of downloading LanguageTool.

    :param version_name: The snapshot version (date string or 'latest').
    :type version_name: str
    """

    def __init__(self, version_name: str) -> None:
        """
        Initialize a SnapshotLocalLanguageTool instance.
        """
        self._version_name = version_name

    def download(self) -> None:
        """
        Download and install this snapshot version of LanguageTool.

        This method checks Java compatibility, downloads the snapshot ZIP file,
        and extracts it to the download folder. For snapshots, the extracted
        directory is renamed to match the expected version name if necessary.
        """
        confirm_java_compatibility(self._version_name)

        download_folder = get_language_tool_download_path()

        # Use the env var to the jar directory if it is defined
        # otherwise look in the download directory
        if os.environ.get(LTP_JAR_DIR_PATH_ENV_VAR):
            return

        if self not in self.get_installed_versions():
            # For snapshots, pass expected_dirname to rename the extracted folder
            with (
                tempfile.TemporaryDirectory() as temp_dir,
                tempfile.NamedTemporaryFile(
                    suffix=".zip", dir=temp_dir
                ) as downloaded_file,
                self._get_remote_zip(downloaded_file) as zip_file,
            ):
                lt_dir = zip_file.infolist()[0].filename
                expected_dirname = f"LanguageTool-{self.version_name}/"
                if lt_dir != expected_dirname:
                    with (
                        tempfile.NamedTemporaryFile(
                            suffix=".zip", dir=temp_dir
                        ) as temp_file,
                        zipfile.ZipFile(temp_file, "w") as renamed_zip,
                    ):
                        for item in zip_file.infolist():
                            buffer = zip_file.read(item.filename)
                            new_name = item.filename.replace(
                                lt_dir, expected_dirname, 1
                            )
                            renamed_zip.writestr(new_name, buffer)
                        temp_file.seek(0)
                        renamed_zip.extractall(download_folder)
                else:
                    zip_file.extractall(download_folder)

    @property
    def version_name(self) -> str:
        """
        Get the snapshot version name.

        Returns the current snapshot version string if 'latest' was specified,
        otherwise returns the specified date string.

        :return: The snapshot version string.
        :rtype: str
        """
        if self._version_name == LTP_DOWNLOAD_VERSION:
            return LT_SNAPSHOT_CURRENT_VERSION
        return self._version_name

    @property
    def version_into(self) -> datetime:
        """
        Get the snapshot version as a datetime object for comparison.

        Converts the version date string to a datetime object. For 'latest',
        uses the current date.

        :return: A datetime object representing the snapshot date.
        :rtype: datetime
        """
        if self._version_name == LTP_DOWNLOAD_VERSION:
            date_str = datetime.now().strftime("%Y%m%d")
        else:
            date_str = self._version_name
        return datetime.strptime(date_str, "%Y%m%d")

    @property
    def download_url(self) -> str:
        """
        Get the download URL for this snapshot version.

        Constructs the URL to download the snapshot from the snapshot server.

        :return: The download URL for this snapshot.
        :rtype: str
        """
        filename = FILENAME_SNAPSHOT.format(version=self._version_name)
        return urljoin(BASE_URL_SNAPSHOT, filename)
