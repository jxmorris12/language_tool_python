"""LanguageTool command line."""

import argparse
import locale
import os
import re
import sys

from . import __version__
from . import get_build_date
from . import get_version
from . import LanguageTool


def parse_args():
    parser = argparse.ArgumentParser(
        description=__doc__.strip(),
        prog='language-check'.format(os.path.basename(sys.executable),
                                     'language_check'))
    parser.add_argument('files', nargs='+',
                        help='plain text file or "-" for stdin')
    parser.add_argument('-c', '--encoding',
                        help='input encoding')
    parser.add_argument('-l', '--language', metavar='CODE',
                        help='language code of the input or "auto"')
    parser.add_argument('-m', '--mother-tongue', metavar='CODE',
                        help='language code of your first language')
    parser.add_argument('-d', '--disable', metavar='RULES', type=get_rules,
                        action=RulesAction, default=set(),
                        help='list of rule IDs to be disabled')
    parser.add_argument('-e', '--enable', metavar='RULES', type=get_rules,
                        action=RulesAction, default=set(),
                        help='list of rule IDs to be enabled')
    parser.add_argument('--api', action='store_true',
                        help='print results as XML')
    parser.add_argument(
        '--version', action='version',
        version='%(prog)s {} (LanguageTool {} ({}))'.format(
            __version__,
            get_version(),
            get_build_date()),
        help='show version')
    parser.add_argument('-a', '--apply', action='store_true',
                        help='automatically apply suggestions if available')
    parser.add_argument('-s', '--spell-check-off', dest='spell_check',
                        action='store_false',
                        help='disable spell-checking rules')
    parser.add_argument('--ignore-lines',
                        help='ignore lines that match this regular expression')
    return parser.parse_args()


class RulesAction(argparse.Action):

    def __call__(self, parser, namespace, values, option_string=None):
        getattr(namespace, self.dest).update(values)


def get_rules(rules: str) -> set:
    return {rule.upper() for rule in re.findall(r"[\w\-]+", rules)}


def get_text(filename, encoding, ignore):
    with open(filename, encoding=encoding) as f:
        text = ''.join('\n' if (ignore and re.match(ignore, line)) else line
                       for line in f.readlines())
    return text


def main():
    args = parse_args()

    status = 0

    for filename in args.files:
        if len(args.files) > 1:
            print(filename, file=sys.stderr)

        if filename == '-':
            filename = sys.stdin.fileno()
            encoding = args.encoding or (
                sys.stdin.encoding if sys.stdin.isatty()
                else locale.getpreferredencoding()
            )
        else:
            encoding = args.encoding or 'utf-8'

        lang_tool = LanguageTool(
            motherTongue=args.mother_tongue)
        guess_language = None

        text = get_text(filename, encoding, ignore=args.ignore_lines)

        if args.language:
            if args.language.lower() == 'auto':
                try:
                    from guess_language import guess_language
                except ImportError:
                    print('guess_language is unavailable.', file=sys.stderr)
                    return 1
                else:
                    language = guess_language(text)
                    if not args.api:
                        print('Detected language: {}'.format(language),
                              file=sys.stderr)
                    if not language:
                        return 1
                    lang_tool.language = language
            else:
                lang_tool.language = args.language

        if not args.spell_check:
            lang_tool.disable_spellchecking()

        lang_tool.disabled.update(args.disable)
        lang_tool.enabled.update(args.enable)

        if args.api:
            print(lang_tool._check_api(text).decode())
        elif args.apply:
            print(lang_tool.correct(text))
        else:
            for match in lang_tool.check(text):
                rule_id = match.ruleId
                if match.subId is not None:
                    rule_id += '[{}]'.format(match.subId)

                replacement_text = ', '.join(
                    "'{}'".format(word)
                    for word in match.replacements).strip()

                message = match.msg

                # Messages that end with punctuation already include the
                # suggestion.
                if replacement_text and not message.endswith(('.', '?')):
                    message += '; suggestions: ' + replacement_text

                print('{}:{}:{}: {}: {}'.format(
                    filename,
                    match.fromy + 1,
                    match.fromx + 1,
                    rule_id,
                    message))
                status = 2

    return status
