#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Download latest LanguageTool distribution."""

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


BASE_URL = 'http://www.languagetool.org/download/'
FILENAME = 'LanguageTool-2.2.zip'
PACKAGE_PATH = 'language_check'


if NormalizedVersion:
    class Version(NormalizedVersion):

        def __init__(self, version):
            self.unnormalized_version = version
            NormalizedVersion.__init__(
                self, suggest_normalized_version(version))

        def __repr__(self):
            return '{}({!r})'.format(
                self.__class__.__name__, self.unnormalized_version)

        def __str__(self):
            return self.unnormalized_version
else:
    class Version(LooseVersion):
        pass


def get_common_prefix(z):
    """Get common directory in a zip file if any."""
    l = z.namelist()
    if l and all(n.startswith(l[0]) for n in l[1:]):
        return l[0]
    return None


def download_lt(update=False):
    assert os.path.isdir(PACKAGE_PATH)
    old_path_list = [
        path for path in
        glob.glob(os.path.join(PACKAGE_PATH, 'LanguageTool*'))
        if os.path.isdir(path)
    ]

    if old_path_list and not update:
        return

    url = urljoin(BASE_URL, FILENAME)
    dirname = os.path.splitext(FILENAME)[0]
    extract_path = os.path.join(PACKAGE_PATH, dirname)

    if extract_path in old_path_list:
        print('No update needed: {!r}'.format(dirname))
        return

    with closing(TemporaryFile()) as t:
        with closing(urlopen(url)) as u:
            content_len = int(u.headers['Content-Length'])
            sys.stdout.write(
                'Downloading {!r} ({:.1f} MiB)...\n'
                .format(FILENAME, content_len / 1048576.)
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
                    '\r{:.0%}'.format(float(data_len) / content_len))
                sys.stdout.flush()
            sys.stdout.write('\n')
        t.seek(0)
        for old_path in old_path_list:
            if os.path.isdir(old_path):
                shutil.rmtree(old_path)
        with closing(ZipFile(t)) as z:
            prefix = get_common_prefix(z)
            if prefix:
                z.extractall(PACKAGE_PATH)
                os.rename(os.path.join(PACKAGE_PATH, prefix),
                          os.path.join(PACKAGE_PATH, dirname))
            else:
                z.extractall(extract_path)


if __name__ == '__main__':
    sys.exit(download_lt(update=True))
