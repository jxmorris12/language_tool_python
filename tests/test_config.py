"""Tests for the configuration options of LanguageTool."""

import re
import time

import pytest

from language_tool_python.exceptions import LanguageToolError


def test_langtool_languages() -> None:
    """
    Test that LanguageTool supports the expected set of languages.
    This test verifies that the LanguageTool instance correctly identifies
    and returns all expected supported languages, including various regional
    variants and language codes.

    :raises AssertionError: If the supported languages do not include all expected languages.
    """
    import language_tool_python

    with language_tool_python.LanguageTool("en-US") as tool:
        assert tool._get_languages().issuperset(
            {
                "es-AR",
                "ast-ES",
                "fa",
                "ar",
                "ja",
                "pl",
                "en-ZA",
                "sl",
                "be-BY",
                "gl",
                "de-DE-x-simple-language-DE",
                "ga",
                "da-DK",
                "ca-ES-valencia",
                "eo",
                "pt-PT",
                "ro",
                "fr-FR",
                "sv-SE",
                "br-FR",
                "es-ES",
                "be",
                "de-CH",
                "pl-PL",
                "it-IT",
                "de-DE-x-simple-language",
                "en-NZ",
                "sv",
                "auto",
                "km",
                "pt",
                "da",
                "ta-IN",
                "de",
                "fa-IR",
                "ca",
                "de-AT",
                "de-DE",
                "sk",
                "ta",
                "uk",
                "en-US",
                "zh",
                "uk-UA",
                "pt-AO",
                "el-GR",
                "br",
                "ca-ES-balear",
                "fr",
                "sk-SK",
                "pt-BR",
                "ro-RO",
                "it",
                "es",
                "ru-RU",
                "km-KH",
                "en-GB",
                "sl-SI",
                "gl-ES",
                "pt-MZ",
                "nl",
                "el",
                "ca-ES",
                "zh-CN",
                "de-LU",
                "nl-NL",
                "ja-JP",
                "ast",
                "tl",
                "ga-IE",
                "en-AU",
                "en",
                "ru",
                "nl-BE",
                "en-CA",
                "tl-PH",
            },
        )


def test_config_text_length() -> None:
    """
    Test the maxTextLength configuration parameter.
    This test verifies that LanguageTool correctly enforces the maximum text length
    limit specified in the configuration, raising an error for texts exceeding the
    limit while successfully checking texts within the limit.

    :raises AssertionError: If the tool does not raise an error for text exceeding the limit
                           or fails to check text within the limit.
    """
    import language_tool_python

    with language_tool_python.LanguageTool(
        "en-US",
        config={"maxTextLength": 12},
    ) as tool:
        # With this config file, checking text with >12 characters should raise an error.
        error_msg = re.escape(
            "Error: Your text exceeds the limit of 12 characters (it's 27 characters). Please submit a shorter text.",
        )
        with pytest.raises(LanguageToolError, match=error_msg):
            tool.check("Hello darkness my old frend")
        # But checking shorter text should work fine.
        # (should have 1 match for this one)
        assert len(tool.check("Hello darkne"))


def test_config_caching() -> None:
    """
    Test the caching configuration parameters.
    This test verifies that LanguageTool's caching mechanism (cacheSize and pipelineCaching)
    significantly improves performance when checking the same text multiple times. The test
    measures the time difference between the first and second checks to ensure caching
    provides a substantial speedup.

    :raises AssertionError: If caching does not provide the expected performance improvement.
    """
    import language_tool_python

    with language_tool_python.LanguageTool(
        "en-US",
        config={"cacheSize": 1000, "pipelineCaching": True},
    ) as tool:
        s = "hello darkness my old frend"
        t1 = time.time()
        tool.check(s)
        t2 = time.time()
        tool.check(s)
        t3 = time.time()

        # This is a silly test that says: caching should speed up a grammar-checking by a factor
        # of speed_factor when checking the same sentence twice. It theoretically could be very flaky.
        # But in practice I've observed speedup of around 250x (6.76s to 0.028s).
        speedup_factor = 10.0
        assert (t2 - t1) / speedup_factor > (t3 - t2)


def test_disabled_rule_in_config() -> None:
    """
    Test the disabledRuleIds configuration parameter.
    This test verifies that LanguageTool correctly disables specific grammar rules
    when specified in the configuration. The test checks text that would normally
    trigger the disabled rule and confirms that no matches are returned.

    :raises AssertionError: If the disabled rule still produces matches.
    """
    import language_tool_python

    grammar_tool_config = {"disabledRuleIds": ["MORFOLOGIK_RULE_EN_US"]}
    with language_tool_python.LanguageTool("en-US", config=grammar_tool_config) as tool:
        text = "He realised that the organization was in jeopardy."
        matches = tool.check(text)
        assert len(matches) == 0
