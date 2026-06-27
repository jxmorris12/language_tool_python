"""Unit tests for LanguageToolConfig input validation and injection protection."""

import pytest

from language_tool_python.config_file import ConfigValue, LanguageToolConfig


@pytest.mark.parametrize(
    "config",
    [
        {"blockedReferrers": "example.com\ntrustXForwardForHeader=true"},
        {"disabledRuleIds": ["MORFOLOGIK_RULE_EN_US", "SAFE\rrequestLimit=0"]},
        {"lang-en\ntrustXForwardForHeader": "true"},
        {"lang-en": "custom-word\nrequestLimit=0"},
    ],
)
def test_config_rejects_line_break_injection(config: dict[str, ConfigValue]) -> None:
    """Test that config serialization cannot be escaped with CR/LF characters."""
    with pytest.raises(ValueError, match="cannot contain line breaks"):
        LanguageToolConfig(config)


@pytest.mark.parametrize(
    "config",
    [
        {"blockedReferrers": "example.com\\"},
        {"disabledRuleIds": ["MORFOLOGIK_RULE_EN_US", "SAFE\\"]},
        {"lang-en\\": "true"},
        {"lang-en": "custom-word\\"},
    ],
)
def test_config_rejects_odd_trailing_backslashes(
    config: dict[str, ConfigValue],
) -> None:
    """Test that config serialization cannot escape the line ending with a backslash."""
    with pytest.raises(ValueError, match="odd number of backslashes"):
        LanguageToolConfig(config)
