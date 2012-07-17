"""LanguageTool command line
"""

import argparse
import os
import sys

import language_tool

DEFAULT_ENCODING = "utf-8"


def parse_args():
    parser = argparse.ArgumentParser(
        description=__doc__.strip(),
        prog="{} -m {}".format(os.path.basename(sys.executable),
                               "language_tool")
    )
    parser.add_argument("file", nargs="?", help="plain text file")
    parser.add_argument("--encoding", dest="encoding", help="input encoding")
    parser.add_argument("--language", dest="language",
                        help='language code of the input or "auto"')
    parser.add_argument("--mothertongue", dest="motherTongue",
                        help="language code of your first language")
    parser.add_argument("--disable", dest="disable",
                        help="comma-separated list of rule IDs to be disabled")
    parser.add_argument("--enable", dest="enable",
                        help="comma-separated list of rule IDs to be enabled")
    parser.add_argument("--version", dest="version", action="store_true",
                        help="print LanguageTool version number")
    parser.add_argument("--apply", dest="apply", action="store_true",
                        help="automatically apply suggestions if available")
    return parser.parse_args()


def get_rules(rules: str) -> set:
    return {rule.strip() for rule in rules.split(",")}


def main():
    args = parse_args()

    if args.version:
        print("LanguageTool {}".format(language_tool.get_version()))
        return

    if args.file:
        file = args.file
        encoding = args.encoding if args.encoding else DEFAULT_ENCODING
    else:
        file = sys.stdin.fileno()
        encoding = args.encoding if args.encoding else sys.stdin.encoding

    with open(file, encoding=encoding) as f:
        text = "\n".join(f.readlines())

    language = args.language

    if language and language.lower() == "auto":
        try:
            from guess_language import guess_language
        except ImportError:
            print("guess_language is unavailable.", file=sys.stderr)
            language = None
        else:
            language = guess_language(text)
            print("Language detected as: {!r}".format(language), file=sys.stderr)

    lang_tool = language_tool.LanguageTool(language, args.motherTongue)

    if args.disable is not None:
        lang_tool.disable(get_rules(args.disable))
    if args.enable is not None:
        lang_tool.enable(get_rules(args.enable))

    if args.apply:
        print(lang_tool.correct(text))
    else:
        for match in lang_tool.check(text):
            print(match)

if __name__ == "__main__":
    sys.exit(main())
