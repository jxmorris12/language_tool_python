#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Download latest LanguageTool distribution."""

import glob
import os
import re
import shutil
import subprocess
import sys
import os

from contextlib import closing
from distutils.spawn import find_executable
from tempfile import TemporaryFile
from warnings import warn
from zipfile import ZipFile

try:
    from urllib.request import urlopen
    from urllib.parse import urljoin
except ImportError:
    from urllib import urlopen
    from urlparse import urljoin

ALT_BASE_URL = os.environ['language_tool_python_DOWNLOAD_HOST'] \
    if os.environ.get('language_tool_python_DOWNLOAD_HOST') \
    else None
BASE_URL = ALT_BASE_URL or 'https://www.languagetool.org/download/'
FILENAME = 'LanguageTool-{version}.zip'
PACKAGE_PATH = os.path.dirname(os.path.realpath(__file__))
LATEST_VERSION = '4.9'

JAVA_VERSION_REGEX = re.compile(
    r'^(?:java|openjdk) version "(?P<major1>\d+)\.(?P<major2>\d+)\.[^"]+"',
    re.MULTILINE)

# Updated for later versions of java
JAVA_VERSION_REGEX_UPDATED = re.compile(
    r'^(?:java|openjdk) [version ]?(?P<major1>\d+)\.(?P<major2>\d+)',
    re.MULTILINE)


def parse_java_version(version_text):
    """Return Java version (major1, major2).

    >>> parse_java_version('''java version "1.6.0_65"
    ... Java(TM) SE Runtime Environment (build 1.6.0_65-b14-462-11M4609)
    ... Java HotSpot(TM) 64-Bit Server VM (build 20.65-b04-462, mixed mode))
    ... ''')
    (1, 6)

    >>> parse_java_version('''
    ... openjdk version "1.8.0_60"
    ... OpenJDK Runtime Environment (build 1.8.0_60-b27)
    ... OpenJDK 64-Bit Server VM (build 25.60-b23, mixed mode))
    ... ''')
    (1, 8)

    """
    match = re.search(JAVA_VERSION_REGEX, version_text) or re.search(JAVA_VERSION_REGEX_UPDATED, version_text) 
    if not match:
        raise SystemExit(
            'Could not parse Java version from """{}""".'.format(version_text))
    return (int(match.group('major1')), int(match.group('major2')))

def confirm_java_compatibility():
    """ Confirms Java major version >= 8. """
    java_path = find_executable('java')
    if not java_path:
        # Just ignore this and assume an old version of Java. It might not be
        # found because of a PATHEXT-related issue
        # (https://bugs.python.org/issue2200).
        raise ModuleNotFoundError('No java install detected. Please install java to use language-tool-python.')

    output = subprocess.check_output([java_path, '-version'],
                                     stderr=subprocess.STDOUT,
                                     universal_newlines=True)

    major_version, minor_version = parse_java_version(output)
    if major_version < 8:
        raise SystemError('Detected java {}.{}. LanguageTool requires Java >= 8.'.format(major_version, minor_version))
    
    return True

def get_common_prefix(z):
    """Get common directory in a zip file if any."""
    name_list = z.namelist()
    if name_list and all(n.startswith(name_list[0]) for n in name_list[1:]):
        return name_list[0]
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

    confirm_java_compatibility()
    version = LATEST_VERSION
    filename = FILENAME.format(version=version)
    url = urljoin(BASE_URL, filename)
    dirname = os.path.splitext(filename)[0]
    extract_path = os.path.join(PACKAGE_PATH, dirname)

    if extract_path in old_path_list:
        print('No update needed: {!r}'.format(dirname))
        return

    with closing(TemporaryFile()) as t:
        with closing(urlopen(url)) as u:
            content_len = int(u.headers['Content-Length'])

            sys.stdout.write(
                'Downloading {!r} ({:.1f} MiB)...\n'.format(
                    filename,
                    content_len / 1048576.))
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
