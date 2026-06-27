"""Unit tests for config_file.py encoders, validators, and LanguageToolConfig."""

from __future__ import annotations

from pathlib import Path

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
)
from language_tool_python.exceptions import PathError


class TestBoolEncoder:
    """Tests for the _bool_encoder() function."""

    def test_true(self) -> None:
        """True is encoded as the string 'true'."""
        assert _bool_encoder(v=True) == "true"

    def test_false(self) -> None:
        """False is encoded as the string 'false'."""
        assert _bool_encoder(v=False) == "false"

    def test_truthy_int(self) -> None:
        """A truthy integer is encoded as 'true'."""
        assert _bool_encoder(1) == "true"

    def test_falsy_int(self) -> None:
        """A falsy integer is encoded as 'false'."""
        assert _bool_encoder(0) == "false"


class TestIntEncoder:
    """Tests for the _int_encoder() function."""

    def test_positive(self) -> None:
        """A positive integer is converted to its decimal string."""
        assert _int_encoder(42) == "42"

    def test_zero(self) -> None:
        """Zero is converted to '0'."""
        assert _int_encoder(0) == "0"


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

    def test_string_passthrough(self) -> None:
        """A plain string is returned unchanged."""
        assert _comma_list_encoder("a,b,c") == "a,b,c"

    def test_list_joined(self) -> None:
        """A list of strings is joined with commas."""
        assert _comma_list_encoder(["a", "b", "c"]) == "a,b,c"

    def test_tuple_joined(self) -> None:
        """A tuple of strings is joined with commas."""
        assert _comma_list_encoder(("x", "y")) == "x,y"

    def test_single_item(self) -> None:
        """A single-element list returns the element without a comma."""
        assert _comma_list_encoder(["only"]) == "only"


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


class TestIsLangKey:
    """Tests for the _is_lang_key() predicate."""

    def test_lang_code_format(self) -> None:
        """A key of the form 'lang-XX' is recognized as a language key."""
        assert _is_lang_key("lang-en") is True

    def test_lang_code_dict_path_format(self) -> None:
        """A key of the form 'lang-XX-dictPath' is recognized as a language key."""
        assert _is_lang_key("lang-en-dictPath") is True

    def test_not_lang_prefix(self) -> None:
        """A key without the 'lang-' prefix is not a language key."""
        assert _is_lang_key("cacheSize") is False

    def test_lang_only_no_code(self) -> None:
        """'lang-' with no language code is not a valid language key."""
        assert _is_lang_key("lang-") is False

    def test_lang_too_many_parts(self) -> None:
        """A key with more than three parts is not a valid language key."""
        assert _is_lang_key("lang-en-dictPath-extra") is False


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

    def test_empty_config_raises(self) -> None:
        """Constructing with an empty dict raises ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            LanguageToolConfig({})

    def test_valid_config_creates_file(self) -> None:
        """A valid config creates a temporary .properties file on disk."""
        cfg = LanguageToolConfig({"cacheSize": 500})
        assert cfg.path
        assert Path(cfg.path).exists()

    def test_config_file_content(self) -> None:
        """The .properties file contains the expected key=value pair."""
        cfg = LanguageToolConfig({"cacheSize": 500})
        content = Path(cfg.path).read_text(encoding="utf-8")
        assert "cacheSize=500" in content

    def test_multiple_options(self) -> None:
        """Multiple config options all appear in the .properties file."""
        cfg = LanguageToolConfig({"cacheSize": 100, "pipelineCaching": True})
        content = Path(cfg.path).read_text(encoding="utf-8")
        assert "cacheSize=100" in content
        assert "pipelineCaching=true" in content

    def test_config_dict_stored(self) -> None:
        """The encoded config is stored on the .config attribute."""
        cfg = LanguageToolConfig({"cacheSize": 200})
        assert cfg.config == {"cacheSize": "200"}

    def test_boolean_config(self) -> None:
        """A boolean config value is encoded as 'true' or 'false'."""
        cfg = LanguageToolConfig({"premiumOnly": False})
        assert cfg.config == {"premiumOnly": "false"}

    def test_list_config(self) -> None:
        """A list config value is encoded as a comma-separated string."""
        cfg = LanguageToolConfig({"disabledRuleIds": ["RULE_A", "RULE_B"]})
        assert cfg.config["disabledRuleIds"] == "RULE_A,RULE_B"
