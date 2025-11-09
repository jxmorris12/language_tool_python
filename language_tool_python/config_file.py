"""Module for configuring LanguageTool's local server."""

import atexit
import os
import tempfile
from typing import Any, Dict

# Allowed configuration keys for LanguageTool.
ALLOWED_CONFIG_KEYS = {
    "maxTextLength",
    "maxTextHardLength",
    "maxCheckTimeMillis",
    "maxErrorsPerWordRate",
    "maxSpellingSuggestions",
    "maxCheckThreads",
    "cacheSize",
    "cacheTTLSeconds",
    "requestLimit",
    "requestLimitInBytes",
    "timeoutRequestLimit",
    "requestLimitPeriodInSeconds",
    "languageModel",
    "fasttextModel",
    "fasttextBinary",
    "maxWorkQueueSize",
    "rulesFile",
    "blockedReferrers",
    "premiumOnly",
    "disabledRuleIds",
    "pipelineCaching",
    "maxPipelinePoolSize",
    "pipelineExpireTimeInSeconds",
    "pipelinePrewarming",
    "trustXForwardForHeader",
    "suggestionsEnabled",
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
    return (len(parts) == 2 and len(parts[1]) > 0) or (
        len(parts) == 3 and len(parts[1]) > 0 and parts[2] == "dictPath"
    )


def _validate_config_keys(config: Dict[str, Any]) -> None:
    """
    Validate that all keys in the configuration dictionary are allowed.

    :param config: Dictionary containing configuration keys and values.
    :type config: Dict[str, Any]
    :raises ValueError: If a key is found that is not in ALLOWED_CONFIG_KEYS and is not a language key.
    """
    for key in config:
        if key not in ALLOWED_CONFIG_KEYS and not _is_lang_key(key):
            raise ValueError(f"unexpected key in config: {key}")


class LanguageToolConfig:
    """
    Configuration class for LanguageTool.

    :param config: Dictionary containing configuration keys and values.
    :type config: Dict[str, Any]

    Attributes:
        config (Dict[str, Any]): Dictionary containing configuration keys and values.
        path (str): Path to the temporary file storing the configuration.
    """

    config: Dict[str, Any]
    path: str

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the LanguageToolConfig object.
        """
        if not config:
            raise ValueError("config cannot be empty")
        _validate_config_keys(config)

        self.config = config

        if "disabledRuleIds" in self.config:
            self.config["disabledRuleIds"] = ",".join(self.config["disabledRuleIds"])
        if "blockedReferrers" in self.config:
            self.config["blockedReferrers"] = ",".join(self.config["blockedReferrers"])
        for key in [
            "pipelineCaching",
            "premiumOnly",
            "pipelinePrewarming",
            "trustXForwardForHeader",
            "suggestionsEnabled",
        ]:
            if key in self.config:
                self.config[key] = str(bool(self.config[key])).lower()

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

        # Remove file when program exits.
        atexit.register(lambda: os.unlink(temp_name))

        return temp_name
