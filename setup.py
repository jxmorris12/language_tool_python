#!/usr/bin/env python3
"""Backward-compatible setup script
"""

import glob
import os
import re
import sys
import shutil
import subprocess
import warnings

from distutils.version import LooseVersion

try:
    from setuptools import setup
    USING_SETUPTOOLS = True
except ImportError:
    from distutils.core import setup
    USING_SETUPTOOLS = False

try:
    from configparser import RawConfigParser
except ImportError:
    from ConfigParser import RawConfigParser, NoOptionError

    class RawConfigParser(RawConfigParser):
        """Dictionary access for config objects
        """
        class Section:
            def __init__(self, config, section):
                self.config = config
                self.section = section

            def __getitem__(self, option):
                try:
                    return self.config.get(self.section, option)
                except NoOptionError:
                    raise KeyError(option)

            def __setitem__(self, option, value):
                self.config.set(self.section, option, value)

        def __getitem__(self, section):
            if section not in self.sections():
                raise KeyError(section)
            return RawConfigParser.Section(self, section)

try:
    import multiprocessing
    NUM_PROCESSES = multiprocessing.cpu_count()
except (ImportError, NotImplementedError):
    NUM_PROCESSES = 1

try:
    from lib3to2.main import main as lib3to2_main

    def run_3to2(args=[]):
        return lib3to2_main("lib3to2.fixes", BASE_ARGS_3TO2 + args)
except ImportError:
    def run_3to2(args=[]):
        return subprocess.call(["3to2"] + BASE_ARGS_3TO2 + args)

# For environment markers
import platform #@UnusedImport

python_version = "%s.%s" % sys.version_info[:2]
python_full_version = sys.version.split()[0]

PY2K_DIR = os.path.join("build", "py2k")
BASE_ARGS_3TO2 = [
    "-w", "-n", "--no-diffs",
    "-j", str(NUM_PROCESSES),
]

MULTI_OPTIONS = set([
    ("global", "commands"),
    ("global", "compilers"),
    ("global", "setup_hooks"),
    ("metadata", "platform"),
    ("metadata", "supported-platform"),
    ("metadata", "classifier"),
    ("metadata", "requires-dist"),
    ("metadata", "provides-dist"),
    ("metadata", "obsoletes-dist"),
    ("metadata", "requires-external"),
    ("metadata", "project-url"),
    ("files", "packages"),
    ("files", "modules"),
    ("files", "scripts"),
    ("files", "package_data"),
    ("files", "data_files"),
    ("files", "extra_files"),
    ("files", "resources"),
])

ENVIRON_OPTIONS = set([
    ("metadata", "classifier"),
    ("metadata", "requires-dist"),
    ("metadata", "provides-dist"),
    ("metadata", "obsoletes-dist"),
    ("metadata", "requires-python"),
    ("metadata", "requires-external"),
])


def split_multiline(value):
    """Split a multiline string into a list, excluding blank lines.
    """
    return [element for element in (line.strip() for line in value.split("\n"))
            if element]


def split_elements(value):
    """Split a string with comma or space-separated elements into a list.
    """
    l = [v.strip() for v in value.split(",")]
    if len(l) == 1:
        l = value.split()
    return l


def eval_environ(value):
    """Evaluate environment markers.
    """
    def eval_environ_str(value):
        parts = value.split(";")
        if len(parts) < 2:
            return value
        expr = parts[1].lstrip()
        if not re.match("^((\\w+(\\.\\w+)?|'.*?'|\".*?\")\\s+"
                        "(in|==|!=|not in)\\s+"
                        "(\\w+(\\.\\w+)?|'.*?'|\".*?\")"
                        "(\s+(or|and)\s+)?)+$", expr):
            raise ValueError("bad environment marker: %r" % expr)
        expr = re.sub(r"(platform\.\w+)", r"\1()", expr)
        return parts[0] if eval(expr) else ""

    if isinstance(value, list):
        new_value = []
        for element in value:
            element = eval_environ_str(element)
            if element:
                new_value.append(element)
    elif isinstance(value, str):
        new_value = eval_environ_str(value)
    else:
        new_value = value

    return new_value


def get_cfg_value(config, section, option):
    """Get configuration value.
    """
    try:
        value = config[section][option]
    except KeyError:
        if (section, option) in MULTI_OPTIONS:
            return []
        else:
            return ""
    if (section, option) in MULTI_OPTIONS:
        value = split_multiline(value)
    if (section, option) in ENVIRON_OPTIONS:
        value = eval_environ(value)
    return value


def set_cfg_value(config, section, option, value):
    """Set configuration value.
    """
    if isinstance(value, list):
        value = "\n".join(value)
    config[section][option] = value


def get_package_data(value):
    package_data = {}
    firstline = True
    prev = None
    for line in value:
        if "=" in line:
            # package name -- file globs or specs
            key, value = line.split("=")
            prev = package_data[key.strip()] = value.split()
        elif firstline:
            # invalid continuation on the first line
            raise ValueError(
                'malformed package_data first line: %r (misses "=")' %
                line)
        else:
            # continuation, add to last seen package name
            prev.extend(line.split())
        firstline = False
    return package_data


def get_data_files(value):
    data_files = []
    for data in value:
        data = data.split("=")
        if len(data) != 2:
            continue
        key, value = data
        values = [v.strip() for v in value.split(",")]
        data_files.append((key, values))
    return data_files


def cfg_to_args(config):
    """Compatibility helper to use setup.cfg in setup.py.
    """
    opts_to_args = {
        "metadata": [
            ("name", "name"),
            ("version", "version"),
            ("author", "author"),
            ("author-email", "author_email"),
            ("maintainer", "maintainer"),
            ("maintainer-email", "maintainer_email"),
            ("home-page", "url"),
            ("summary", "description"),
            ("description", "long_description"),
            ("download-url", "download_url"),
            ("classifier", "classifiers"),
            ("platform", "platforms"),
            ("license", "license"),
            ("keywords", "keywords"),
        ],
        "files": [
            ("packages_root", "package_dir"),
            ("packages", "packages"),
            ("modules", "py_modules"),
            ("scripts", "scripts"),
            ("package_data", "package_data"),
            ("data_files", "data_files"),
        ],
    }

    if USING_SETUPTOOLS:
        opts_to_args["metadata"].append(("requires-dist", "install_requires"))

    kwargs = {}

    for section in opts_to_args:
        for option, argname in opts_to_args[section]:
            value = get_cfg_value(config, section, option)
            if value:
                kwargs[argname] = value

    if "long_description" not in kwargs:
        filenames = get_cfg_value(config, "metadata", "description-file")
        if filenames:
            value = []
            for filename in filenames.split():
                fp = open(filename)
                try:
                    value.append(fp.read())
                finally:
                    fp.close()
            kwargs["long_description"] = "\n\n".join(value)

    if "package_dir" in kwargs:
        kwargs["package_dir"] = {"": kwargs["package_dir"]}

    if "keywords" in kwargs:
        kwargs["keywords"] = split_elements(kwargs["keywords"])

    if "package_data" in kwargs:
        kwargs["package_data"] = get_package_data(kwargs["package_data"])

    if "data_files" in kwargs:
        kwargs["data_files"] = get_data_files(kwargs["data_files"])

    return kwargs


def write_py2k_header(file_list):
    """Write Python 2 shebang and add encoding cookie if needed.
    """
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
                    try:
                        version_test = version >= version_3
                    except TypeError:
                        version_test = True
                    if version_test:
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
                lines += f.readlines()
        finally:
            f.close()

        if rewrite_needed:
            f = open(file, "wb")
            try:
                f.writelines(lines)
            finally:
                f.close()


def generate_py2k(config, py2k_dir=PY2K_DIR, overwrite=False, run_tests=False):
    """Generate Python 2 code from Python 3 code.
    """
    if os.path.isdir(py2k_dir):
        if not overwrite:
            return
    else:
        os.makedirs(py2k_dir)

    file_list = []
    test_scripts = []

    packages_root = get_cfg_value(config, "files", "packages_root")

    for name in get_cfg_value(config, "files", "packages"):
        name = name.replace(".", os.path.sep)
        py3k_path = os.path.join(packages_root, name)
        py2k_path = os.path.join(py2k_dir, py3k_path)
        if not os.path.isdir(py2k_path):
            os.makedirs(py2k_path)
        for fn in os.listdir(py3k_path):
            path = os.path.join(py3k_path, fn)
            if not os.path.isfile(path):
                continue
            if not os.path.splitext(path)[1].lower() == ".py":
                continue
            new_path = os.path.join(py2k_path, fn)
            shutil.copy(path, new_path)
            file_list.append(new_path)

    for name in get_cfg_value(config, "files", "modules"):
        name = name.replace(".", os.path.sep) + ".py"
        py3k_path = os.path.join(packages_root, name)
        py2k_path = os.path.join(py2k_dir, py3k_path)
        dirname = os.path.dirname(py2k_path)
        if not os.path.isdir(dirname):
            os.makedirs(dirname)
        shutil.copy(py3k_path, py2k_path)
        file_list.append(py2k_path)

    for name in get_cfg_value(config, "files", "scripts"):
        py3k_path = os.path.join(packages_root, name)
        py2k_path = os.path.join(py2k_dir, py3k_path)
        dirname = os.path.dirname(py2k_path)
        if not os.path.isdir(dirname):
            os.makedirs(dirname)
        shutil.copy(py3k_path, py2k_path)
        file_list.append(py2k_path)

    setup_py_path = os.path.abspath(__file__)

    for pattern in get_cfg_value(config, "files", "extra_files"):
        for path in glob.glob(pattern):
            if os.path.abspath(path) == setup_py_path:
                continue
            py2k_path = os.path.join(py2k_dir, path)
            py2k_dirname = os.path.dirname(py2k_path)
            if not os.path.isdir(py2k_dirname):
                os.makedirs(py2k_dirname)
            shutil.copy(path, py2k_path)
            filename = os.path.split(path)[1]
            ext = os.path.splitext(filename)[1].lower()
            if ext == ".py":
                file_list.append(py2k_path)
            if (os.access(py2k_path, os.X_OK) and
                re.search(r"\btest\b|_test\b|\btest_", filename)
            ):
                test_scripts.append(py2k_path)

    for package, patterns in get_package_data(
            get_cfg_value(config, "files", "package_data")).items():
        for pattern in patterns:
            py3k_pattern = os.path.join(packages_root, package, pattern)
            for py3k_path in glob.glob(py3k_pattern):
                py2k_path = os.path.join(py2k_dir, py3k_path)
                py2k_dirname = os.path.dirname(py2k_path)
                if not os.path.isdir(py2k_dirname):
                    os.makedirs(py2k_dirname)
                shutil.copy(py3k_path, py2k_path)

    run_3to2(file_list)
    write_py2k_header(file_list)

    if run_tests:
        for script in test_scripts:
            subprocess.check_call([script])


def hook(config):
    """Setup hook
    """
    if sys.version_info.major < 3:
        generate_py2k(config)
        packages_root = get_cfg_value(config, "files", "packages_root")
        packages_root = os.path.join(PY2K_DIR, packages_root)
        set_cfg_value(config, "files", "packages_root", packages_root)


def load_config(file="setup.cfg"):
    config = RawConfigParser()
    config.optionxform = lambda x: x.lower().replace("_", "-")
    config.read(file)

    for hook_name in get_cfg_value(config, "global", "setup_hooks"):
        try:
            if hook_name == "setup.hook":
                func = hook
            else:
                module, obj = hook_name.split(".", 1)
                module = __import__(module, globals(), locals(), [], 0)
                func = getattr(module, obj)
            func(config)
        except Exception as e:
            warnings.warn("%s: %s" % (hook_name, e))

    return config


def main():
    """Running with distutils or setuptools
    """
    config = load_config()
    setup(**cfg_to_args(config))


if __name__ == "__main__":
    sys.exit(main())
