"""LanguageTool download module."""

import logging
import os
import re
import requests
import subprocess
import tempfile
import tqdm
from typing import IO, Dict, Optional, Tuple
import zipfile
from datetime import datetime

from shutil import which
from urllib.parse import urljoin
from .utils import (
    find_existing_language_tool_downloads,
    get_language_tool_download_path,
    PathError,
    LTP_JAR_DIR_PATH_ENV_VAR
)

# Create logger for this file.
logging.basicConfig(format='%(message)s')
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


# Get download host from environment or default.
BASE_URL_SNAPSHOT = os.environ.get('LTP_DOWNLOAD_HOST_SNAPSHOT', 'https://internal1.languagetool.org/snapshots/')
FILENAME_SNAPSHOT = 'LanguageTool-{version}-snapshot.zip'
BASE_URL_RELEASE = os.environ.get('LTP_DOWNLOAD_HOST_RELEASE', 'https://www.languagetool.org/download/')
FILENAME_RELEASE = 'LanguageTool-{version}.zip'

LTP_DOWNLOAD_VERSION = 'latest'
LT_SNAPSHOT_CURRENT_VERSION = '6.7-SNAPSHOT'

JAVA_VERSION_REGEX = re.compile(
    r'^(?:java|openjdk) version "(?P<major1>\d+)(|\.(?P<major2>\d+)\.[^"]+)"',
    re.MULTILINE)

# Updated for later versions of java
JAVA_VERSION_REGEX_UPDATED = re.compile(
    r'^(?:java|openjdk) [version ]?(?P<major1>\d+)\.(?P<major2>\d+)',
    re.MULTILINE)

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
    match = (
        re.search(JAVA_VERSION_REGEX, version_text)
        or re.search(JAVA_VERSION_REGEX_UPDATED, version_text)
    )
    if not match:
        raise SystemExit(f'Could not parse Java version from """{version_text}""".')
    major1 = int(match.group('major1'))
    major2 = int(match.group('major2')) if match.group('major2') else 0
    return (major1, major2)


def confirm_java_compatibility(language_tool_version: Optional[str] = LTP_DOWNLOAD_VERSION) -> None:
    """
    Confirms if the installed Java version is compatible with language-tool-python.
    This function checks if Java is installed and verifies that the major version is at least 8 or 17 (depending on the LanguageTool version).
    It raises an error if Java is not installed or if the version is incompatible.

    :param language_tool_version: The version of LanguageTool to check compatibility for.
    :type language_tool_version: Optional[str]
    :raises ModuleNotFoundError: If no Java installation is detected.
    :raises SystemError: If the detected Java version is less than the required version.
    """

    java_path = which('java')
    if not java_path:
        raise ModuleNotFoundError(
            'No java install detected. '
            'Please install java to use language-tool-python.'
        )

    output = subprocess.check_output([java_path, '-version'],
                                     stderr=subprocess.STDOUT,
                                     universal_newlines=True)

    major_version, minor_version = parse_java_version(output)
    version_date_cutoff = datetime.strptime('2025-03-27', '%Y-%m-%d')
    is_old_version = (
        language_tool_version != 'latest' and (
            (re.match(r'^\d+\.\d+$', language_tool_version) and language_tool_version < '6.6') or 
            (re.match(r'^\d{8}$', language_tool_version) and datetime.strptime(language_tool_version, '%Y%m%d') < version_date_cutoff)
        )
    )

    # Some installs of java show the version number like `14.0.1`
    # and others show `1.14.0.1`
    # (with a leading 1). We want to support both.
    # (See softwareengineering.stackexchange.com/questions/175075/why-is-java-version-1-x-referred-to-as-java-x)
    if is_old_version:
        if (major_version == 1 and minor_version < 8) or (major_version != 1 and major_version < 8):
            raise SystemError(f'Detected java {major_version}.{minor_version}. LanguageTool requires Java >= 8 for version {language_tool_version}.')
    else:
        if (major_version == 1 and minor_version < 17) or (major_version != 1 and major_version < 17):
            raise SystemError(f'Detected java {major_version}.{minor_version}. LanguageTool requires Java >= 17 for version {language_tool_version}.')


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


def http_get(url: str, out_file: IO[bytes], proxies: Optional[Dict[str, str]] = None) -> None:
    """
    Downloads a file from a given URL and writes it to the specified output file.

    :param url: The URL to download the file from.
    :type url: str
    :param out_file: The file object to write the downloaded content to.
    :type out_file: IO[bytes]
    :param proxies: Optional dictionary of proxies to use for the request.
    :type proxies: Optional[Dict[str, str]]
    :raises PathError: If the file could not be found at the given URL (HTTP 404).
    """
    req = requests.get(url, stream=True, proxies=proxies)
    content_length = req.headers.get('Content-Length')
    total = int(content_length) if content_length is not None else None
    if req.status_code == 404:
        raise PathError(f'Could not find at URL {url}. The given version may not exist or is no longer available.')
    version = url.split('/')[-1].split('-')[1].replace('-snapshot', '').replace('.zip', '')
    progress = tqdm.tqdm(unit="B", unit_scale=True, total=total,
                         desc=f'Downloading LanguageTool {version}')
    for chunk in req.iter_content(chunk_size=1024):
        if chunk:  # filter out keep-alive new chunks
            progress.update(len(chunk))
            out_file.write(chunk)
    progress.close()


def unzip_file(temp_file_name: str, directory_to_extract_to: str) -> None:
    """
    Unzips a zip file to a specified directory.

    :param temp_file_name: A temporary file object representing the zip file to be extracted.
    :type temp_file_name: str
    :param directory_to_extract_to: The directory where the contents of the zip file will be extracted.
    :type directory_to_extract_to: str
    """
    
    logger.info(f'Unzipping {temp_file_name} to {directory_to_extract_to}.')
    with zipfile.ZipFile(temp_file_name, 'r') as zip_ref:
        zip_ref.extractall(directory_to_extract_to)


def download_zip(url: str, directory: str) -> None:
    """
    Downloads a ZIP file from the given URL and extracts it to the specified directory.

    :param url: The URL of the ZIP file to download.
    :type url: str
    :param directory: The directory where the ZIP file should be extracted.
    :type directory: str
    """
    # Download file.
    downloaded_file = tempfile.NamedTemporaryFile(suffix='.zip', delete=False)
    http_get(url, downloaded_file)
    # Close the file so we can extract it.
    downloaded_file.close()
    # Extract zip file to path.
    unzip_file(downloaded_file.name, directory)
    # Remove the temporary file.
    os.remove(downloaded_file.name)
    # Tell the user the download path.
    logger.info(f'Downloaded {url} to {directory}.')


def download_lt(language_tool_version: Optional[str] = LTP_DOWNLOAD_VERSION) -> None:
    """
    Downloads and extracts the specified version of LanguageTool.
    This function checks for Java compatibility, creates the necessary download
    directory if it does not exist, and downloads the specified version of
    LanguageTool if it is not already present.

    :param language_tool_version: The version of LanguageTool to download. If not
                                  specified, the default version defined by
                                  LTP_DOWNLOAD_VERSION is used.
    :type language_tool_version: Optional[str]
    :raises AssertionError: If the download folder is not a directory.
    :raises ValueError: If the specified version format is invalid.
    """

    confirm_java_compatibility(language_tool_version)

    download_folder = get_language_tool_download_path()

    # Use the env var to the jar directory if it is defined
    # otherwise look in the download directory
    if os.environ.get(LTP_JAR_DIR_PATH_ENV_VAR):
        return

    # Make download path, if it doesn't exist.
    os.makedirs(download_folder, exist_ok=True)

    assert os.path.isdir(download_folder)
    old_path_list = find_existing_language_tool_downloads(download_folder)

    if language_tool_version:
        version = language_tool_version
        if re.match(r'^\d+\.\d+$', version):
            filename = FILENAME_RELEASE.format(version=version)
            language_tool_download_url = urljoin(BASE_URL_RELEASE, filename)
        elif version == "latest":
            filename = FILENAME_SNAPSHOT.format(version=version)
            language_tool_download_url = urljoin(BASE_URL_SNAPSHOT, filename)
        else:
            raise ValueError(
                f"You can only download a specific version of LanguageTool if it is "
                f"formatted like 'x.y' (e.g. '5.4'). The version you provided is {version}."
                f"You can also use 'latest' to download the latest snapshot of LanguageTool."
            )
        dirname, _ = os.path.splitext(filename)
        dirname = dirname.replace('latest', LT_SNAPSHOT_CURRENT_VERSION)
        if version == "latest":
            dirname = f"LanguageTool-{LT_SNAPSHOT_CURRENT_VERSION}"
        extract_path = os.path.join(download_folder, dirname)

        if extract_path not in old_path_list:
            download_zip(language_tool_download_url, download_folder)
