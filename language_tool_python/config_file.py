"""Module for configuring LanguageTool's local server."""

import atexit
import logging
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Optional, Tuple, Union

from .exceptions import PathError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class OptionSpec:
    """
    Specification for a configuration option.

    This class defines the structure and behavior of a configuration option,
    including its type constraints, encoding mechanism, and optional validation.

    This class is frozen (immutable) to ensure configuration specifications
    remain constant throughout the application lifecycle.
    """

    py_types: Union[type, Tuple[type, ...]]
    """The Python type(s) that this option accepts."""

    encoder: Callable[[Any], str]
    """A callable that converts the option value to its string representation."""

    validator: Optional[Callable[[Any], None]] = None
    """An optional validator function for the option value."""


def _bool_encoder(v: Any) -> str:
    """
    Encode a value as a lowercase boolean string.

    Converts any value to a boolean and returns its string representation
    in lowercase format ('true' or 'false').

    :param v: The value to be converted to a boolean string.
    :type v: Any
    :return: A lowercase string representation of the boolean value ('true' or 'false').
    :rtype: str
    """
    return str(bool(v)).lower()


def _comma_list_encoder(v: Union[str, Iterable[str]]) -> str:
    """
    Encode a value as a comma-separated list string.

    Converts a value into a string representation suitable for comma-separated
    list configuration options. If the input is already a string, it is returned
    as-is. If it's an iterable, its elements are converted to strings and joined
    with commas.

    :param v: The value to encode. Can be a string or an iterable of values.
    :type v: Union[str, Iterable[str]]
    :return: A comma-separated string representation of the input value.
    :rtype: str
    """
    if isinstance(v, str):
        return v
    return ",".join(str(x) for x in v)


def _path_encoder(v: Any) -> str:
    """
    Encode a path value to a string.
    Converts the input to a Path object, then to a string, and escapes all
    backslashes by doubling them. This is useful for windows file paths and
    other contexts where backslashes need to be escaped. (because they will
    be used by LT java binary)

    :param v: The path value to encode. Can be any type that Path accepts
        (str, Path, etc.).
    :type v: Any
    :return: The path as a string with escaped backslashes (e.g., "C:\\\\Users\\\\file").
    :rtype: str
    """
    return str(Path(v)).replace("\\", "\\\\")


def _path_validator(v: Any) -> None:
    """
    Validate that a given path exists and is a file.

    :param v: The path to validate, which will be converted to a Path object
    :type v: Any
    :raises PathError: If the path does not exist
    :raises PathError: If the path exists but is not a file
    """
    p = Path(v)
    if not p.exists():
        err = f"path does not exist: {p}"
        raise PathError(err)
    if not p.is_file():
        err = f"path is not a file: {p}"
        raise PathError(err)


CONFIG_SCHEMA: Dict[str, OptionSpec] = {
    "maxTextLength": OptionSpec(int, lambda v: str(int(v))),
    "maxTextHardLength": OptionSpec(int, lambda v: str(int(v))),
    "maxCheckTimeMillis": OptionSpec(int, lambda v: str(int(v))),
    "maxErrorsPerWordRate": OptionSpec((int, float), lambda v: str(float(v))),
    "maxSpellingSuggestions": OptionSpec(int, lambda v: str(int(v))),
    "maxCheckThreads": OptionSpec(int, lambda v: str(int(v))),
    "cacheSize": OptionSpec(int, lambda v: str(int(v))),
    "cacheTTLSeconds": OptionSpec(int, lambda v: str(int(v))),
    "requestLimit": OptionSpec(int, lambda v: str(int(v))),
    "requestLimitInBytes": OptionSpec(int, lambda v: str(int(v))),
    "timeoutRequestLimit": OptionSpec(int, lambda v: str(int(v))),
    "requestLimitPeriodInSeconds": OptionSpec(int, lambda v: str(int(v))),
    "languageModel": OptionSpec((str, Path), _path_encoder, _path_validator),
    "fasttextModel": OptionSpec((str, Path), _path_encoder, _path_validator),
    "fasttextBinary": OptionSpec((str, Path), _path_encoder, _path_validator),
    "maxWorkQueueSize": OptionSpec(int, lambda v: str(int(v))),
    "rulesFile": OptionSpec((str, Path), _path_encoder, _path_validator),
    "blockedReferrers": OptionSpec((str, list, tuple, set), _comma_list_encoder),
    "premiumOnly": OptionSpec((bool, int), _bool_encoder),
    "disabledRuleIds": OptionSpec((str, list, tuple, set), _comma_list_encoder),
    "pipelineCaching": OptionSpec((bool, int), _bool_encoder),
    "maxPipelinePoolSize": OptionSpec(int, lambda v: str(int(v))),
    "pipelineExpireTimeInSeconds": OptionSpec(int, lambda v: str(int(v))),
    "pipelinePrewarming": OptionSpec((bool, int), _bool_encoder),
    "trustXForwardForHeader": OptionSpec((bool, int), _bool_encoder),
    "suggestionsEnabled": OptionSpec((bool, int), _bool_encoder),
}


def _is_lang_key(key: str) -> bool:
    """
    Check if a given key is a valid language key.
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
    return (len(parts) == 2 and len(parts[1]) > 0) or (  # lang-<code>
        len(parts) == 3
        and len(parts[1]) > 0
        and parts[2] == "dictPath"  # lang-<code>-dictPath
    )


def _encode_config(config: Dict[str, Any]) -> Dict[str, str]:
    """
    Encode configuration dictionary values to their string representations.
    This function converts a configuration dictionary into a format suitable for
    serialization by encoding each value according to its corresponding schema
    specification.

    :param config: A dictionary containing configuration keys and values to be encoded.
    :type config: Dict[str, Any]
    :return: A dictionary with the same keys but with all values encoded as strings.
    :rtype: Dict[str, str]
    :raises ValueError: If a key in the config is not found in the CONFIG_SCHEMA and
                       is not a language key.
    :raises TypeError: If a value's type does not match the expected type(s) defined
                      in the CONFIG_SCHEMA specification.
    """
    logger.debug("Encoding LanguageTool config with keys: %s", list(config.keys()))
    encoded: Dict[str, str] = {}
    for key, value in config.items():
        if _is_lang_key(key) and key.count("-") == 1:  # lang-<code>
            logger.debug("Encoding language option %s=%r", key, value)
            encoded[key] = str(value)
            continue
        if _is_lang_key(key) and key.count("-") == 2:  # lang-<code>-dictPath
            logger.debug("Encoding language dictPath %s=%r", key, value)
            _path_validator(value)
            encoded[key] = _path_encoder(value)
            continue

        spec = CONFIG_SCHEMA.get(key)
        if spec is None:
            err = f"unexpected key in config: {key}"
            raise ValueError(err)

        if not isinstance(value, spec.py_types):
            err = f"invalid type for {key}: {type(value).__name__}"
            raise TypeError(err)
        if spec.validator is not None:
            spec.validator(value)
        encoded[key] = spec.encoder(value)
    return encoded


class LanguageToolConfig:
    """
    Configuration class for LanguageTool.

    :param config: Dictionary containing configuration keys and values.
    :type config: Dict[str, Any]
    """

    config: Dict[str, Any]
    """Dictionary containing configuration keys and values."""

    path: str
    """Path to the temporary file storing the configuration."""

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the LanguageToolConfig object.
        """
        if not config:
            err = "config cannot be empty"
            raise ValueError(err)

        self.config = _encode_config(config)
        self.path = self._create_temp_file()

    def _create_temp_file(self) -> str:
        """
        Create a temporary file to store the configuration.

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
