"""Unit tests for the CLI helper functions in __main__.py."""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from language_tool_python.__main__ import (
    CliArgs,
    _read_project_version,
    get_input_text,
    get_remote_server,
    get_rules,
    get_text,
    parse_args,
    print_exception,
)


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
        assert "test error" in capsys.readouterr().err

    def test_with_debug_prints_traceback(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """With debug=True, the full traceback is printed to stderr."""
        try:
            msg = "original error"
            raise ValueError(msg)
        except ValueError:
            print_exception(ValueError("current error"), debug=True)
        captured = capsys.readouterr()
        assert "ValueError" in captured.err


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
        assert version.count(".") >= 1
