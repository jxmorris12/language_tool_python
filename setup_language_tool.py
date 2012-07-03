import sys

from download_lt import download_lt


def hook(config):
    if "sdist" in sys.argv:
        del config["files"]["package_data"]
    elif any(arg.startswith("install") or
             arg.startswith("build") or
             arg.startswith("bdist") for arg in sys.argv):
        download_lt()
