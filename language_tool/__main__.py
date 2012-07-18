"""LanguageTool command line
"""

import argparse
import os
import re
import sys

import language_tool

DEFAULT_ENCODING = "utf-8"


def parse_args():
    parser = argparse.ArgumentParser(
        description=__doc__.strip(),
        prog="{} -m {}".format(os.path.basename(sys.executable),
                               "language_tool")
    )
    parser.add_argument("file", nargs="?",
                        help="plain text file")
    parser.add_argument("--encoding",
                        help="input encoding")
    parser.add_argument("--language", metavar="CODE",
                        help='language code of the input or "auto"')
    parser.add_argument("--mother-tongue", metavar="CODE",
                        help="language code of your first language")
    parser.add_argument("--disable", metavar="RULES", type=get_rules,
                        help="list of rule IDs to be disabled")
    parser.add_argument("--enable", metavar="RULES", type=get_rules,
                        help="list of rule IDs to be enabled")
    parser.add_argument("--version", action="store_true",
                        help="print LanguageTool version number")
    parser.add_argument("--apply", action="store_true",
                        help="automatically apply suggestions if available")
    return parser.parse_args()


def get_rules(rules: str) -> set:
    return {rule.upper() for rule in re.findall(r"\w+", rules)}


def get_text(file, encoding):
    with open(file, encoding=encoding) as f:
        text = "\n".join(f.readlines())
    return text


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

    lang_tool = language_tool.LanguageTool(motherTongue=args.mother_tongue)
    guess_language = None

    if args.language:
        if args.language.lower() == "auto":
            try:
                from guess_language import guess_language
            except ImportError:
                print("guess_language is unavailable.", file=sys.stderr)
                return 1
            else:
                text = get_text(file, encoding)
                language = guess_language(text)
                print("Detected language: {}".format(language),
                      file=sys.stderr)
                if not language:
                    return 1
                lang_tool.language = language
        else:
            lang_tool.language = args.language

    if not guess_language:
        print("Language: {}".format(lang_tool.language))
        text = get_text(file, encoding)

    if args.disable is not None:
        lang_tool.disable(args.disable)
    if args.enable is not None:
        lang_tool.enable(args.enable)

    if args.apply:
        print(lang_tool.correct(text))
    else:
        print()
        for match in lang_tool.check(text):
            print(match)
            print()


if __name__ == "__main__":
    sys.exit(main())
