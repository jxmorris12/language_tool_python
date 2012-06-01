#!/usr/bin/env python3
"""Convert Python 3 source into Python 2 source, using lib3to2
"""
import codecs
import glob
import re
import os
import shutil
import subprocess
import sys
from distutils.version import LooseVersion
try:
    from configparser import RawConfigParser
except ImportError:
    from ConfigParser import RawConfigParser
try:
    import multiprocessing
    cpu_count = multiprocessing.cpu_count()
except (ImportError, NotImplementedError):
    cpu_count = 1

from lib3to2.main import main as lib3to2_main

# For environment markers
import platform #@UnusedImport
import os #@UnusedImport
import sys

python_version = "%s.%s" % sys.version_info[:2]
python_full_version = sys.version.split()[0]


ADDITIONAL_FILES = []
PY2_DIR = "py2"
SETUP_PY = "setup.py"
SETUP_CFG = "setup.cfg"


MULTI_OPTIONS = set([("global", "commands"),
                     ("global", "compilers"),
                     ("global", "setup_hooks"),
                     ("metadata", "platform"),
                     ("metadata", "supported_platform"),
                     ("metadata", "classifiers"),
                     ("metadata", "requires_dist"),
                     ("metadata", "provides_dist"),
                     ("metadata", "obsoletes_dist"),
                     ("metadata", "requires_external"),
                     ("metadata", "project_url"),
                     ("files", "packages"),
                     ("files", "modules"),
                     ("files", "scripts"),
                     ("files", "extra_files")])

ENVIRON_OPTIONS = set([("metadata", "classifier"),
                       ("metadata", "requires_dist"),
                       ("metadata", "provides_dist"),
                       ("metadata", "obsoletes_dist"),
                       ("metadata", "requires_python"),
                       ("metadata", "requires_external")])


def has_get_option(config, section, option):
    if config.has_option(section, option):
        return config.get(section, option)
    elif config.has_option(section, option.replace('_', '-')):
        return config.get(section, option.replace('_', '-'))
    else:
        return False


def split_multiline(value):
    """Split a multiline string into a list, excluding blank lines."""

    return [element for element in
            (line.strip() for line in value.split('\n'))
            if element]


def eval_environ(value):
    """"Evaluate environment markers."""

    def eval_environ_str(value):
        parts = value.split(";")
        if len(parts) < 2:
            new_value = parts[0]
        else:
            expr = parts[1].lstrip()
            if not re.match("^((\\w+(\\.\\w+)?|'.*?'|\".*?\")\\s+"
                            "(in|==|!=|not in)\\s+"
                            "(\\w+(\\.\\w+)?|'.*?'|\".*?\")"
                            "(\s+(or|and)\s+)?)+$", expr):
                raise ValueError("bad environment marker: %r" % (expr,))
            expr = re.sub(r"(platform.\w+)", r"\1()", expr)
            new_value = parts[0] if eval(expr) else None
        return new_value

    if isinstance(value, list):
        new_value = []
        for element in value:
            element = eval_environ_str(element)
            if element is not None:
                new_value.append(element)
    elif isinstance(value, str):
        new_value = eval_environ_str(value)
    else:
        new_value = value

    return new_value


def get_cfg_value(config, section, option):
    value = has_get_option(config, section, option)
    if value:
        if (section, option) in MULTI_OPTIONS:
            value = split_multiline(value)
        if (section, option) in ENVIRON_OPTIONS:
            value = eval_environ(value)
        return value
    if (section, option) in MULTI_OPTIONS:
        return []
    else:
        return None


def rewrite_header(file_list):
    if not isinstance(file_list, list):
        file_list = [file_list]

    python_re = re.compile(br"^(#!.*\bpython)(.*)([\r\n]+)$")
    coding_re = re.compile(br"coding[:=]\s*([-\w.]+)")
    new_line_re = re.compile(br"([\r\n]+)$")
    version_3 = LooseVersion("3")

    for file in file_list:
        if not os.path.getsize(file):
            continue

        rewrite_needed = False
        python_found = False
        coding_found = False
        lines = []

        f = open(file, "rb")
        try:
            while len(lines) < 2:
                line = f.readline()
                match = python_re.match(line)
                if match:
                    python_found = True
                    version = LooseVersion(match.group(2).decode() or "2")
                    if version >= version_3:
                        line = python_re.sub(br"\g<1>2\g<3>", line)
                        rewrite_needed = True
                elif coding_re.search(line):
                    coding_found = True
                lines.append(line)
            if not coding_found:
                match = new_line_re.search(lines[0])
                newline = match.group(1) if match else b"\n"
                line = b"# -*- coding: utf-8 -*-" + newline
                lines.insert(1 if python_found else 0, line)
                rewrite_needed = True
            if rewrite_needed:
                lines.extend(f.readlines())
        finally:
            f.close()

        if rewrite_needed:
            f = open(file, "wb")
            try:
                f.writelines(lines)
            finally:
                f.close()


def main():
    if not os.path.isdir(PY2_DIR):
        os.makedirs(PY2_DIR)
    else:
        for name in os.listdir(PY2_DIR):
            path = os.path.join(PY2_DIR, name)
            if os.path.isfile(path):
                os.remove(path)
            else:
                shutil.rmtree(path)

    config = RawConfigParser()
    f = codecs.open(SETUP_CFG, encoding="utf-8")
    try:
        config.readfp(f)
    finally:
        f.close()

    packages_root = get_cfg_value(config, "files", "packages_root")
    if not packages_root:
        packages_root = ""
    packages = get_cfg_value(config, "files", "packages")
    modules = get_cfg_value(config, "files", "modules")
    scripts = get_cfg_value(config, "files", "scripts")
    file_list = []
    test_scripts = []

    for name in packages:
        name = name.replace(".", os.path.sep)
        py3_path = os.path.join(packages_root, name)
        py2_path = os.path.join(PY2_DIR, py3_path)
        if not os.path.isdir(py2_path):
            os.makedirs(py2_path)
        for fn in os.listdir(py3_path):
            path = os.path.join(py3_path, fn)
            if not os.path.isfile(path):
                continue
            if not os.path.splitext(path)[1].lower() == ".py":
                continue
            new_path = os.path.join(py2_path, fn)
            shutil.copy(path, new_path)
            file_list.append(new_path)

    for name in modules:
        name = name.replace(".", os.path.sep) + ".py"
        py3_path = os.path.join(packages_root, name)
        py2_path = os.path.join(PY2_DIR, py3_path)
        dirname = os.path.dirname(py2_path)
        if not os.path.isdir(dirname):
            os.makedirs(dirname)
        shutil.copy(py3_path, py2_path)
        file_list.append(py2_path)

    for name in scripts:
        py3_path = os.path.join(packages_root, name)
        py2_path = os.path.join(PY2_DIR, py3_path)
        dirname = os.path.dirname(py2_path)
        if not os.path.isdir(dirname):
            os.makedirs(dirname)
        shutil.copy(py3_path, py2_path)
        file_list.append(py2_path)

    for path in glob.glob("*test*"):
        dir_path, name = os.path.split(path)
        if not re.search(r"\btest\b|_test\b|\btest_", name):
            continue
        py2_path = os.path.join(PY2_DIR, path)
        if os.path.isfile(path):
            shutil.copy(path, py2_path)
            file_list.append(py2_path)
            if os.path.splitext(name)[1].lower() == ".py":
                test_scripts.append(py2_path)
        else:
            shutil.copytree(path, py2_path)

    lib3to2_main("lib3to2.fixes",
                 ["--no-diffs", "-wnj", str(cpu_count)] + file_list)

    rewrite_header(file_list)

    py2_path = os.path.join(PY2_DIR, SETUP_PY)
    shutil.copy(SETUP_PY, py2_path)

    config.set("metadata", "name", config.get("metadata", "name") + "-py2")
    f = codecs.open(os.path.join(PY2_DIR, SETUP_CFG), "w", encoding="utf-8")
    try:
        config.write(f)
    finally:
        f.close()

    for pattern in ADDITIONAL_FILES:
        for path in glob.glob(pattern):
            for dirpath, dirnames, filenames in os.walk(path):
                for dirname in dirnames:
                    path = os.path.join(dirpath, dirname)
                    py2_path = os.path.join(PY2_DIR, path)
                    os.makedirs(py2_path)
                for filename in filenames:
                    path = os.path.join(dirpath, filename)
                    py2_path = os.path.join(PY2_DIR, path)
                    shutil.copy(path, py2_path)

    for script in test_scripts:
        subprocess.check_call([script])


if __name__ == "__main__":
    sys.exit(main())
