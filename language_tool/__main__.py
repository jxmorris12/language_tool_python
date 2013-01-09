"""LanguageTool command line
"""

import argparse
import locale
import os
import re
import sys

import language_tool.console_mode

DEFAULT_ENCODING = "utf-8"


def parse_args():
    parser = argparse.ArgumentParser(
        description=__doc__.strip(),
        prog="{} -m {}".format(os.path.basename(sys.executable),
                               "language_tool")
    )
    parser.add_argument("file",
                        help="plain text file or “-” for stdin")
    parser.add_argument("-c", "--encoding",
                        help="input encoding")
    parser.add_argument("-l", "--language", metavar="CODE",
                        help="language code of the input or “auto”")
    parser.add_argument("-m", "--mother-tongue", metavar="CODE",
                        help="language code of your first language")
    parser.add_argument("-d", "--disable", metavar="RULES", type=get_rules,
                        action=RulesAction, default=set(),
                        help="list of rule IDs to be disabled")
    parser.add_argument("-e", "--enable", metavar="RULES", type=get_rules,
                        action=RulesAction, default=set(),
                        help="list of rule IDs to be enabled")
    parser.add_argument("--api", action="store_true",
                        help="print results as XML")
    parser.add_argument("--version", action="version",
                        version="LanguageTool {} ({})"
                                .format(language_tool.get_version(),
                                        language_tool.get_build_date()),
                        help="show LanguageTool version and build date")
    parser.add_argument("-a", "--apply", action="store_true",
                        help="automatically apply suggestions if available")
    parser.add_argument("-s", "--spell-check-off", dest="spell_check",
                        action="store_false",
                        help="disable spell-checking rules")
    return parser.parse_args()


class RulesAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        getattr(namespace, self.dest).update(values)


def get_rules(rules: str) -> set:
    return {rule.upper() for rule in re.findall(r"[\w\-]+", rules)}


def get_text(file, encoding):
    with open(file, encoding=encoding) as f:
        text = "".join(f.readlines())
    return text


def main():
    args = parse_args()

    if args.file == "-":
        file = sys.stdin.fileno()
        encoding = args.encoding or (
            sys.stdin.encoding if sys.stdin.isatty()
            else locale.getpreferredencoding()
        )
    else:
        file = args.file
        encoding = args.encoding or "utf-8"

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
                if not args.api:
                    print("Detected language: {}".format(language),
                          file=sys.stderr)
                if not language:
                    return 1
                lang_tool.language = language
        else:
            lang_tool.language = args.language

    if not guess_language:
        if not args.api:
            print("Language: {}".format(lang_tool.language))
        text = get_text(file, encoding)

    if not args.spell_check:
        lang_tool.disable_spellchecking()

    lang_tool.disabled.update(args.disable)
    lang_tool.enabled.update(args.enable)

    if args.api:
        print(lang_tool._check_api(text).decode("utf-8"))
    elif args.apply:
        print(lang_tool.correct(text))
    else:
        print()
        for n, match in enumerate(lang_tool.check(text)):
            print("{}.) {}".format(n + 1, match))
            print()


if __name__ == "__main__":
    sys.exit(main())
