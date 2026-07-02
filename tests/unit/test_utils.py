"""Unit tests for language_tool_python.utils (classify_matches, correct)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from language_tool_python.match import Match, four_byte_char_positions
from language_tool_python.utils import TextStatus, classify_matches, correct

if TYPE_CHECKING:
    from language_tool_python._internals.api_types import CheckMatch


def _make_match(
    rule_id: str = "RULE",
    offset: int = 0,
    length: int = 4,
    replacements: list[str] | None = None,
) -> Match:
    attrib: CheckMatch = {
        "message": "Error",
        "shortMessage": "",
        "replacements": [{"value": r} for r in (replacements or [])],
        "offset": offset,
        "length": length,
        "context": {"text": "text here.", "offset": offset, "length": length},
        "sentence": "text here.",
        "type": {"typeName": "Other"},
        "rule": {
            "id": rule_id,
            "description": "desc",
            "issueType": "misspelling",
            "category": {"id": "TYPOS", "name": "Typos"},
        },
        "ignoreForIncompleteSentence": False,
        "contextForSureMatch": 0,
    }
    return Match(attrib, four_byte_char_positions("text here."))


class TestClassifyMatches:
    """Tests for classify_matches() match-set status classifier."""

    def test_no_matches_returns_correct(self) -> None:
        """An empty match list is classified as CORRECT."""
        assert classify_matches([]) == TextStatus.CORRECT

    def test_matches_with_replacements_returns_faulty(self) -> None:
        """A match that has a replacement is classified as FAULTY."""
        m = _make_match(replacements=["fix"])
        assert classify_matches([m]) == TextStatus.FAULTY

    def test_matches_without_replacements_returns_garbage(self) -> None:
        """A match without any replacement is classified as GARBAGE."""
        m = _make_match(replacements=[])
        assert classify_matches([m]) == TextStatus.GARBAGE

    def test_mixed_filters_to_faulty(self) -> None:
        """A mix of matches with and without replacements is classified as FAULTY."""
        m_with = _make_match(replacements=["fix"])
        m_without = _make_match(replacements=[])
        assert classify_matches([m_with, m_without]) == TextStatus.FAULTY

    def test_all_without_replacements_is_garbage(self) -> None:
        """Multiple matches all lacking replacements are classified as GARBAGE."""
        matches = [_make_match(replacements=[]) for _ in range(3)]
        assert classify_matches(matches) == TextStatus.GARBAGE


class TestCorrect:
    """Tests for correct() auto-correction function."""

    def test_no_matches_returns_unchanged(self) -> None:
        """Text with no matches is returned unchanged."""
        assert correct("hello world", []) == "hello world"

    def test_single_correction(self) -> None:
        """A single match with a replacement is applied to the text."""
        m = _make_match(offset=0, length=4, replacements=["text"])
        result = correct("text here.", [m])
        assert result == "text here."

    def test_correction_replaces_error(self) -> None:
        """A misspelled word is replaced by the first suggested correction."""
        text = "Helo world"
        attrib: CheckMatch = {
            "message": "Misspelling",
            "shortMessage": "",
            "replacements": [{"value": "Hello"}],
            "offset": 0,
            "length": 4,
            "context": {"text": text, "offset": 0, "length": 4},
            "sentence": text,
            "type": {"typeName": "Other"},
            "rule": {
                "id": "SPELL",
                "description": "Spelling",
                "issueType": "misspelling",
                "category": {"id": "TYPOS", "name": "Typos"},
            },
            "ignoreForIncompleteSentence": False,
            "contextForSureMatch": 0,
        }
        m = Match(attrib, four_byte_char_positions(text))
        result = correct(text, [m])
        assert result == "Hello world"

    def test_match_without_replacement_is_skipped(self) -> None:
        """A match with no replacement leaves the text unchanged."""
        m = _make_match(offset=0, length=4, replacements=[])
        assert correct("text here.", [m]) == "text here."

    def test_overlapping_match_skips_mismatched_error(self) -> None:
        """The second of two overlapping matches is skipped when offset drifts."""
        # First match replaces "aa" (offset 0, len 2) with "xxxxxx" (longer).
        # Second match overlaps at offset 1, len 2 ("ab"). After the first
        # replacement expands the text, the second match's expected text no
        # longer sits at the right position → continue branch is hit.
        text = "aabbc"
        attrib1: CheckMatch = {
            "message": "e",
            "shortMessage": "",
            "replacements": [{"value": "xxxxxx"}],
            "offset": 0,
            "length": 2,
            "context": {"text": text, "offset": 0, "length": 2},
            "sentence": text,
            "type": {"typeName": "Other"},
            "rule": {
                "id": "R",
                "description": "d",
                "issueType": "misspelling",
                "category": {"id": "C", "name": "C"},
            },
            "ignoreForIncompleteSentence": False,
            "contextForSureMatch": 0,
        }
        attrib2: CheckMatch = {
            "message": "e",
            "shortMessage": "",
            "replacements": [{"value": "y"}],
            "offset": 1,
            "length": 2,
            "context": {"text": text, "offset": 1, "length": 2},
            "sentence": text,
            "type": {"typeName": "Other"},
            "rule": {
                "id": "R",
                "description": "d",
                "issueType": "misspelling",
                "category": {"id": "C", "name": "C"},
            },
            "ignoreForIncompleteSentence": False,
            "contextForSureMatch": 0,
        }
        positions = four_byte_char_positions(text)
        m1 = Match(attrib1, positions)
        m2 = Match(attrib2, positions)
        result = correct(text, [m1, m2])
        assert result == "xxxxxxbbc"

    def test_correct_adjusts_offset_for_length_change(self) -> None:
        """A length-changing replacement shifts the offset for subsequent matches."""
        text = "A b c"
        attrib1: CheckMatch = {
            "message": "err",
            "shortMessage": "",
            "replacements": [{"value": "AAA"}],
            "offset": 0,
            "length": 1,
            "context": {"text": text, "offset": 0, "length": 1},
            "sentence": text,
            "type": {"typeName": "Other"},
            "rule": {
                "id": "R",
                "description": "d",
                "issueType": "misspelling",
                "category": {"id": "C", "name": "C"},
            },
            "ignoreForIncompleteSentence": False,
            "contextForSureMatch": 0,
        }
        attrib2: CheckMatch = {
            "message": "err",
            "shortMessage": "",
            "replacements": [{"value": "BBB"}],
            "offset": 2,
            "length": 1,
            "context": {"text": text, "offset": 2, "length": 1},
            "sentence": text,
            "type": {"typeName": "Other"},
            "rule": {
                "id": "R",
                "description": "d",
                "issueType": "misspelling",
                "category": {"id": "C", "name": "C"},
            },
            "ignoreForIncompleteSentence": False,
            "contextForSureMatch": 0,
        }
        positions = four_byte_char_positions(text)
        m1 = Match(attrib1, positions)
        m2 = Match(attrib2, positions)
        result = correct(text, [m1, m2])
        assert result == "AAA BBB c"


@pytest.mark.parametrize(
    ("status", "value"),
    [
        (TextStatus.CORRECT, "correct"),
        (TextStatus.FAULTY, "faulty"),
        (TextStatus.GARBAGE, "garbage"),
    ],
)
def test_text_status_values(status: TextStatus, value: str) -> None:
    """TextStatus enum values match expected strings."""
    assert status.value == value
