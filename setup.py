#!/usr/bin/env python3
"""Backward-compatible setup script
"""

import codecs
import glob
import os
import re
import shutil
import subprocess
import sys

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
    from ConfigParser import RawConfigParser
    from collections import MutableMapping  # 2.6

    class RawConfigParser(RawConfigParser, MutableMapping):
        """ConfigParser that does not do interpolation

        Emulate dictionary-like access.
        """
        class Section(MutableMapping):
            """A single section from a parser
            """
            def __init__(self, config, section):
                self.config = config
                self.section = section

            def __getitem__(self, option):
                if self.config.has_option(self.section, option):
                    return self.config.get(self.section, option)
                raise KeyError(option)

            def __setitem__(self, option, value):
                self.config.set(self.section, option, value)

            def __delitem__(self, option):
                self.config.remove_option(self.section, option)

            def __iter__(self):
                return iter(self.config.options(self.section))

            def __len__(self):
                return len(self.config.options(self.section))

        def __getitem__(self, section):
            if self.has_section(section):
                return RawConfigParser.Section(self, section)
            raise KeyError(section)

        def __setitem__(self, section, value):
            if self.has_section(section):
                self.remove_section(section)
            self.add_section(section)
            for key in value:
                self.set(section, key, value[key])

        def __delitem__(self, section):
            self.remove_section(section)

        def __iter__(self):
            return iter(self.sections())

        def __len__(self):
            return len(self.sections())

PY2K_DIR = os.path.join("build", "py2k")
LIB_DIR = os.path.join("build", "lib")
IS_PY2K = sys.version_info[0] < 3

BASE_ARGS_3TO2 = [
    "-w", "-n", "--no-diffs",
]

if os.name in set(["posix"]):
    try:
        from multiprocessing import cpu_count
        BASE_ARGS_3TO2 += ["-j", str(cpu_count())]
    except (ImportError, NotImplementedError):
        pass

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

# For environment markers
import platform #@UnusedImport

python_version = "%s.%s" % sys.version_info[:2]
python_full_version = sys.version.split()[0]


def which(program, win_allow_cross_arch=True):
    """Identify the location of an executable file.
    """
    def is_exe(path):
        return os.path.isfile(path) and os.access(path, os.X_OK)

    def _get_path_list():
        return os.environ["PATH"].split(os.pathsep)

    if os.name == "nt":
        def find_exe(program):
            root, ext = os.path.splitext(program)
            if ext:
                if is_exe(program):
                    return program
            else:
                for ext in os.environ["PATHEXT"].split(os.pathsep):
                    program_path = root + ext.lower()
                    if is_exe(program_path):
                        return program_path
            return None

        def get_path_list():
            paths = _get_path_list()
            if win_allow_cross_arch:
                alt_sys_path = os.path.expandvars(r"$WINDIR\Sysnative")
                if os.path.isdir(alt_sys_path):
                    paths.insert(0, alt_sys_path)
                else:
                    alt_sys_path = os.path.expandvars(r"$WINDIR\SysWOW64")
                    if os.path.isdir(alt_sys_path):
                        paths.append(alt_sys_path)
            return paths

    else:
        def find_exe(program):
            return program if is_exe(program) else None

        get_path_list = _get_path_list

    if os.path.split(program)[0]:
        program_path = find_exe(program)
        if program_path:
            return program_path
    else:
        for path in get_path_list():
            program_path = find_exe(os.path.join(path, program))
            if program_path:
                return program_path
    return None


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


def read_description_file(config):
    filenames = get_cfg_value(config, "metadata", "description-file")
    if not filenames:
        return ""
    value = []
    for filename in filenames.split():
        f = codecs.open(filename, encoding="utf-8")
        try:
            value.append(f.read())
        finally:
            f.close()
    return "\n\n".join(value).strip()


def cfg_to_args(config):
    """Compatibility helper to use setup.cfg in setup.py.
    """
    kwargs = {}
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
        if IS_PY2K and not which("3to2"):
            kwargs["setup_requires"] = ["3to2"]
        kwargs["zip_safe"] = False

    for section in opts_to_args:
        for option, argname in opts_to_args[section]:
            value = get_cfg_value(config, section, option)
            if value:
                kwargs[argname] = value

    if "long_description" not in kwargs:
        kwargs["long_description"] = read_description_file(config)

    if "package_dir" in kwargs:
        kwargs["package_dir"] = {"": kwargs["package_dir"]}

    if "keywords" in kwargs:
        kwargs["keywords"] = split_elements(kwargs["keywords"])

    if "package_data" in kwargs:
        kwargs["package_data"] = get_package_data(kwargs["package_data"])

    if "data_files" in kwargs:
        kwargs["data_files"] = get_data_files(kwargs["data_files"])

    return kwargs


def run_3to2(args=None):
    """Convert Python files using lib3to2.
    """
    args = BASE_ARGS_3TO2 if args is None else BASE_ARGS_3TO2 + args
    try:
        proc = subprocess.Popen(["3to2"] + args, stderr=subprocess.PIPE)
    except OSError:
        for path in glob.glob("*.egg"):
            if os.path.isdir(path) and not path in sys.path:
                sys.path.append(path)
        try:
            from lib3to2.main import main as lib3to2_main
        except ImportError:
            raise OSError("3to2 script is unavailable.")
        else:
            if lib3to2_main("lib3to2.fixes", args):
                raise Exception("lib3to2 parsing error")
    else:
        # HACK: workaround for 3to2 never returning non-zero
        # when using the -j option.
        num_errors = 0
        while proc.poll() is None:
            line = proc.stderr.readline()
            sys.stderr.write(line)
            num_errors += line.count(": ParseError: ")
        if proc.returncode or num_errors:
            raise Exception("lib3to2 parsing error")


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


def generate_py2k(config, py2k_dir=PY2K_DIR, run_tests=False):
    """Generate Python 2 code from Python 3 code.
    """
    def copy(src, dst):
        if (not os.path.isfile(dst) or
                os.path.getmtime(src) > os.path.getmtime(dst)):
            shutil.copy(src, dst)
            return dst
        return None

    def copy_data(src, dst):
        if (not os.path.isfile(dst) or
                os.path.getmtime(src) > os.path.getmtime(dst) or
                os.path.getsize(src) != os.path.getsize(dst)):
            shutil.copy(src, dst)
            return dst
        return None

    copied_py_files = []
    test_scripts = []

    if not os.path.isdir(py2k_dir):
        os.makedirs(py2k_dir)

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
            if copy(path, new_path):
                copied_py_files.append(new_path)

    for name in get_cfg_value(config, "files", "modules"):
        name = name.replace(".", os.path.sep) + ".py"
        py3k_path = os.path.join(packages_root, name)
        py2k_path = os.path.join(py2k_dir, py3k_path)
        dirname = os.path.dirname(py2k_path)
        if not os.path.isdir(dirname):
            os.makedirs(dirname)
        if copy(py3k_path, py2k_path):
            copied_py_files.append(py2k_path)

    for name in get_cfg_value(config, "files", "scripts"):
        py3k_path = os.path.join(packages_root, name)
        py2k_path = os.path.join(py2k_dir, py3k_path)
        dirname = os.path.dirname(py2k_path)
        if not os.path.isdir(dirname):
            os.makedirs(dirname)
        if copy(py3k_path, py2k_path):
            copied_py_files.append(py2k_path)

    setup_py_path = os.path.abspath(__file__)

    for pattern in get_cfg_value(config, "files", "extra_files"):
        for path in glob.glob(pattern):
            if os.path.abspath(path) == setup_py_path:
                continue
            py2k_path = os.path.join(py2k_dir, path)
            py2k_dirname = os.path.dirname(py2k_path)
            if not os.path.isdir(py2k_dirname):
                os.makedirs(py2k_dirname)
            filename = os.path.split(path)[1]
            ext = os.path.splitext(filename)[1].lower()
            if ext == ".py":
                if copy(path, py2k_path):
                    copied_py_files.append(py2k_path)
            else:
                copy_data(path, py2k_path)
            if (os.access(py2k_path, os.X_OK) and
                    re.search(r"\btest\b|_test\b|\btest_", filename)):
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
                copy_data(py3k_path, py2k_path)

    if copied_py_files:
        copied_py_files.sort()
        try:
            run_3to2(copied_py_files)
            write_py2k_header(copied_py_files)
        except:
            shutil.rmtree(py2k_dir)
            raise

    if run_tests:
        for script in test_scripts:
            subprocess.check_call([script])


def load_config(file="setup.cfg"):
    config = RawConfigParser()
    config.optionxform = lambda x: x.lower().replace("_", "-")
    config.read(file)
    return config


def run_setup_hooks(config):
    for hook_name in get_cfg_value(config, "global", "setup_hooks"):
        module, obj = hook_name.split(".", 1)
        if module == "setup":
            func = globals()[obj]
        else:
            module = __import__(module, globals(), locals(), [], 0)
            func = getattr(module, obj)
        func(config)


def default_hook(config):
    """Default setup hook
    """
    if (any(arg.startswith("bdist") for arg in sys.argv) and
            os.path.isdir(PY2K_DIR) != IS_PY2K and os.path.isdir(LIB_DIR)):
        shutil.rmtree(LIB_DIR)

    if IS_PY2K and any(arg.startswith("install") or
                       arg.startswith("build") or
                       arg.startswith("bdist") for arg in sys.argv):
        generate_py2k(config)
        packages_root = get_cfg_value(config, "files", "packages_root")
        packages_root = os.path.join(PY2K_DIR, packages_root)
        set_cfg_value(config, "files", "packages_root", packages_root)


def main():
    """Running with distutils or setuptools
    """
    config = load_config()
    run_setup_hooks(config)
    setup(**cfg_to_args(config))


if __name__ == "__main__":
    sys.exit(main())
