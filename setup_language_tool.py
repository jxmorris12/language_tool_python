import sys

import setup
from download_lt import download_lt


def hook(config):
    if "sdist" in sys.argv:
        del config["files"]["package_data"]
    else:
        download_lt()
