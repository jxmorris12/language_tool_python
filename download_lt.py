#!/usr/bin/env python3
"""Download latest LanguageTool distribution
"""

import glob
import os
import re
import shutil
import sys

from contextlib import closing
from tempfile import TemporaryFile
from zipfile import ZipFile

try:
    from urllib.request import urlopen
    from urllib.parse import urljoin
except ImportError:
    from urllib import urlopen
    from urlparse import urljoin

try:
    from packaging.version import NormalizedVersion, suggest_normalized_version
except ImportError:
    try:
        from distutils2.version import (
            NormalizedVersion, suggest_normalized_version)
    except ImportError:
        from distutils.version import LooseVersion
        NormalizedVersion = None

import language_tool


BASE_URL = "http://www.languagetool.org/download/"
PACKAGE_PATH = "language_tool"


if NormalizedVersion:
    class Version(NormalizedVersion):
        def __init__(self, version):
            self.unnormalized_version = version
            NormalizedVersion.__init__(
                self, suggest_normalized_version(version))

        def __repr__(self):
            return "{}({!r})".format(
                self.__class__.__name__, self.unnormalized_version)

        def __str__(self):
            return self.unnormalized_version
else:
    class Version(LooseVersion):
        pass


def download_lt(update=False):
    """Download and extract LanguageTool distribution into package directory.
    """
    assert os.path.isdir(PACKAGE_PATH)
    try:
        lt_dir = language_tool.get_language_tool_dir()
    except language_tool.Error:
        lt_dir = None

    if lt_dir and not update:
        return

    contents = ""

    with closing(urlopen(BASE_URL)) as u:
        while True:
            data = u.read()
            if not data:
                break
            contents += data.decode()

    href_format = r'<a href="(LanguageTool-(\d+.*?)\.{})">'

    matches = [
        (m.group(1), Version(m.group(2))) for m in
        re.finditer(href_format.format("zip"), contents)
    ]

    if not matches:
        matches = [
            (m.group(1), Version(m.group(2))) for m in
            re.finditer(href_format.format("oxt"), contents)
        ]

    filename, version = matches[-1]

    if lt_dir:
        try:
            installed_version = Version(language_tool.get_version())
            update_needed = installed_version < version
        except TypeError:
            update_needed = True
    else:
        update_needed = True

    if not update_needed:
        print("No update needed: {!s}".format(installed_version))
        return

    url = urljoin(BASE_URL, filename)
    dirname = os.path.splitext(filename)[0]
    extract_path = os.path.join(PACKAGE_PATH, dirname)

    with closing(TemporaryFile()) as t:
        with closing(urlopen(url)) as u:
            content_len = int(u.headers["Content-Length"])
            sys.stdout.write(
                "Downloading {!r} ({:.1f} MiB)...\n"
                .format(filename, content_len / 1048576.)
            )
            sys.stdout.flush()
            chunk_len = content_len // 100
            data_len = 0
            while True:
                data = u.read(chunk_len)
                if not data:
                    break
                data_len += len(data)
                t.write(data)
                sys.stdout.write(
                    "\r{:.0%}".format(float(data_len) / content_len))
                sys.stdout.flush()
            sys.stdout.write("\n")
        t.seek(0)

        if lt_dir and os.path.isdir(lt_dir):
            shutil.rmtree(lt_dir)

        with closing(ZipFile(t)) as z:
            z.extractall(extract_path)


if __name__ == "__main__":
    sys.exit(download_lt(update="--no-update" not in sys.argv))
