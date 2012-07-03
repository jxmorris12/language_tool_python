#!/usr/bin/env python3
"""Cross-platform which command
"""
#   © 2012 spirit <hiddenspirit@gmail.com>
#
#   This program is free software: you can redistribute it and/or modify it
#   under the terms of the GNU Lesser General Public License as published
#   by the Free Software Foundation, either version 3 of the License,
#   or (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty
#   of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
#   See the GNU Lesser General Public License for more details.
#
#   You should have received a copy of the GNU Lesser General Public License
#   along with this program. If not, see <http://www.gnu.org/licenses/>.

import os


__all__ = ["which"]

WIN_ALLOW_CROSS_ARCH = True


def which(program):
    """Identify the location of an executable file.
    """
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
        if WIN_ALLOW_CROSS_ARCH:
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


def main():
    for arg in sys.argv[1:]:
        path = which(arg)
        if path:
            print(path)


if __name__ == "__main__":
    import sys
    sys.exit(main())
