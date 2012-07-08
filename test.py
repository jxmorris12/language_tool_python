#!/usr/bin/env python3
"""Test suite for language_tool
"""
import unittest
from collections import namedtuple
import warnings

import language_tool
from language_tool.country_codes import get_country_code


class TestLanguageTool(unittest.TestCase):
    Test = namedtuple("Test", ("text", "matches"))
    Match = namedtuple("Match", ("fromy", "fromx", "ruleId"))

    tests = {
        "en": [
            Test(
                ("Paste your own text here... or check this text too see "
                 "a few of the problems that that LanguageTool can detect. "
                 "Did you notice that their is no spelcheckin included?"),
                [
                    Match(0, 47, "TOO_TO"),
                    Match(0, 132, "THEIR_IS"),
                ]
            ),
        ],
        "fr": [
            Test(
                ("Se texte est un exemple pour pour vous montrer "
                 "le fonctionnement de LanguageTool. "
                 "notez que LanguageTool ne comporte pas "
                 "de correcteur orthographique."),
                [
                    Match(0, 0, "SE_CE"),
                    Match(0, 3, "TE_NV"),
                    Match(0, 24, "FRENCH_WORD_REPEAT_RULE"),
                    Match(0, 82, "UPPERCASE_SENTENCE_START"),
                ]
            ),
            Test(
                "C'est un soucis, comme même!",
                [
                    Match(0, 6, "ACCORD_NOMBRE"),
                    Match(0, 17, "COMME_MEME"),
                    Match(0, 23, "FRENCH_WHITESPACE"),
                ]
            ),
        ],
        "ja": [
            Test("日本語", []),
        ],
    }

    def test_samples(self):
        languages = language_tool.get_languages()
        for language, tests in self.tests.items():
            if language not in languages:
                version = language_tool.get_version()
                warnings.warn(
                    "LanguageTool {} doesn’t support language {!r}"
                    .format(version, language)
                )
                continue
            lang_tool = language_tool.LanguageTool(language)
            for text, expected_matches in tests:
                matches = lang_tool.check(text)
                for expected_match in expected_matches:
                    for match in matches:
                        if (
                            (match.fromy, match.fromx, match.ruleId) ==
                            (expected_match.fromy, expected_match.fromx,
                             expected_match.ruleId)
                        ):
                            break
                    else:
                        raise IndexError(
                            "can’t find {!r}".format(expected_match))

    def test_languages(self):
        languages = language_tool.get_languages()
        self.assertIn("en", languages)

    def test_version(self):
        version = language_tool.get_version()
        self.assertTrue(version)


class TestCountryCodes(unittest.TestCase):
    tests = {
        "Australian": "AU",
        "Canadian": "CA",
        "GB": "GB",
        "New Zealand": "NZ",
        "South African": "ZA",
        "US": "US",
        "Austria": "AT",
        "Germany": "DE",
        "Swiss": "CH",
        "Brazil": "BR",
        "Portugal": "PT",

        "Australia": "AU",
        "Canada": "CA",
        "United Kingdom": "GB",
        "South Africa": "ZA",
        "United States": "US",
        "Switzerland": "CH",

        "Austrian": "AT",
        "Brazilian": "BR",
    }

    def test_country_codes(self):
        for country, code in self.tests.items():
            self.assertEqual(get_country_code(country), code)


if __name__ == "__main__":
    unittest.main()
