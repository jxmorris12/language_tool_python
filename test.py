#!/usr/bin/env python3
"""Test suit for language_tool
"""
import unittest
from collections import namedtuple

from language_tool import LanguageTool


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
        ],
    }

    def test_samples(self):
        for language, tests in self.tests.items():
            lt = LanguageTool(language)
            for text, expected_matches in tests:
                matches = lt.check(text)
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


if __name__ == "__main__":
    unittest.main()
