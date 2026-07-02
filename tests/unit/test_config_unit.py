"""Unit tests for config_file.py encoders, validators, and LanguageToolConfig."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from language_tool_python.config_file import (
    LanguageToolConfig,
    _bool_encoder,
    _comma_list_encoder,
    _encode_config,
    _int_encoder,
    _is_lang_key,
    _number_encoder,
    _path_encoder,
    _path_validator,
    _reject_line_breaks,
)
from language_tool_python.exceptions import PathError

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator, Mapping

    from language_tool_python.config_file import ConfigValue


class TestBoolEncoder:
    """Tests for the _bool_encoder() function."""

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            (True, "true"),
            (False, "false"),
            (1, "true"),
            (0, "false"),
        ],
        ids=["true", "false", "truthy_int", "falsy_int"],
    )
    def test_encodes_bool_value(self, value: bool, expected: str) -> None:
        """Truthy/falsy values are encoded as lowercase 'true'/'false'."""
        assert _bool_encoder(value) == expected


class TestIntEncoder:
    """Tests for the _int_encoder() function."""

    @pytest.mark.parametrize(
        ("value", "expected"),
        [(42, "42"), (0, "0")],
        ids=["positive", "zero"],
    )
    def test_encodes_int_value(self, value: int, expected: str) -> None:
        """Integers are converted to their decimal string representation."""
        assert _int_encoder(value) == expected


class TestNumberEncoder:
    """Tests for the _number_encoder() function."""

    def test_integer(self) -> None:
        """An integer value is rendered as a float string."""
        assert _number_encoder(5) == "5.0"

    def test_float(self) -> None:
        """A float value is rendered with its decimal part."""
        assert _number_encoder(3.14) == "3.14"


class TestCommaListEncoder:
    """Tests for the _comma_list_encoder() function."""

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("a,b,c", "a,b,c"),
            (["a", "b", "c"], "a,b,c"),
            (("x", "y"), "x,y"),
            (["only"], "only"),
        ],
        ids=["string_passthrough", "list_joined", "tuple_joined", "single_item"],
    )
    def test_encodes_comma_list_value(
        self, value: str | list[str] | tuple[str, ...], expected: str
    ) -> None:
        """Strings pass through unchanged; iterables are comma-joined."""
        assert _comma_list_encoder(value) == expected


class TestPathEncoder:
    """Tests for the _path_encoder() function."""

    def test_path_object(self, tmp_path: Path) -> None:
        """A Path object is encoded to a string containing the path components."""
        result = _path_encoder(tmp_path / "model")
        assert "model" in result

    def test_backslash_escaped(self) -> None:
        """Windows backslashes in path strings are escaped or converted."""
        p = Path("C:\\Users\\test\\model")
        result = _path_encoder(p)
        assert "\\\\" in result or "/" in result


class TestPathValidator:
    """Tests for the _path_validator() function."""

    def test_existing_file(self, tmp_path: Path) -> None:
        """An existing file path passes validation without error."""
        f = tmp_path / "file.txt"
        f.write_text("content")
        _path_validator(f)

    def test_existing_directory(self, tmp_path: Path) -> None:
        """An existing directory path passes validation without error."""
        _path_validator(tmp_path)

    def test_nonexistent_raises(self, tmp_path: Path) -> None:
        """A path that does not exist raises PathError."""
        with pytest.raises(PathError, match="does not exist"):
            _path_validator(tmp_path / "nonexistent.txt")


class TestRejectLineBreaks:
    """Tests for the _reject_line_breaks() config-value validator."""

    @pytest.mark.parametrize(
        "value",
        ["line\nbreak", "line\rbreak", "line\r\nbreak"],
        ids=["lf", "cr", "crlf"],
    )
    def test_raises_on_line_break(self, value: str) -> None:
        """Any value containing a line-break character raises ValueError."""
        with pytest.raises(ValueError, match="line breaks"):
            _reject_line_breaks("field", value)

    @pytest.mark.parametrize(
        "value",
        ["one\\", "three\\\\\\"],
        ids=["one", "three"],
    )
    def test_raises_on_odd_trailing_backslashes(self, value: str) -> None:
        """A value ending with an odd number of backslashes raises ValueError."""
        with pytest.raises(ValueError, match="odd number of backslashes"):
            _reject_line_breaks("field", value)

    @pytest.mark.parametrize(
        "value",
        ["no backslash at all", "two\\\\", "four\\\\\\\\"],
        ids=["none", "two", "four"],
    )
    def test_accepts_even_trailing_backslashes(self, value: str) -> None:
        """A value ending with an even number of backslashes does not raise."""
        _reject_line_breaks("field", value)  # must not raise


class TestIsLangKey:
    """Tests for the _is_lang_key() predicate."""

    @pytest.mark.parametrize(
        ("key", "expected"),
        [
            ("lang-en", True),
            ("lang-en-dictPath", True),
            ("cacheSize", False),
            ("lang-", False),
            ("lang-en-dictPath-extra", False),
        ],
        ids=[
            "lang_code_format",
            "lang_code_dict_path_format",
            "not_lang_prefix",
            "lang_only_no_code",
            "lang_too_many_parts",
        ],
    )
    def test_is_lang_key(self, key: str, expected: bool) -> None:
        """_is_lang_key() correctly classifies each key shape."""
        assert _is_lang_key(key) is expected


class TestEncodeConfig:
    """Tests for the _encode_config() dict encoder."""

    def test_int_option(self) -> None:
        """An integer option value is encoded as its decimal string."""
        result = _encode_config({"cacheSize": 1000})
        assert result == {"cacheSize": "1000"}

    def test_bool_option(self) -> None:
        """A boolean option value is encoded as 'true' or 'false'."""
        result = _encode_config({"pipelineCaching": True})
        assert result == {"pipelineCaching": "true"}

    def test_number_option(self) -> None:
        """A float option value is encoded as its float string."""
        result = _encode_config({"maxErrorsPerWordRate": 0.5})
        assert result == {"maxErrorsPerWordRate": "0.5"}

    def test_list_option(self) -> None:
        """A list option value is encoded as a comma-separated string."""
        result = _encode_config({"blockedReferrers": ["a.com", "b.com"]})
        assert result == {"blockedReferrers": "a.com,b.com"}

    def test_lang_code_option(self) -> None:
        """A language-code option is passed through without modification."""
        result = _encode_config({"lang-en": "custom-word"})
        assert result == {"lang-en": "custom-word"}

    def test_lang_dict_path_option(self, tmp_path: Path) -> None:
        """A language dict-path option is accepted when the path exists."""
        result = _encode_config({"lang-en-dictPath": str(tmp_path)})
        assert "lang-en-dictPath" in result

    def test_unknown_key_raises(self) -> None:
        """An unrecognized config key raises ValueError."""
        with pytest.raises(ValueError, match="unexpected key"):
            _encode_config({"unknownKey": "value"})

    def test_wrong_type_raises(self) -> None:
        """A value of the wrong type for a known key raises TypeError."""
        with pytest.raises(TypeError, match="invalid type"):
            _encode_config({"cacheSize": "not_an_int"})

    def test_path_validator_called(self, tmp_path: Path) -> None:
        """A path-type config option with a nonexistent path raises PathError."""
        nonexistent = tmp_path / "no_such_model"
        with pytest.raises(PathError, match="does not exist"):
            _encode_config({"languageModel": str(nonexistent)})


class TestLanguageToolConfig:
    """Tests for the LanguageToolConfig class."""

    @pytest.fixture()  # noqa: PT001  # bare @pytest.fixture resolves to Any under mypy strict here
    def make_config(
        self,
    ) -> Iterator[Callable[[Mapping[str, ConfigValue]], LanguageToolConfig]]:
        """Build a LanguageToolConfig factory that deletes its temp files afterwards.

        LanguageToolConfig() creates a real temporary file (normally cleaned up via
        an atexit hook that only runs at interpreter shutdown), so without this
        fixture, every test in this class would leak a file for the rest of the
        test session.
        """
        created: list[LanguageToolConfig] = []

        def _make(config: Mapping[str, ConfigValue]) -> LanguageToolConfig:
            cfg = LanguageToolConfig(config)
            created.append(cfg)
            return cfg

        yield _make

        for cfg in created:
            Path(cfg.path).unlink(missing_ok=True)

    def test_empty_config_raises(self) -> None:
        """Constructing with an empty dict raises ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            LanguageToolConfig({})

    def test_valid_config_creates_file(
        self, make_config: Callable[[Mapping[str, ConfigValue]], LanguageToolConfig]
    ) -> None:
        """A valid config creates a temporary .properties file on disk."""
        cfg = make_config({"cacheSize": 500})
        assert cfg.path
        assert Path(cfg.path).exists()

    def test_config_file_content(
        self, make_config: Callable[[Mapping[str, ConfigValue]], LanguageToolConfig]
    ) -> None:
        """The .properties file contains the expected key=value pair."""
        cfg = make_config({"cacheSize": 500})
        content = Path(cfg.path).read_text(encoding="utf-8")
        assert "cacheSize=500" in content

    def test_multiple_options(
        self, make_config: Callable[[Mapping[str, ConfigValue]], LanguageToolConfig]
    ) -> None:
        """Multiple config options all appear in the .properties file."""
        cfg = make_config({"cacheSize": 100, "pipelineCaching": True})
        content = Path(cfg.path).read_text(encoding="utf-8")
        assert "cacheSize=100" in content
        assert "pipelineCaching=true" in content

    def test_config_dict_stored(
        self, make_config: Callable[[Mapping[str, ConfigValue]], LanguageToolConfig]
    ) -> None:
        """The encoded config is stored on the .config attribute."""
        cfg = make_config({"cacheSize": 200})
        assert cfg.config == {"cacheSize": "200"}

    def test_boolean_config(
        self, make_config: Callable[[Mapping[str, ConfigValue]], LanguageToolConfig]
    ) -> None:
        """A boolean config value is encoded as 'true' or 'false'."""
        cfg = make_config({"premiumOnly": False})
        assert cfg.config == {"premiumOnly": "false"}

    def test_list_config(
        self, make_config: Callable[[Mapping[str, ConfigValue]], LanguageToolConfig]
    ) -> None:
        """A list config value is encoded as a comma-separated string."""
        cfg = make_config({"disabledRuleIds": ["RULE_A", "RULE_B"]})
        assert cfg.config["disabledRuleIds"] == "RULE_A,RULE_B"

    def test_lang_dict_path_end_to_end(
        self,
        make_config: Callable[[Mapping[str, ConfigValue]], LanguageToolConfig],
        tmp_path: Path,
    ) -> None:
        """A full LanguageToolConfig with a lang-xx-dictPath key writes it to disk."""
        cfg = make_config({"lang-en-dictPath": str(tmp_path)})
        content = Path(cfg.path).read_text(encoding="utf-8")
        assert "lang-en-dictPath=" in content
