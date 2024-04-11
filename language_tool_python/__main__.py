"""LanguageTool command line."""

import argparse
import locale
import re
import sys

from .server import LanguageTool
from .utils import LanguageToolError

import pkg_resources
__version__ = pkg_resources.require("language_tool_python")[0].version


def parse_args():
    parser = argparse.ArgumentParser(
        description=__doc__.strip() if __doc__ else None,
        prog='language_tool_python')
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
    parser.add_argument('--enabled-only', action='store_true',
                        help='disable all rules except those specified in '
                             '--enable')
    parser.add_argument(
        '--version', action='version',
        version='%(prog)s {}'.format(__version__),
        help='show version')
    parser.add_argument('-a', '--apply', action='store_true',
                        help='automatically apply suggestions if available')
    parser.add_argument('-s', '--spell-check-off', dest='spell_check',
                        action='store_false',
                        help='disable spell-checking rules')
    parser.add_argument('--ignore-lines',
                        help='ignore lines that match this regular expression')
    parser.add_argument('--remote-host',
                        help='hostname of the remote LanguageTool server')
    parser.add_argument('--remote-port',
                        help='port of the remote LanguageTool server')

    args = parser.parse_args()

    if args.enabled_only:
        if args.disable:
            parser.error('--enabled-only cannot be used with --disable')

        if not args.enable:
            parser.error('--enabled-only requires --enable')

    return args


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


def print_unicode(text):
    """Print in a portable manner."""
    if sys.version_info[0] < 3:
        text = text.encode('utf-8')

    print(text)


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

        remote_server = None
        if args.remote_host is not None:
            remote_server = args.remote_host
            if args.remote_port is not None:
                remote_server += ':{}'.format(args.remote_port)
        lang_tool = LanguageTool(
            motherTongue=args.mother_tongue,
            remote_server=remote_server,
        )
        guess_language = None

        try:
            text = get_text(filename, encoding, ignore=args.ignore_lines)
        except UnicodeError as exception:
            print('{}: {}'.format(filename, exception), file=sys.stderr)
            continue

        if args.language:
            if args.language.lower() == 'auto':
                try:
                    from guess_language import guess_language
                except ImportError:
                    print('guess_language is unavailable.', file=sys.stderr)
                    return 1
                else:
                    language = guess_language(text)
                    print('Detected language: {}'.format(language),
                          file=sys.stderr)
                    if not language:
                        return 1
                    lang_tool.language = language
            else:
                lang_tool.language = args.language

        if not args.spell_check:
            lang_tool.disable_spellchecking()

        lang_tool.disabled_rules.update(args.disable)
        lang_tool.enabled_rules.update(args.enable)
        lang_tool.enabled_rules_only = args.enabled_only

        try:
            if args.apply:
                print_unicode(lang_tool.correct(text))
            else:
                for match in lang_tool.check(text):
                    rule_id = match.ruleId

                    replacement_text = ', '.join(
                        "'{}'".format(word)
                        for word in match.replacements).strip()

                    message = match.message

                    # Messages that end with punctuation already include the
                    # suggestion.
                    if replacement_text and not message.endswith(('.', '?')):
                        message += '; suggestions: ' + replacement_text

                    print_unicode('{}: {}: {}'.format(
                        filename,
                        rule_id,
                        message))

                    status = 2
        except LanguageToolError as exception:
            print('{}: {}'.format(filename, exception), file=sys.stderr)
            continue

    return status


sys.exit(main())
