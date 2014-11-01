#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Modified version of "python -m doctest" with relaxed options."""

import doctest
import os
import sys


def main():
    testfiles = [arg for arg in sys.argv[1:] if arg and arg[0] != '-']
    if not testfiles:
        name = os.path.basename(sys.argv[0])
        if '__loader__' in globals():          # python -m
            name, _ = os.path.splitext(name)
        print('usage: {0} [-v] file ...'.format(name))
        return 2

    optionflags = doctest.ELLIPSIS | doctest.NORMALIZE_WHITESPACE

    for filename in testfiles:
        if filename.endswith('.py'):
            # It is a module -- insert its dir into sys.path and try to
            # import it. If it is part of a package, that possibly
            # won't work because of package imports.
            dirname, filename = os.path.split(filename)
            sys.path.insert(0, dirname)
            m = __import__(filename[:-3])
            del sys.path[0]
            failures, _ = doctest.testmod(m, optionflags=optionflags)
        else:
            failures, _ = doctest.testfile(filename, module_relative=False,
                                           optionflags=optionflags)
        if failures:
            return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
