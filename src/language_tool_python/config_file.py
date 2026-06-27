"""Module for configuring LanguageTool's local server."""

from __future__ import annotations

import atexit
import logging
import tempfile
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from os import PathLike
from pathlib import Path
from typing import TypeVar, cast

from ._internals.utils import SupportsBool
from .exceptions import PathError

__all__ = [
    "ConfigValue",
    "LanguageToolConfig",
]

ConfigValue = PathLike[str] | SupportsBool | str | int | float | Iterable[str]
"""Union of types accepted as values in the :class:`LanguageToolConfig` dictionary.

:class:`os.PathLike`\\ [:class:`str`], :class:`.SupportsBool`, :class:`str`,
:class:`int`, :class:`float`, :class:`collections.abc.Iterable`\\ [:class:`str`]
"""

_ConfigValueT = TypeVar("_ConfigValueT", bound=ConfigValue)

logger = logging.getLogger(__name__)

_LANGUAGE_KEY_PARTS = 2
_LANGUAGE_KEY_WITH_DICT_PATH_PARTS = 3
_LANGUAGE_DICT_PATH_SEPARATOR_COUNT = 2


def _reject_line_breaks(field_name: str, value: str) -> None:
    """Reject values that would break the one-option-per-line config format.

    :param field_name: The name of the configuration field being validated.
    :type field_name: str
    :param value: The value of the configuration field to validate.
    :type value: str
    :raises ValueError: If the value contains line break characters or ends with an odd
        number of backslashes.
    """
    if "\n" in value or "\r" in value:
        err = f"config {field_name} cannot contain line breaks"
        raise ValueError(err)

    trailing_backslashes = len(value) - len(value.rstrip("\\"))
    if trailing_backslashes % 2 == 1:
        err = f"config {field_name} cannot end with an odd number of backslashes"
        raise ValueError(err)


@dataclass(frozen=True)
class _OptionSpec:
    """Specification for a configuration option.

    This class defines the structure and behavior of a configuration option, including
    its type constraints, encoding mechanism, and optional validation.

    This class is frozen (immutable) to ensure configuration specifications remain
    constant throughout the application lifecycle.
    """

    py_types: type[object] | tuple[type[object], ...]
    """The Python type(s) that this option accepts."""

    encoder: Callable[[ConfigValue], str]
    """A callable that converts the option value to its string representation."""

    validator: Callable[[ConfigValue], None] | None = None
    """An optional validator function for the option value."""


def _option_spec(
    py_types: type[object] | tuple[type[object], ...],
    encoder: Callable[[_ConfigValueT], str],
    validator: Callable[[_ConfigValueT], None] | None = None,
) -> _OptionSpec:
    """Create a schema entry for a runtime-checked configuration option."""
    return _OptionSpec(
        py_types=py_types,
        encoder=cast("Callable[[ConfigValue], str]", encoder),
        validator=cast("Callable[[ConfigValue], None] | None", validator),
    )


def _bool_encoder(v: SupportsBool) -> str:
    """Encode a value as a lowercase boolean string.

    Converts any value to a boolean and returns its string representation in lowercase
    format ('true' or 'false').

    :param v: The value to be converted to a boolean string.
    :type v: SupportsBool
    :return: A lowercase string representation of the boolean value ('true' or 'false').
    :rtype: str
    """
    return str(bool(v)).lower()


def _int_encoder(v: int) -> str:
    """Encode an integer value as a string."""
    return str(int(v))


def _number_encoder(v: int | float) -> str:
    """Encode a numeric value as a string."""
    return str(float(v))


def _comma_list_encoder(v: str | Iterable[str]) -> str:
    """Encode a value as a comma-separated list string.

    Converts a value into a string representation suitable for comma-separated list
    configuration options. If the input is already a string, it is returned as-is. If
    it's an iterable, its elements are converted to strings and joined with commas.

    :param v: The value to encode. Can be a string or an iterable of values.
    :type v: str | collections.abc.Iterable[str]
    :return: A comma-separated string representation of the input value.
    :rtype: str
    """
    if isinstance(v, str):
        return v
    return ",".join(str(x) for x in v)


def _path_encoder(v: PathLike[str] | str) -> str:
    r"""Encode a path value to a string.

    Converts the input to a Path object, then to a string, and escapes all backslashes
    by doubling them. This is useful for windows file paths and other contexts where
    backslashes need to be escaped. (because they will be used by LT java binary)

    :param v: The path value to encode. Can be any type that Path accepts (str, Path,
        etc.).
    :type v: PathLike[str] | str
    :return: The path as a string with escaped backslashes (e.g., "C:\\Users\\file").
    :rtype: str
    """
    return str(Path(v)).replace("\\", "\\\\")


def _path_validator(v: PathLike[str] | str) -> None:
    """Validate that a given path exists and is a file or directory.

    :param v: The path to validate, which will be converted to a Path object
    :type v: PathLike[str] | str
    :raises PathError: If the path does not exist
    :raises PathError: If the path exists but is not a file or directory
    """
    p = Path(v)
    if not p.exists():
        err = f"path does not exist: {p}"
        raise PathError(err)
    if not p.is_file() and not p.is_dir():  # pragma: no cover
        err = f"path is not a file/directory: {p}"
        raise PathError(err)


_CONFIG_SCHEMA: dict[str, _OptionSpec] = {
    "maxTextLength": _option_spec(int, _int_encoder),
    "maxTextHardLength": _option_spec(int, _int_encoder),
    "maxCheckTimeMillis": _option_spec(int, _int_encoder),
    "maxErrorsPerWordRate": _option_spec((int, float), _number_encoder),
    "maxSpellingSuggestions": _option_spec(int, _int_encoder),
    "maxCheckThreads": _option_spec(int, _int_encoder),
    "cacheSize": _option_spec(int, _int_encoder),
    "cacheTTLSeconds": _option_spec(int, _int_encoder),
    "requestLimit": _option_spec(int, _int_encoder),
    "requestLimitInBytes": _option_spec(int, _int_encoder),
    "timeoutRequestLimit": _option_spec(int, _int_encoder),
    "requestLimitPeriodInSeconds": _option_spec(int, _int_encoder),
    "languageModel": _option_spec((str, Path), _path_encoder, _path_validator),
    "fasttextModel": _option_spec((str, Path), _path_encoder, _path_validator),
    "fasttextBinary": _option_spec((str, Path), _path_encoder, _path_validator),
    "maxWorkQueueSize": _option_spec(int, _int_encoder),
    "rulesFile": _option_spec((str, Path), _path_encoder, _path_validator),
    "blockedReferrers": _option_spec((str, list, tuple, set), _comma_list_encoder),
    "premiumOnly": _option_spec((bool, int), _bool_encoder),
    "disabledRuleIds": _option_spec((str, list, tuple, set), _comma_list_encoder),
    "pipelineCaching": _option_spec((bool, int), _bool_encoder),
    "maxPipelinePoolSize": _option_spec(int, _int_encoder),
    "pipelineExpireTimeInSeconds": _option_spec(int, _int_encoder),
    "pipelinePrewarming": _option_spec((bool, int), _bool_encoder),
    "trustXForwardForHeader": _option_spec((bool, int), _bool_encoder),
    "suggestionsEnabled": _option_spec((bool, int), _bool_encoder),
}


def _is_lang_key(key: str) -> bool:
    """Check if a given key is a valid language key.

    A valid language key must follow one of these formats:

        - lang-<code> where code is a non-empty language code
        - lang-<code>-dictPath where code is a non-empty language code

    :param key: The key string to validate
    :type key: str
    :return: True if the key is a valid language key, False otherwise
    :rtype: bool
    """
    if not key.startswith("lang-"):
        return False

    parts = key.split("-")
    return (len(parts) == _LANGUAGE_KEY_PARTS and len(parts[1]) > 0) or (  # lang-<code>
        len(parts) == _LANGUAGE_KEY_WITH_DICT_PATH_PARTS
        and len(parts[1]) > 0
        and parts[2] == "dictPath"  # lang-<code>-dictPath
    )


def _encode_config(config: Mapping[str, ConfigValue]) -> dict[str, str]:
    """Encode configuration dictionary values to their string representations.

    This function converts a configuration dictionary into a format suitable for
    serialization by encoding each value according to its corresponding schema
    specification.

    :param config: A dictionary containing configuration keys and values to be encoded.
    :type config: collections.abc.Mapping[str, ConfigValue]
    :return: A dictionary with the same keys but with all values encoded as strings.
    :rtype: dict[str, str]
    :raises ValueError: If a key in the config is not found in the CONFIG_SCHEMA and is
        not a language key, or if a key/value cannot be serialized safely.
    :raises TypeError: If a value's type does not match the expected type(s) defined in
        the CONFIG_SCHEMA specification.
    :raises PathError: If a path-like configuration value does not point to an existing
        file.
    """
    logger.debug("Encoding LanguageTool config with keys: %s", list(config.keys()))
    encoded: dict[str, str] = {}
    for key, value in config.items():
        _reject_line_breaks("key", key)
        if _is_lang_key(key) and key.count("-") == 1:  # lang-<code>
            logger.debug("Encoding language option %s=%r", key, value)
            encoded[key] = str(value)
            _reject_line_breaks(key, encoded[key])
            continue
        if (
            _is_lang_key(key) and key.count("-") == _LANGUAGE_DICT_PATH_SEPARATOR_COUNT
        ):  # lang-<code>-dictPath
            logger.debug("Encoding language dictPath %s=%r", key, value)
            path_value = cast("PathLike[str] | str", value)
            _path_validator(path_value)
            encoded[key] = _path_encoder(path_value)
            _reject_line_breaks(key, encoded[key])
            continue

        spec = _CONFIG_SCHEMA.get(key)
        if spec is None:
            err = f"unexpected key in config: {key}"
            raise ValueError(err)

        if not isinstance(value, spec.py_types):
            err = f"invalid type for {key}: {type(value).__name__}"
            raise TypeError(err)
        if spec.validator is not None:
            spec.validator(value)
        encoded[key] = spec.encoder(value)
        _reject_line_breaks(key, encoded[key])
    return encoded


class LanguageToolConfig:
    """Configuration class for LanguageTool.

    :param config: Dictionary containing configuration keys and values.
    :type config: collections.abc.Mapping[str, ConfigValue]
    """

    config: dict[str, str]
    """Dictionary containing configuration keys and values."""

    path: str
    """Path to the temporary file storing the configuration."""

    def __init__(self, config: Mapping[str, ConfigValue]) -> None:
        """Initialize the LanguageToolConfig object.

        :raises ValueError: If the config is empty or contains invalid keys/values.
        :raises TypeError: If a config value has an unsupported type.
        :raises PathError: If a path-like config value does not point to an existing
            file.
        """
        if not config:
            err = "config cannot be empty"
            raise ValueError(err)

        self.config = _encode_config(config)
        self.path = self._create_temp_file()

    def _create_temp_file(self) -> str:
        """Create a temporary file to store the configuration.

        :return: Path to the temporary file.
        :rtype: str
        """
        with tempfile.NamedTemporaryFile(
            mode="w",
            delete=False,
            encoding="utf-8",
        ) as tmp_file:
            # Write key=value entries as lines in temporary file.
            for key, value in self.config.items():
                tmp_file.write(f"{key}={value}\n")
            temp_name = tmp_file.name

        logger.debug("Created temporary LanguageTool config file at %s", temp_name)

        # Remove file when program exits.
        atexit.register(lambda: Path(temp_name).unlink(missing_ok=True))

        return temp_name
