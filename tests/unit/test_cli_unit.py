"""Unit tests for the CLI helper functions in __main__.py."""

from __future__ import annotations

import io
import logging
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Iterator

from language_tool_python.__main__ import (
    CliArgs,
    _read_project_version,
    get_input_text,
    get_remote_server,
    get_rules,
    get_text,
    main,
    parse_args,
    print_exception,
    process_file,
)
from language_tool_python.exceptions import LanguageToolError

NUMBER_OF_DOTS_IN_VERSION = 2  # e.g. "3.4.0" has two dots


class TestGetRules:
    """Tests for the get_rules() rule-string parser."""

    def test_comma_separated(self) -> None:
        """Comma-separated rule IDs are returned as a set."""
        assert get_rules("RULE_A,RULE_B") == {"RULE_A", "RULE_B"}

    def test_uppercases(self) -> None:
        """Rule IDs are uppercased."""
        assert get_rules("rule_a") == {"RULE_A"}

    def test_hyphen_allowed(self) -> None:
        """Hyphens inside rule IDs are preserved."""
        assert get_rules("MORFOLOGIK-RULE") == {"MORFOLOGIK-RULE"}

    def test_whitespace_separated(self) -> None:
        """Whitespace-separated rule IDs are each returned."""
        assert get_rules("RULE_A RULE_B") == {"RULE_A", "RULE_B"}

    def test_empty_string(self) -> None:
        """Empty input returns an empty set."""
        assert get_rules("") == set()


class TestParseArgsEnabledOnly:
    """Tests for the --enabled-only CLI argument validation."""

    def test_enabled_only_with_disable_raises(self) -> None:
        """--enabled-only combined with --disable causes SystemExit."""
        with pytest.raises(SystemExit):
            parse_args(
                [
                    "-l",
                    "en-US",
                    "--enabled-only",
                    "-e",
                    "RULE",
                    "-d",
                    "OTHER",
                    "file.txt",
                ]
            )

    def test_enabled_only_with_enable_passes(self) -> None:
        """--enabled-only with --enable is accepted."""
        args = parse_args(["-l", "en-US", "--enabled-only", "-e", "RULE", "file.txt"])
        assert args.enabled_only is True
        assert "RULE" in args.enable


class TestGetRemoteServer:
    """Tests for the get_remote_server() URL builder."""

    def _args(self, host: str | None = None, port: str | None = None) -> CliArgs:
        """Build a minimal CliArgs with only remote_host/remote_port set."""
        args = CliArgs()
        args.remote_host = host
        args.remote_port = port
        return args

    def test_no_host_returns_none(self) -> None:
        """Returns None when no remote host is set."""
        assert get_remote_server(self._args()) is None

    def test_host_without_port(self) -> None:
        """Returns the host name alone when no port is given."""
        assert get_remote_server(self._args(host="localhost")) == "localhost"

    def test_host_with_port(self) -> None:
        """Returns host:port when both are provided."""
        result = get_remote_server(self._args(host="localhost", port="8081"))
        assert result == "localhost:8081"


class TestPrintException:
    """Tests for the print_exception() stderr printer."""

    def test_without_debug_prints_to_stderr(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Without debug=True, only the message is printed to stderr."""
        print_exception(ValueError("test error"), debug=False)
        result = capsys.readouterr()
        assert "test error" in result.err
        assert "ValueError" not in result.err

    def test_with_debug_prints_traceback(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """With debug=True, the full traceback is printed to stderr."""
        try:
            msg = "original error"
            raise ValueError(msg)
        except ValueError:
            print_exception(ValueError("current error"), debug=True)
        result = capsys.readouterr()
        assert "original error" in result.err
        assert "ValueError" in result.err


class TestGetText:
    """Tests for the get_text() file reader."""

    def test_reads_file(self, tmp_path: Path) -> None:
        """File content is returned as-is when no ignore pattern is given."""
        f = tmp_path / "test.txt"
        f.write_text("hello world\n", encoding="utf-8")
        result = get_text(str(f), encoding="utf-8", ignore=None)
        assert result == "hello world\n"

    def test_ignore_replaces_matching_lines(self, tmp_path: Path) -> None:
        """Lines matching the ignore regex are replaced with a newline."""
        f = tmp_path / "test.txt"
        f.write_text("keep this\n# skip this\nkeep too\n", encoding="utf-8")
        result = get_text(str(f), encoding="utf-8", ignore=r"#.*")
        assert "# skip this" not in result
        assert "keep this" in result
        assert "keep too" in result

    def test_no_ignore_keeps_all(self, tmp_path: Path) -> None:
        """All lines are kept when no ignore pattern is set."""
        f = tmp_path / "test.txt"
        f.write_text("line1\nline2\n", encoding="utf-8")
        result = get_text(str(f), encoding=None, ignore=None)
        assert result == "line1\nline2\n"


class TestGetInputText:
    """Tests for the get_input_text() stdin/file dispatcher."""

    def _args(
        self, ignore_lines: str | None = None, encoding: str | None = None
    ) -> CliArgs:
        """Build a minimal CliArgs with only ignore_lines/encoding set."""
        args = CliArgs()
        args.ignore_lines = ignore_lines
        args.encoding = encoding
        return args

    def test_reads_from_file(self, tmp_path: Path) -> None:
        """Regular filename is read from disk."""
        f = tmp_path / "input.txt"
        f.write_text("test content", encoding="utf-8")
        result = get_input_text(str(f), self._args())
        assert result == "test content"

    def test_reads_from_stdin(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Filename '-' reads from stdin."""
        monkeypatch.setattr("sys.stdin", io.StringIO("stdin content"))
        result = get_input_text("-", self._args())
        assert result == "stdin content"

    def test_stdin_with_ignore_lines(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Matching lines from stdin are suppressed when ignore_lines is set."""
        monkeypatch.setattr("sys.stdin", io.StringIO("keep\n# skip\nkeep2\n"))
        result = get_input_text("-", self._args(ignore_lines=r"#.*"))
        assert "# skip" not in result
        assert "keep" in result
        assert "keep2" in result

    def test_uses_encoding(self, tmp_path: Path) -> None:
        """Non-UTF-8 files are decoded with the specified encoding."""
        f = tmp_path / "latin.txt"
        content = "caf\xe9"
        f.write_bytes(content.encode("latin-1"))
        result = get_input_text(str(f), self._args(encoding="latin-1"))
        assert "caf" in result


class TestReadProjectVersion:
    """Tests for _read_project_version()."""

    def test_reads_version_from_pyproject(self) -> None:
        """Version string is read from the project's pyproject.toml."""
        pyproject = Path(__file__).parent.parent.parent / "pyproject.toml"
        version = _read_project_version(pyproject)
        assert isinstance(version, str)
        assert version.count(".") == NUMBER_OF_DOTS_IN_VERSION


class _MockMatch:
    """Minimal match object for process_file unit tests."""

    def __init__(
        self,
        rule_id: str = "RULE",
        message: str = "A suggestion.",
        replacements: list[str] | None = None,
    ) -> None:
        self.rule_id = rule_id
        self.message = message
        self.replacements: list[str] = replacements or []

    def get_line_and_column(self, _text: str) -> tuple[int, int]:
        return (1, 0)


class _MockLangTool:
    """Minimal LanguageTool mock for process_file unit tests."""

    _last_instance: _MockLangTool | None = None

    def __init__(self, **_kw: object) -> None:
        _MockLangTool._last_instance = self
        self.disabled_rules: set[str] = set()
        self.enabled_rules: set[str] = set()
        self.disabled_categories: set[str] = set()
        self.enabled_categories: set[str] = set()
        self.enabled_rules_only: bool = False
        self.picky: bool = False
        self._spellcheck_disabled: bool = False
        self._matches: list[_MockMatch] = []

    def __enter__(self) -> _MockLangTool:
        return self

    def __exit__(self, *_: object) -> None:
        pass

    def disable_spellchecking(self) -> None:
        self._spellcheck_disabled = True

    def check(self, _text: str) -> list[_MockMatch]:
        return self._matches

    def correct(self, text: str) -> str:
        return text + " (corrected)"


class _RaisingLangTool:
    """LanguageTool mock that raises LanguageToolError on context entry."""

    def __init__(self, **_kw: object) -> None:
        pass

    def __enter__(self) -> _RaisingLangTool:
        err = "server failed"
        raise LanguageToolError(err)

    def __exit__(self, *_: object) -> None:
        pass


def _parse_file_args(filename: str, **overrides: object) -> CliArgs:
    """Build CliArgs from parse_args defaults with optional field overrides."""
    args = parse_args([filename])
    for k, v in overrides.items():
        setattr(args, k, v)
    return args


class TestProcessFile:
    """Tests for process_file() with LanguageTool mocked."""

    @pytest.fixture(autouse=True)
    def _reset_last_instance(self) -> Iterator[None]:
        """Reset _MockLangTool._last_instance before and after each test.

        Without this, only tests that explicitly reset the class attribute could
        reliably assert on the instance created by the test they belong to.
        """
        _MockLangTool._last_instance = None
        yield
        _MockLangTool._last_instance = None

    def test_prints_filename_to_stderr_for_multiple_files(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Filename is printed to stderr when processing multiple files."""
        f = tmp_path / "a.txt"
        f.write_text("hello", encoding="utf-8")
        monkeypatch.setattr(
            "language_tool_python.__main__.LanguageTool",
            _MockLangTool,
        )
        args = _parse_file_args(str(f), files=[str(f), "other.txt"])
        process_file(str(f), args, None)
        assert str(f) in capsys.readouterr().err

    def test_returns_zero_on_file_not_found(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """Returns 0 when get_input_text raises FileNotFoundError."""
        monkeypatch.setattr(
            "language_tool_python.__main__.LanguageTool",
            _MockLangTool,
        )
        missing = str(tmp_path / "does_not_exist.txt")
        result = process_file(missing, _parse_file_args(missing), None)
        assert result == 0

    def test_disables_spellcheck_when_flag_off(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """disable_spellchecking() is called when spell_check=False."""
        f = tmp_path / "text.txt"
        f.write_text("hello", encoding="utf-8")
        monkeypatch.setattr(
            "language_tool_python.__main__.LanguageTool",
            _MockLangTool,
        )
        process_file(str(f), _parse_file_args(str(f), spell_check=False), None)
        assert _MockLangTool._last_instance is not None
        assert _MockLangTool._last_instance._spellcheck_disabled

    def test_sets_picky_when_flag_on(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """Picky is set to True on the tool when args.picky=True."""
        f = tmp_path / "text.txt"
        f.write_text("hello", encoding="utf-8")
        monkeypatch.setattr(
            "language_tool_python.__main__.LanguageTool",
            _MockLangTool,
        )
        process_file(str(f), _parse_file_args(str(f), picky=True), None)
        assert _MockLangTool._last_instance is not None
        assert _MockLangTool._last_instance.picky is True

    def test_apply_prints_corrected_text_and_returns_zero(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """--apply prints corrected text to stdout and returns 0."""
        f = tmp_path / "text.txt"
        f.write_text("hello", encoding="utf-8")
        monkeypatch.setattr(
            "language_tool_python.__main__.LanguageTool",
            _MockLangTool,
        )
        result = process_file(str(f), _parse_file_args(str(f), apply=True), None)
        assert result == 0
        assert "corrected" in capsys.readouterr().out

    def test_returns_zero_on_language_tool_error(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """Returns 0 when LanguageTool raises LanguageToolError on entry."""
        f = tmp_path / "text.txt"
        f.write_text("hello", encoding="utf-8")
        monkeypatch.setattr(
            "language_tool_python.__main__.LanguageTool",
            _RaisingLangTool,
        )
        result = process_file(str(f), _parse_file_args(str(f)), None)
        assert result == 0

    def test_prints_match_and_returns_two_when_issues_found(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Match details are printed and status 2 is returned when issues are found."""

        class _MatchingLangTool(_MockLangTool):
            def check(self, _text: str) -> list[_MockMatch]:
                return [
                    _MockMatch(
                        rule_id="SOME_RULE",
                        message="Fix this.",
                        replacements=["fix"],
                    ),
                ]

        f = tmp_path / "text.txt"
        f.write_text("hello", encoding="utf-8")
        monkeypatch.setattr(
            "language_tool_python.__main__.LanguageTool",
            _MatchingLangTool,
        )
        status_issues = 2
        result = process_file(str(f), _parse_file_args(str(f)), None)
        assert result == status_issues
        out = capsys.readouterr().out
        assert "SOME_RULE" in out
        assert "fix" in out


class TestMain:
    """Tests for main() with LanguageTool mocked."""

    def test_verbose_flag_sets_debug_logging(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """--verbose sets the root logger level to DEBUG."""
        f = tmp_path / "text.txt"
        f.write_text("hello", encoding="utf-8")
        monkeypatch.setattr(
            "language_tool_python.__main__.LanguageTool",
            _MockLangTool,
        )
        root = logging.getLogger()
        original_level = root.level
        try:
            result = main(["--verbose", str(f)])
            assert result == 0
            assert root.level == logging.DEBUG
        finally:
            root.setLevel(original_level)

    def test_status_is_max_across_multiple_files(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """main() aggregates status via max() across all processed files."""

        class _ConditionalLangTool(_MockLangTool):
            def check(self, text: str) -> list[_MockMatch]:
                if text == "bad text":
                    return [_MockMatch(rule_id="SOME_RULE")]
                return []

        clean_file = tmp_path / "clean.txt"
        clean_file.write_text("good text", encoding="utf-8")
        bad_file = tmp_path / "bad.txt"
        bad_file.write_text("bad text", encoding="utf-8")

        monkeypatch.setattr(
            "language_tool_python.__main__.LanguageTool",
            _ConditionalLangTool,
        )
        status_issues = 2
        result = main([str(clean_file), str(bad_file)])
        assert result == status_issues

    def test_remote_server_propagates_to_language_tool_constructor(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """--remote-host/--remote-port flow through to the LanguageTool constructor."""
        f = tmp_path / "text.txt"
        f.write_text("hello", encoding="utf-8")
        captured_kwargs: list[dict[str, object]] = []

        class _CapturingLangTool(_MockLangTool):
            def __init__(self, **kw: object) -> None:
                super().__init__(**kw)
                captured_kwargs.append(kw)

        monkeypatch.setattr(
            "language_tool_python.__main__.LanguageTool",
            _CapturingLangTool,
        )

        main(["--remote-host", "example.test", "--remote-port", "8081", str(f)])

        assert len(captured_kwargs) == 1
        assert captured_kwargs[0]["remote_server"] == "example.test:8081"
