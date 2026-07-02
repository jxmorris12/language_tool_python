"""Integration tests for LanguageTool configuration options (require a local server)."""

import re

import pytest

import language_tool_python
from language_tool_python.exceptions import LanguageToolError


def test_langtool_languages() -> None:
    """Test that LanguageTool supports the expected set of languages.

    This test verifies that the LanguageTool instance correctly identifies and returns
    all expected supported languages, including various regional variants and language
    codes.

    :raises AssertionError: If the supported languages do not include all expected
        languages.
    """
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
    """Test the maxTextLength configuration parameter.

    This test verifies that LanguageTool correctly enforces the maximum text length
    limit specified in the configuration, raising an error for texts exceeding the limit
    while successfully checking texts within the limit.

    :raises AssertionError: If the tool does not raise an error for text exceeding the
        limit or fails to check text within the limit.
    """
    with language_tool_python.LanguageTool(
        "en-US",
        config={"maxTextLength": 12},
    ) as tool:
        # With this config file, checking text with >12 characters should raise an error
        error_msg = re.escape(
            (
                "Error: Your text exceeds the limit of 12 characters (it's 27 "
                "characters). Please submit a shorter text."
            ),
        )
        with pytest.raises(LanguageToolError, match=error_msg):
            tool.check("Hello darkness my old frend")
        # But checking shorter text should work fine.
        # (should have 1 match for this one)
        assert len(tool.check("Hello darkne"))


def test_config_caching() -> None:
    """Test that the caching configuration parameters are accepted by the server.

    This test verifies that LanguageTool starts successfully and correctly checks
    text when configured with ``cacheSize`` and ``pipelineCaching``, including when
    the same sentence is checked twice in a row (the second call takes the cache
    hit code path server-side).

    The actual speedup these options provide is a wall-clock measurement, which is
    too noisy on shared CI runners to gate pass/fail on: it belongs in the
    ``perf``-marked benchmark suite (see ``test_bench_check_with_pipeline_cache`` in
    ``tests/benchmarks/test_bench_check.py``), which is opt-in and does not affect
    CI results.

    :raises AssertionError: If the tool fails to produce matches under this config.
    """
    with language_tool_python.LanguageTool(
        "en-US",
        config={"cacheSize": 1000, "pipelineCaching": True},
    ) as tool:
        s = "hello darkness my old frend"
        assert len(tool.check(s)) > 0
        # Second check of the same sentence exercises the cache-hit path.
        assert len(tool.check(s)) > 0


def test_inexistent_language() -> None:
    """Test that creating a LanguageTag with an invalid language code raises an error.

    This test verifies that the LanguageTag constructor correctly validates language
    codes and raises a ValueError when given a language code that is not supported.
    A real server is required here to obtain the list of supported languages via
    ``tool._get_languages()``.

    :raises AssertionError: If ValueError is not raised for an invalid language code.
    """
    with (
        language_tool_python.LanguageTool("en-US") as tool,
        pytest.raises(ValueError, match="unsupported language"),
    ):
        language_tool_python.LanguageTag("xx-XX", tool._get_languages())


def test_disabled_rule_in_config() -> None:
    """Test the disabledRuleIds configuration parameter.

    This test verifies that LanguageTool correctly disables specific grammar rules when
    specified in the configuration. The test checks text that would normally trigger the
    disabled rule and confirms that no matches are returned.

    :raises AssertionError: If the disabled rule still produces matches.
    """
    grammar_tool_config = {"disabledRuleIds": ["MORFOLOGIK_RULE_EN_US"]}
    with language_tool_python.LanguageTool("en-US", config=grammar_tool_config) as tool:
        text = "He realised that the organization was in jeopardy."
        matches = tool.check(text)
        assert len(matches) == 0
