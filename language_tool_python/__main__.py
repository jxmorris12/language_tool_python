"""LanguageTool command line."""

from __future__ import annotations

import argparse
import importlib.resources
import logging
import re
import sys
import traceback
from importlib.metadata import PackageNotFoundError, version
from logging.config import dictConfig
from pathlib import Path
from typing import TYPE_CHECKING, TypedDict, cast

from ._internals.compat import toml_loads
from .exceptions import LanguageToolError
from .server import LanguageTool

if TYPE_CHECKING:
    from collections.abc import Sequence
    from typing import TextIO


class _PyProjectProject(TypedDict):
    version: str


class _PyProject(TypedDict):
    project: _PyProjectProject


def _load_pyproject_and_logconfig(path: Path) -> dict[str, object]:
    """Load a TOML file as a typed dictionary.

    :param path: The path to the TOML file to load.
    :type path: Path
    :return: The contents of the TOML file as a dictionary.
    :rtype: dict[str, object]
    """
    with path.open("rb") as f:
        return cast("dict[str, object]", toml_loads(f.read().decode("utf-8")))


def _read_project_version(pyproject: Path) -> str:
    """Read the package version from pyproject.toml.

    :param pyproject: The path to the pyproject.toml file.
    :type pyproject: Path
    :return: The package version.
    :rtype: str
    """
    pyproject_config = cast("_PyProject", _load_pyproject_and_logconfig(pyproject))
    return pyproject_config["project"]["version"]


try:
    __version__ = version("language_tool_python")
    # If the package is not installed in the environment,
    # read the version from pyproject.toml
except PackageNotFoundError:
    project_root = Path(__file__).resolve().parent.parent
    pyproject = project_root / "pyproject.toml"
    __version__ = _read_project_version(pyproject)


logger = logging.getLogger(__name__)
with importlib.resources.as_file(
    importlib.resources.files("language_tool_python").joinpath("logging.toml"),
) as config_path:
    log_config = _load_pyproject_and_logconfig(config_path)
dictConfig(log_config)

RULE_RE: re.Pattern[str] = re.compile(r"[\w-]+")


class CliArgs(argparse.Namespace):
    """Typed command-line arguments."""

    files: list[str]
    encoding: str | None
    language: str | None
    mother_tongue: str | None
    disable: set[str]
    enable: set[str]
    enabled_only: bool
    picky: bool
    apply: bool
    spell_check: bool
    ignore_lines: str | None
    remote_host: str | None
    remote_port: str | None
    verbose: bool


def parse_args(argv: Sequence[str] | None = None) -> CliArgs:
    """Parse command line arguments.

    :return: parsed arguments
    :rtype: CliArgs
    """
    parser = argparse.ArgumentParser(
        description=__doc__.strip() if __doc__ else None,
        prog="language_tool_python",
    )
    parser.add_argument("files", nargs="+", help='plain text file or "-" for stdin')
    parser.add_argument("-c", "--encoding", help="input encoding")
    parser.add_argument(
        "-l",
        "--language",
        metavar="CODE",
        help='language code of the input or "auto"',
    )
    parser.add_argument(
        "-m",
        "--mother-tongue",
        metavar="CODE",
        help="language code of your first language",
    )
    parser.add_argument(
        "-d",
        "--disable",
        metavar="RULES",
        type=get_rules,
        action=RulesAction,
        default=set[str](),
        help="list of rule IDs to be disabled",
    )
    parser.add_argument(
        "-e",
        "--enable",
        metavar="RULES",
        type=get_rules,
        action=RulesAction,
        default=set[str](),
        help="list of rule IDs to be enabled",
    )
    parser.add_argument(
        "--enabled-only",
        action="store_true",
        help="disable all rules except those specified in --enable",
    )
    parser.add_argument(
        "-p",
        "--picky",
        action="store_true",
        help="If set, additional rules will be activated.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
        help="show version",
    )
    parser.add_argument(
        "-a",
        "--apply",
        action="store_true",
        help="automatically apply suggestions if available",
    )
    parser.add_argument(
        "-s",
        "--spell-check-off",
        dest="spell_check",
        action="store_false",
        help="disable spell-checking rules",
    )
    parser.add_argument(
        "--ignore-lines",
        help="ignore lines that match this regular expression",
    )
    parser.add_argument(
        "--remote-host",
        help="hostname of the remote LanguageTool server",
    )
    parser.add_argument("--remote-port", help="port of the remote LanguageTool server")
    parser.add_argument("--verbose", action="store_true", help="enable verbose output")

    args = CliArgs()
    parser.parse_args(argv, namespace=args)

    if args.enabled_only:
        if args.disable:
            parser.error("--enabled-only cannot be used with --disable")

        if not args.enable:
            parser.error("--enabled-only requires --enable")

    return args


class RulesAction(argparse.Action):
    """Custom argparse action to update a set of rules in the namespace.

    This action is used to modify the set of rules stored in the argparse namespace when
    the action is triggered. It updates the attribute specified by 'self.dest' with the
    provided values.
    """

    dest: str
    """The destination attribute to update."""

    def __call__(
        self,
        _parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: str | Sequence[object] | None,
        _option_string: str | None = None,
    ) -> None:
        """Update the namespace rule set when the action is triggered.

        The method updates the set of rules in the namespace with the provided values.
        It is invoked automatically by argparse when the corresponding command-line
        argument is encountered.

        :param _parser: The ArgumentParser object which contains this action.
        :type _parser: argparse.ArgumentParser
        :param namespace: The namespace object that will be returned by parse_args().
        :type namespace: CliArgs
        :param values: The argument values associated with the action.
        :type values: str | Sequence[object] | None
        :param _option_string: The option string that was used to invoke this action.
        :type _option_string: str | None
        """
        cli_args = cast("CliArgs", namespace)
        rule_values = cast("set[str]", values)
        if self.dest == "disable":
            cli_args.disable.update(rule_values)
        elif self.dest == "enable":
            cli_args.enable.update(rule_values)
        else:
            err = f"unexpected rules destination: {self.dest}"
            raise ValueError(err)


def get_rules(rules: str) -> set[str]:
    """Parse a string of rules and return a set of rule IDs.

    :param rules: A string containing rule IDs separated by non-word characters.
    :type rules: str
    :return: A set of rule IDs.
    :rtype: set[str]
    """
    rule_ids = cast("list[str]", RULE_RE.findall(rules))
    return {rule.upper() for rule in rule_ids}


def get_text(
    filename: str | int,
    encoding: str | None,
    ignore: str | None,
) -> str:
    """Read a file and optionally ignore lines matching a regex.

    :param filename: The name of the file to read or file descriptor.
    :type filename: str | int
    :param encoding: The encoding to use for reading the file.
    :type encoding: str | None
    :param ignore: A regular expression pattern to match lines that should be ignored.
    :type ignore: str | None
    :return: The content of the file as a string.
    :rtype: str
    """
    with open(filename, encoding=encoding) as f:  # noqa: PTH123  # Need to use classic open() here to support file descriptors
        return "".join(
            "\n" if (ignore and re.match(ignore, line)) else line for line in f
        )


def print_exception(exc: Exception, debug: bool) -> None:
    """Print an exception message to stderr, optionally including a stack trace.

    :param exc: The exception to print.
    :type exc: Exception
    :param debug: Whether to include a stack trace.
    :type debug: bool
    """
    if debug:
        traceback.print_exc()
    else:
        print(exc, file=sys.stderr)


def get_remote_server(args: CliArgs) -> str | None:
    """Build the remote server address from parsed arguments.

    :param args: Parsed command-line arguments.
    :type args: CliArgs
    :return: The remote server address in the format "host:port" or None if no remote
        host is specified.
    :rtype: str | None
    """
    if args.remote_host is None:
        return None

    remote_server: str = args.remote_host
    if args.remote_port is not None:
        remote_server += f":{args.remote_port}"

    return remote_server


def get_input_text(filename: str, args: CliArgs) -> str:
    """Read input text from a file or stdin.

    :param filename: The name of the file to read or "-" for stdin.
    :type filename: str
    :param args: Parsed command-line arguments.
    :type args: CliArgs
    :return: The input text as a string.
    :rtype: str
    """
    if filename == "-":
        stdin = cast("TextIO", sys.stdin)
        raw = stdin.read()
        if args.ignore_lines:
            return "".join(
                "\n" if re.match(args.ignore_lines, line) else line
                for line in raw.splitlines(keepends=True)
            )
        return raw

    encoding = args.encoding or "utf-8"
    return get_text(filename, encoding, ignore=args.ignore_lines)


def process_file(
    filename: str,
    args: CliArgs,
    remote_server: str | None,
) -> int:
    """Check a single input file and return the resulting status.

    :param filename: The name of the file to check or "-" for stdin.
    :type filename: str
    :param args: Parsed command-line arguments.
    :type args: CliArgs
    :param remote_server: The remote server address or None.
    :type remote_server: str | None
    :return: The resulting status.
    :rtype: int
    """
    if len(args.files) > 1:
        print(filename, file=sys.stderr)

    try:
        with LanguageTool(
            language=args.language,
            mother_tongue=args.mother_tongue,
            remote_server=remote_server,
        ) as lang_tool:
            try:
                text = get_input_text(filename, args)
            except (UnicodeError, FileNotFoundError) as exception:
                print_exception(exception, args.verbose)
                return 0

            if not args.spell_check:
                lang_tool.disable_spellchecking()

            lang_tool.disabled_rules.update(args.disable)
            lang_tool.enabled_rules.update(args.enable)
            lang_tool.enabled_rules_only = args.enabled_only

            if args.picky:
                lang_tool.picky = True

            if args.apply:
                print(lang_tool.correct(text))
                return 0

            status = 0
            for match in lang_tool.check(text):
                rule_id = match.rule_id

                replacement_text = ", ".join(
                    f"'{word}'" for word in match.replacements
                ).strip()

                message = match.message

                # Messages that end with punctuation already include the
                # suggestion.
                if replacement_text and not message.endswith("?"):
                    message += " Suggestions: " + replacement_text

                line, column = match.get_line_and_column(text)

                print(f"{filename}:{line}:{column}: {rule_id}: {message}")

                status = 2

            return status
    except LanguageToolError as exception:
        print_exception(exception, args.verbose)
        return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Parse arguments, process files, and check text using LanguageTool.

    :param argv: Command-line arguments to parse, or None to use sys.argv.
    :type argv: Sequence[str] | None
    :return: Exit status code
    :rtype: int
    """
    args = parse_args(argv)

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    status = 0
    remote_server = get_remote_server(args)

    for filename in args.files:
        status = max(status, process_file(filename, args, remote_server))
    return status


if __name__ == "__main__":
    raise SystemExit(main())
