#!/usr/bin/env python3

import sys
import _3to2


ADDITIONAL_FILES = [
    "language_tool/LanguageTool-*/",
]

_3to2.__dict__.update(locals())


if __name__ == "__main__":
    sys.exit(_3to2.main())
