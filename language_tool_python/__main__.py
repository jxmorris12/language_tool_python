"""LanguageTool command line."""

import argparse
import locale
import re
import sys
from importlib.metadata import version, PackageNotFoundError
import toml
from typing import Any, Optional, Set, Union

from .server import LanguageTool
from .utils import LanguageToolError

try:
    __version__ = version("language_tool_python")
except PackageNotFoundError: # If the package is not installed in the environment, read the version from pyproject.toml
    with open("pyproject.toml", "rb") as f:
        __version__ = toml.loads(f.read().decode('utf-8'))["project"]["version"]


def parse_args() -> argparse.Namespace:
    """
    Parse command line arguments.

    :return: parsed arguments
    :rtype: argparse.Namespace
    """
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
    parser.add_argument('-p', '--picky', action='store_true',
                        help='If set, additional rules will be activated.')
    parser.add_argument(
        '--version', action='version',
        version=f'%(prog)s {__version__}',
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
    """
    Custom argparse action to update a set of rules in the namespace.
    This action is used to modify the set of rules stored in the argparse
    namespace when the action is triggered. It updates the attribute specified
    by 'self.dest' with the provided values.

    Attributes:
        dest (str): the destination attribute to update
    """
    def __call__(self, parser: argparse.ArgumentParser, namespace: Any, values: Any, option_string: Optional[str] = None):
        """
        This method is called when the action is triggered. It updates the set of rules
        in the namespace with the provided values. The method is invoked automatically
        by argparse when the corresponding command-line argument is encountered.

        :param parser: The ArgumentParser object which contains this action.
        :type parser: argparse.ArgumentParser
        :param namespace: The namespace object that will be returned by parse_args().
        :type namespace: Any
        :param values: The argument values associated with the action.
        :type values: Any
        :param option_string: The option string that was used to invoke this action.
        :type option_string: Optional[str]
        """
        getattr(namespace, self.dest).update(values)


def get_rules(rules: str) -> Set[str]:
    """
    Parse a string of rules and return a set of rule IDs.

    :param rules: A string containing rule IDs separated by non-word characters.
    :type rules: str
    :return: A set of rule IDs.
    :rtype: Set[str]
    """
    return {rule.upper() for rule in re.findall(r"[\w\-]+", rules)}


def get_text(filename: Union[str, int], encoding: Optional[str], ignore: Optional[str]) -> str:
    """
    Read the content of a file and return it as a string, optionally ignoring lines that match a regular expression.

    :param filename: The name of the file to read or file descriptor.
    :type filename: Union[str, int]
    :param encoding: The encoding to use for reading the file.
    :type encoding: Optional[str]
    :param ignore: A regular expression pattern to match lines that should be ignored.
    :type ignore: Optional[str]
    :return: The content of the file as a string.
    :rtype: str
    """
    with open(filename, encoding=encoding) as f:
        text = ''.join('\n' if (ignore and re.match(ignore, line)) else line
                       for line in f.readlines())
    return text


def main() -> int:
    """
    Main function to parse arguments, process files, and check text using LanguageTool.

    :return: Exit status code
    :rtype: int
    """
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
                remote_server += f':{args.remote_port}'
        lang_tool = LanguageTool(
            language=args.language,
            motherTongue=args.mother_tongue,
            remote_server=remote_server,
        )

        try:
            text = get_text(filename, encoding, ignore=args.ignore_lines)
        except UnicodeError as exception:
            print(f'{filename}: {exception}', file=sys.stderr)
            continue

        if not args.spell_check:
            lang_tool.disable_spellchecking()

        lang_tool.disabled_rules.update(args.disable)
        lang_tool.enabled_rules.update(args.enable)
        lang_tool.enabled_rules_only = args.enabled_only

        if args.picky:
            lang_tool.picky = True

        try:
            if args.apply:
                print(lang_tool.correct(text))
            else:
                for match in lang_tool.check(text):
                    rule_id = match.ruleId

                    replacement_text = ', '.join(
                        f"'{word}'"
                        for word in match.replacements).strip()

                    message = match.message

                    # Messages that end with punctuation already include the
                    # suggestion.
                    if replacement_text and not message.endswith('?'):
                        message += ' Suggestions: ' + replacement_text
                    
                    line, column = match.get_line_and_column(text)

                    print(f'{filename}:{line}:{column}: {rule_id}: {message}')

                    status = 2
        except LanguageToolError as exception:
            print(f'{filename}: {exception}', file=sys.stderr)
            continue

    return status


sys.exit(main())
