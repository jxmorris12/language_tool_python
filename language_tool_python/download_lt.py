"""LanguageTool download module."""

import logging
import os
import re
import subprocess
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from shutil import which
from typing import IO, Dict, Optional, Tuple
from urllib.parse import urljoin

import requests
import tqdm
from packaging.version import Version

from .exceptions import PathError
from .utils import (
    LTP_JAR_DIR_PATH_ENV_VAR,
    find_existing_language_tool_downloads,
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
    "https://www.languagetool.org/download/",
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
    This function checks if Java is installed and verifies that the major version is at least 8 or 17 (depending on the LanguageTool version).
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
    version_date_cutoff = datetime.strptime("2025-03-27", "%Y-%m-%d")
    is_old_version = language_tool_version != "latest" and (
        (
            re.match(r"^\d+\.\d+$", language_tool_version)
            and Version(language_tool_version) < Version("6.6")
        )
        or (
            re.match(r"^\d{8}$", language_tool_version)
            and datetime.strptime(language_tool_version, "%Y%m%d") < version_date_cutoff
        )
    )

    # Some installs of java show the version number like '14.0.1'
    # and others show '1.14.0.1'
    # (with a leading 1). We want to support both.
    # (See softwareengineering.stackexchange.com/questions/175075/why-is-java-version-1-x-referred-to-as-java-x)
    if is_old_version:
        if (major_version == 1 and minor_version < 8) or (
            major_version != 1 and major_version < 8
        ):
            err = f"Detected java {major_version}.{minor_version}. LanguageTool requires Java >= 8 for version {language_tool_version}."
            raise SystemError(err)
    else:
        if (major_version == 1 and minor_version < 17) or (
            major_version != 1 and major_version < 17
        ):
            err = f"Detected java {major_version}.{minor_version}. LanguageTool requires Java >= 17 for version {language_tool_version}."
            raise SystemError(err)


def get_common_prefix(z: zipfile.ZipFile) -> Optional[str]:
    """
    Determine the common prefix of all file names in a zip archive.

    :param z: A ZipFile object representing the zip archive.
    :type z: zipfile.ZipFile
    :return: The common prefix of all file names in the zip archive, or None if there is no common prefix.
    :rtype: Optional[str]
    """

    name_list = z.namelist()
    if name_list and all(n.startswith(name_list[0]) for n in name_list[1:]):
        return name_list[0]
    return None


def http_get(
    url: str,
    out_file: IO[bytes],
    proxies: Optional[Dict[str, str]] = None,
) -> None:
    """
    Downloads a file from a given URL and writes it to the specified output file.

    :param url: The URL to download the file from.
    :type url: str
    :param out_file: The file object to write the downloaded content to.
    :type out_file: IO[bytes]
    :param proxies: Optional dictionary of proxies to use for the request.
    :type proxies: Optional[Dict[str, str]]
    :raises TimeoutError: If the request times out.
    :raises PathError: If the file could not be found at the given URL (HTTP 404).
    """
    logger.info("Starting download from %s", url)
    try:
        req = requests.get(url, stream=True, proxies=proxies, timeout=60)
    except requests.exceptions.Timeout as e:
        err = f"Request to {url} timed out."
        raise TimeoutError(err) from e
    content_length = req.headers.get("Content-Length")
    total = int(content_length) if content_length is not None else None
    if req.status_code == 404:
        err = f"Could not find at URL {url}. The given version may not exist or is no longer available."
        raise PathError(err)
    version = (
        url.split("/")[-1].split("-")[1].replace("-snapshot", "").replace(".zip", "")
    )
    progress = tqdm.tqdm(
        unit="B",
        unit_scale=True,
        total=total,
        desc=f"Downloading LanguageTool {version}",
    )
    for chunk in req.iter_content(chunk_size=1024):
        if chunk:  # filter out keep-alive new chunks
            progress.update(len(chunk))
            out_file.write(chunk)
    progress.close()


def unzip_file(temp_file_name: str, directory_to_extract_to: Path) -> None:
    """
    Unzips a zip file to a specified directory.

    :param temp_file_name: A temporary file object representing the zip file to be extracted.
    :type temp_file_name: str
    :param directory_to_extract_to: The directory where the contents of the zip file will be extracted.
    :type directory_to_extract_to: Path
    """

    logger.info("Unzipping %s to %s", temp_file_name, directory_to_extract_to)
    with zipfile.ZipFile(temp_file_name, "r") as zip_ref:
        zip_ref.extractall(directory_to_extract_to)


def download_zip(url: str, directory: Path) -> None:
    """
    Downloads a ZIP file from the given URL and extracts it to the specified directory.

    :param url: The URL of the ZIP file to download.
    :type url: str
    :param directory: The directory where the ZIP file should be extracted.
    :type directory: Path
    """
    logger.info("Downloading from %s to %s", url, directory)
    # Download file using a context manager.
    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as downloaded_file:
        http_get(url, downloaded_file)
        temp_name = downloaded_file.name
    # Extract zip file to path.
    unzip_file(temp_name, directory)
    # Remove the temporary file.
    Path(temp_name).unlink(missing_ok=True)


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
    """

    confirm_java_compatibility(language_tool_version)

    download_folder = get_language_tool_download_path()

    # Use the env var to the jar directory if it is defined
    # otherwise look in the download directory
    if os.environ.get(LTP_JAR_DIR_PATH_ENV_VAR):
        return

    if not download_folder.is_dir():
        err = f"Download folder {download_folder} is not a directory."
        raise PathError(err)
    old_path_list = find_existing_language_tool_downloads(download_folder)

    if language_tool_version:
        version = language_tool_version
        if re.match(r"^\d+\.\d+$", version):
            filename = FILENAME_RELEASE.format(version=version)
            language_tool_download_url = urljoin(BASE_URL_RELEASE, filename)
        elif version == "latest":
            filename = FILENAME_SNAPSHOT.format(version=version)
            language_tool_download_url = urljoin(BASE_URL_SNAPSHOT, filename)
        else:
            err = (
                f"You can only download a specific version of LanguageTool if it is "
                f"formatted like 'x.y' (e.g. '5.4'). The version you provided is {version}."
                f"You can also use 'latest' to download the latest snapshot of LanguageTool."
            )
            raise ValueError(err)
        dirname = Path(filename).stem
        dirname = dirname.replace("latest", LT_SNAPSHOT_CURRENT_VERSION)
        if version == "latest":
            dirname = f"LanguageTool-{LT_SNAPSHOT_CURRENT_VERSION}"
        extract_path = download_folder / dirname

        if extract_path not in old_path_list:
            download_zip(language_tool_download_url, download_folder)
