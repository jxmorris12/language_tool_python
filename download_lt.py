#!/usr/bin/env python3
"""Download latest LanguageTool-*.oxt
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


BASE_URL = "http://www.languagetool.org/download/"
PACKAGE_NAME = "language_tool"


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
    assert os.path.isdir(PACKAGE_NAME)
    old_path_list = glob.glob(os.path.join(PACKAGE_NAME, "LanguageTool*"))

    if old_path_list and not update:
        return

    contents = ""

    with closing(urlopen(BASE_URL)) as u:
        while True:
            data = u.read()
            if not data:
                break
            contents += data.decode()

    filename, version = [
        (m.group(1), Version(m.group(2))) for m in
        re.finditer(r'<a href="(LanguageTool-(\d+.*?).oxt)">', contents)
    ][-1]
    url = urljoin(BASE_URL, filename)
    dirname = os.path.splitext(filename)[0]
    extract_path = os.path.join(PACKAGE_NAME, dirname)

    if extract_path in old_path_list:
        print("No update needed: {}".format(dirname))
        return

    for old_path in old_path_list:
        match = re.search("LanguageTool-(\d+.*?)$", old_path)
        if match:
            current_version = Version(match.group(1))
            try:
                version_test = current_version > version
            except TypeError:
                continue
            if version_test:
                print(
                    "Local version: {}, Remote version: {}"
                    .format(current_version, version)
                )
                return

    with closing(TemporaryFile()) as t:
        with closing(urlopen(url)) as u:
            size = int(u.headers["Content-Length"])
            print(
                "Downloading {} ({:.1f} MiB)..."
                .format(filename, size / 1048576.)
            )
            while True:
                data = u.read()
                if not data:
                    break
                t.write(data)
        t.seek(0)
        for old_path in old_path_list:
            if os.path.isdir(old_path):
                shutil.rmtree(old_path)
        with closing(ZipFile(t)) as z:
            z.extractall(extract_path)


def setup_hook(config):
    download_lt()


if __name__ == "__main__":
    sys.exit(download_lt(True))
