"""Tests for the Match functionality of LanguageTool."""

from typing import Any, Dict, List


def test_langtool_load() -> None:
    """
    Test the basic functionality of LanguageTool and Match object attributes.
    This test verifies that LanguageTool correctly identifies grammar and spelling errors
    in a given text and that Match objects contain all expected attributes with correct values,
    including rule_id, message, replacements, offsets, category, and sentence information.

    :raises AssertionError: If the detected matches do not match the expected output or
                           if Match object attributes are incorrect.
    """
    import language_tool_python

    with language_tool_python.LanguageTool("en-US") as tool:
        matches = tool.check("ain't nothin but a thang")

        expected_matches: List[Dict[str, Any]] = [
            {
                "rule_id": "UPPERCASE_SENTENCE_START",
                "message": "This sentence does not start with an uppercase letter.",
                "replacements": ["Ai"],
                "offset_in_context": 0,
                "context": "ain't nothin but a thang",
                "offset": 0,
                "error_length": 2,
                "category": "CASING",
                "rule_issue_type": "typographical",
                "sentence": "ain't nothin but a thang",
            },
            {
                "rule_id": "MORFOLOGIK_RULE_EN_US",
                "message": "Possible spelling mistake found.",
                "replacements": ["nothing", "no thin"],
                "offset_in_context": 6,
                "context": "ain't nothin but a thang",
                "offset": 6,
                "error_length": 6,
                "category": "TYPOS",
                "rule_issue_type": "misspelling",
                "sentence": "ain't nothin but a thang",
            },
            {
                "rule_id": "MORFOLOGIK_RULE_EN_US",
                "message": "Possible spelling mistake found.",
                "replacements": [
                    "than",
                    "thing",
                    "Zhang",
                    "hang",
                    "thank",
                    "Chang",
                    "tang",
                    "thong",
                    "twang",
                    "Thant",
                    "thane",
                    "Jhang",
                    "Shang",
                    "Thanh",
                    "bhang",
                ],
                "offset_in_context": 19,
                "context": "ain't nothin but a thang",
                "offset": 19,
                "error_length": 5,
                "category": "TYPOS",
                "rule_issue_type": "misspelling",
                "sentence": "ain't nothin but a thang",
            },
        ]

        assert len(matches) == len(expected_matches)
        for match_i, match in enumerate(matches):
            assert isinstance(match, language_tool_python.Match)
            for key in [
                "rule_id",
                "message",
                "offset_in_context",
                "context",
                "offset",
                "error_length",
                "category",
                "rule_issue_type",
                "sentence",
            ]:
                assert expected_matches[match_i][key] == getattr(match, key)

            # For replacements we allow some flexibility in the order
            # of the suggestions depending on the version of LT.
            for key in [
                "replacements",
            ]:
                assert set(expected_matches[match_i][key]) == set(getattr(match, key))


def test_match() -> None:
    """
    Test the string representation of Match objects.
    This test verifies that Match objects can be correctly converted to a human-readable
    string format that includes the offset, length, rule ID, error message, suggestions,
    and contextual visualization of the error location.

    :raises AssertionError: If the Match string representation does not match the expected format.
    """
    import language_tool_python

    with language_tool_python.LanguageTool("en-US") as tool:
        text = "A sentence with a error in the Hitchhiker’s Guide tot he Galaxy"
        matches = tool.check(text)
        assert len(matches) == 2
        assert str(matches[0]) == (
            "Offset 16, length 1, Rule ID: EN_A_VS_AN\n"
            "Message: Use “an” instead of ‘a’ if the following word starts with a vowel sound, e.g. ‘an article’, ‘an hour’.\n"
            "Suggestion: an\n"
            "A sentence with a error in the Hitchhiker’s Guide tot he ..."
            "\n                ^"
        )


def test_correct_en_us() -> None:
    """
    Test the automatic correction functionality for US English text.
    This test verifies that LanguageTool can automatically correct grammar and spelling
    errors in a given text using US English rules, replacing errors with suggested corrections.

    :raises AssertionError: If the corrected text does not match the expected output.
    """
    import language_tool_python

    with language_tool_python.LanguageTool("en-US") as tool:
        matches = tool.check("cz of this brand is awsome,,i love this brand very much")
        assert len(matches) == 4

        assert (
            tool.correct("cz of this brand is awsome,,i love this brand very much")
            == "CZ of this brand is awesome,I love this brand very much"
        )


def test_spellcheck_en_gb() -> None:
    """
    Test the spell-checking enable/disable functionality for British English.
    This test verifies that LanguageTool can toggle spell-checking on and off, demonstrating
    that disabling spell-checking prevents spelling corrections while grammar corrections
    may still be applied.

    :raises AssertionError: If the corrected text does not behave as expected when
                           spell-checking is enabled or disabled.
    """
    import language_tool_python

    s = "Wat is wrong with the spll chker"

    # Correct a sentence with spell-checking
    with language_tool_python.LanguageTool("en-GB") as tool:
        assert tool.correct(s) == "Was is wrong with the sell cheer"

        # Correct a sentence without spell-checking
        tool.disable_spellchecking()
        assert tool.correct(s) == "Wat is wrong with the spll chker"


def test_special_char_in_text() -> None:
    """
    Test that LanguageTool correctly handles text containing special characters and emojis.
    This test verifies that the tool can identify and correct errors in text that includes
    Unicode characters such as emojis, ensuring proper offset calculation and error detection
    despite the presence of multi-byte characters.

    :raises AssertionError: If the corrected text does not match the expected output or
                           if special characters are not handled correctly.
    """
    import language_tool_python

    with language_tool_python.LanguageTool("en-US") as tool:
        text = "The sun was seting 🌅, casting a warm glow over the park. Birds chirpped softly 🐦 as the day slowly fade into night."
        assert (
            tool.correct(text)
            == "The sun was setting 🌅, casting a warm glow over the park. Birds chipped softly 🐦 as the day slowly fade into night."
        )


def test_check_with_regex() -> None:
    """
    Test the check_matching_regions method for selective grammar checking.
    This test verifies that LanguageTool can limit its grammar checking to specific
    regions of text defined by a regular expression, allowing for targeted error detection.
    Additionally, the test is performed with some special characters in the text to ensure
    correct handling of offsets.

    :raises AssertionError: If the detected matches do not correspond to the specified regions.
    """
    import language_tool_python

    with language_tool_python.LanguageTool("en-US") as tool:
        text = '❗ He said "❗ I has a problem" but she replied ❗ "It are fine ❗".'
        matches = tool.check_matching_regions(text, r'"[^"]*"')

        assert len(matches) == 2
        assert (
            language_tool_python.utils.correct(text, matches)
            == '❗ He said "❗ I have a problem" but she replied ❗ "It is fine ❗".'
        )
