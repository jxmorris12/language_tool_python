"""Unit tests for the Match class and related helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from language_tool_python.match import (
    Match,
    _get_match_ordered_dict,
    four_byte_char_positions,
    is_check_match,
)

if TYPE_CHECKING:
    from language_tool_python._internals.api_types import CheckMatch

_DEFAULT_OFFSET = 8
_DEFAULT_LENGTH = 4
_DEFAULT_CONTEXT_OFFSET = 8
_NUM_MATCH_FIELDS = 10


def _make_attrib(  # noqa: PLR0913
    *,
    message: str = "Possible spelling mistake.",
    short_message: str = "Spelling mistake",
    replacements: list[str] | None = None,
    offset: int = 8,
    length: int = 4,
    context_text: str = "This is noot okay.",
    context_offset: int = 8,
    sentence: str = "This is noot okay.",
    rule_id: str = "MORFOLOGIK_RULE_EN_US",
    rule_desc: str = "Possible spelling mistake",
    issue_type: str = "misspelling",
    category_id: str = "TYPOS",
    category_name: str = "Possible Typo",
) -> CheckMatch:
    repl_list: list[str] = replacements if replacements is not None else ["not", "noon"]
    return {
        "message": message,
        "shortMessage": short_message,
        "replacements": [{"value": r} for r in repl_list],
        "offset": offset,
        "length": length,
        "context": {"text": context_text, "offset": context_offset, "length": length},
        "sentence": sentence,
        "type": {"typeName": "Other"},
        "rule": {
            "id": rule_id,
            "description": rule_desc,
            "issueType": issue_type,
            "category": {"id": category_id, "name": category_name},
        },
        "ignoreForIncompleteSentence": False,
        "contextForSureMatch": 0,
    }


def _make_match(text: str = "This is noot okay.", **kwargs: object) -> Match:
    return Match(_make_attrib(**kwargs), four_byte_char_positions(text))  # type: ignore[arg-type]


class TestMatchInit:
    """Tests for Match.__init__() attribute mapping."""

    def test_basic_attributes(self) -> None:
        """Default attributes are populated correctly from the attrib dict."""
        m = _make_match()
        assert m.rule_id == "MORFOLOGIK_RULE_EN_US"
        assert m.message == "Possible spelling mistake."
        assert m.replacements == ["not", "noon"]
        assert m.offset == _DEFAULT_OFFSET
        assert m.error_length == _DEFAULT_LENGTH
        assert m.category == "TYPOS"
        assert m.rule_issue_type == "misspelling"
        assert m.sentence == "This is noot okay."

    def test_context_attributes(self) -> None:
        """Context text and offset are set from the nested context dict."""
        m = _make_match()
        assert m.context == "This is noot okay."
        assert m.offset_in_context == _DEFAULT_CONTEXT_OFFSET

    def test_unicode_normalization(self) -> None:
        """Message text is NFKC-normalized on construction."""
        # "ﬁ" (U+FB01 LATIN SMALL LIGATURE FI) → "fi"
        m = _make_match(message="ﬁnd the error")
        assert m.message == "find the error"

    def test_four_byte_char_adjustment(self) -> None:
        """A 4-byte emoji before the match shifts the Python offset by 1."""
        # "🌅" at position 0 is 1 Python char but 2 Java chars
        # Java offset 3 → Python offset 2 ("🌅 he" → 'h' is at index 2)
        text = "🌅 hello world"
        attrib = _make_attrib(
            offset=3,
            length=5,
            context_text="🌅 hello world",
            context_offset=3,
            sentence="🌅 hello world",
        )
        m = Match(attrib, four_byte_char_positions(text))
        adjusted_offset = 2
        assert m.offset == adjusted_offset

    def test_four_byte_char_after_match_is_not_counted(self) -> None:
        """A 4-byte emoji after the match does not shift the offset."""
        # "🌅" at position 6 is after the match at offset 0, so the adjustment
        # loop must break on its first iteration instead of counting it.
        text = "hello 🌅"
        attrib = _make_attrib(
            offset=0,
            length=5,
            context_text=text,
            context_offset=0,
            sentence=text,
        )
        m = Match(attrib, four_byte_char_positions(text))
        assert m.offset == 0

    def test_no_adjustment_without_four_byte_chars(self) -> None:
        """Offsets are unchanged when no 4-byte characters precede the match."""
        text = "Hello world today"
        expected_offset = 6
        m = Match(
            _make_attrib(
                offset=expected_offset,
                length=5,
                context_text=text,
                context_offset=expected_offset,
                sentence=text,
            ),
            four_byte_char_positions(text),
        )
        assert m.offset == expected_offset

    def test_same_text_reuses_positions(self) -> None:
        """Two matches sharing a precomputed positions list both get correct offsets."""
        text = "Same text here."
        explicit_offset = 5
        four_byte_positions = four_byte_char_positions(text)
        m1 = Match(_make_attrib(context_text=text, sentence=text), four_byte_positions)
        m2 = Match(
            _make_attrib(
                context_text=text,
                sentence=text,
                offset=explicit_offset,
                length=_DEFAULT_LENGTH,
                context_offset=explicit_offset,
            ),
            four_byte_positions,
        )
        assert m1.offset == _DEFAULT_OFFSET
        assert m2.offset == explicit_offset


class TestFourByteCharPositions:
    """Tests for four_byte_char_positions() helper."""

    def test_empty_string(self) -> None:
        """An empty string has no 4-byte char positions."""
        assert four_byte_char_positions("") == []

    def test_ascii_only(self) -> None:
        """A pure-ASCII string has no 4-byte char positions."""
        assert four_byte_char_positions("hello") == []

    def test_emoji_at_start(self) -> None:
        """An emoji at position 0 is reported at index 0."""
        assert four_byte_char_positions("🌅abc") == [0]

    def test_multiple_emojis(self) -> None:
        """Two consecutive emojis are reported with adjusted indices."""
        positions = four_byte_char_positions("🌅🎉abc")
        assert positions == [0, 2]

    def test_emoji_in_middle(self) -> None:
        """An emoji in the middle of ASCII text is reported at the correct index."""
        positions = four_byte_char_positions("ab🌅cd")
        assert positions == [2]


class TestMatchOrderedDict:
    """Tests for _get_match_ordered_dict() field-type registry."""

    def test_returns_all_keys(self) -> None:
        """All expected field names are returned in order."""
        d = _get_match_ordered_dict()
        expected_keys = [
            "rule_id",
            "message",
            "replacements",
            "offset_in_context",
            "context",
            "offset",
            "error_length",
            "category",
            "rule_issue_type",
            "sentence",
        ]
        assert list(d.keys()) == expected_keys

    def test_value_types(self) -> None:
        """Field types are the expected Python built-ins."""
        d = _get_match_ordered_dict()
        assert d["offset"] is int
        assert d["rule_id"] is str
        assert d["replacements"] is list


class TestIsCheckMatch:
    """Tests for the is_check_match() type-guard."""

    def test_valid_check_match(self) -> None:
        """A fully populated attrib dict is recognised as a CheckMatch."""
        assert is_check_match(_make_attrib())

    def test_not_dict(self) -> None:
        """Non-dict values are rejected."""
        assert not is_check_match("not a dict")
        assert not is_check_match(None)
        assert not is_check_match(42)

    def test_missing_field(self) -> None:
        """A dict missing a required field is rejected."""
        attrib = dict(_make_attrib())
        del attrib["message"]
        assert not is_check_match(attrib)

    def test_wrong_type(self) -> None:
        """A dict with a field of the wrong type is rejected."""
        attrib = dict(_make_attrib())
        attrib["offset"] = "not_an_int"
        assert not is_check_match(attrib)


class TestMatchStr:
    """Tests for Match.__str__() human-readable formatter."""

    def test_str_contains_rule_id(self) -> None:
        """The rule ID is present in the string representation."""
        m = _make_match()
        s = str(m)
        assert "MORFOLOGIK_RULE_EN_US" in s

    def test_str_contains_message(self) -> None:
        """The error message is present in the string representation."""
        m = _make_match()
        assert "Possible spelling mistake" in str(m)

    def test_str_contains_suggestions(self) -> None:
        """Replacement suggestions are present in the string representation."""
        m = _make_match()
        assert "not" in str(m)

    def test_str_no_message_skips_message_line(self) -> None:
        """A match with no message omits the Message line."""
        m = _make_match(message="")
        assert "Message" not in str(m)

    def test_str_no_replacements_skips_suggestion(self) -> None:
        """A match with no replacements omits the Suggestion line."""
        m = _make_match(replacements=[])
        assert "Suggestion" not in str(m)


class TestMatchRepr:
    """Tests for Match.__repr__() machine-readable formatter."""

    def test_repr_contains_class_name(self) -> None:
        """The class name 'Match(' appears in the repr."""
        m = _make_match()
        assert "Match(" in repr(m)

    def test_repr_contains_rule_id(self) -> None:
        """The rule ID appears in the repr."""
        m = _make_match()
        assert "MORFOLOGIK_RULE_EN_US" in repr(m)


class TestMatchedText:
    """Tests for the matched_text property."""

    def test_matched_text_extracts_correctly(self) -> None:
        """matched_text returns the exact text slice at offset/length."""
        m = _make_match()
        assert m.matched_text == "noot"


class TestGetLineAndColumn:
    """Tests for Match.get_line_and_column()."""

    def test_single_line(self) -> None:
        """A single-line text returns line 1 and a positive column."""
        text = "This is noot okay."
        m = _make_match(text=text)
        line, col = m.get_line_and_column(text)
        assert line == 1
        assert col > 0

    def test_context_not_in_text_raises(self) -> None:
        """Passing unrelated text raises ValueError."""
        m = _make_match()
        with pytest.raises(ValueError, match="does not match the context"):
            m.get_line_and_column("completely different text here blah blah")


class TestSelectReplacement:
    """Tests for Match.select_replacement() replacement narrower."""

    def test_select_valid_index(self) -> None:
        """Selecting index 1 keeps only the second replacement."""
        m = _make_match()
        m.select_replacement(1)
        assert m.replacements == ["noon"]

    def test_select_first(self) -> None:
        """Selecting index 0 keeps only the first replacement."""
        m = _make_match()
        m.select_replacement(0)
        assert m.replacements == ["not"]

    def test_negative_index_raises(self) -> None:
        """A negative index raises ValueError."""
        m = _make_match()
        with pytest.raises(ValueError, match="numbered from 0"):
            m.select_replacement(-1)

    def test_out_of_bounds_raises(self) -> None:
        """An out-of-range index raises ValueError."""
        m = _make_match()
        with pytest.raises(ValueError, match="numbered from 0"):
            m.select_replacement(99)

    def test_no_replacements_raises(self) -> None:
        """Selecting when there are no replacements raises ValueError."""
        m = _make_match(replacements=[])
        with pytest.raises(ValueError, match="no suggestions"):
            m.select_replacement(0)


class TestMatchComparisons:
    """Tests for Match equality, ordering, and NotImplemented handling."""

    def test_eq_equal_matches(self) -> None:
        """Two matches built from the same attrib dict are equal."""
        m1 = _make_match()
        m2 = _make_match()
        assert m1 == m2

    def test_eq_different_offset(self) -> None:
        """Matches with different offsets are not equal."""
        m1 = _make_match()
        m2 = _make_match(offset=0, context_offset=0)
        assert m1 != m2

    def test_eq_not_implemented_for_non_match(self) -> None:
        """Comparing a Match with a non-Match returns NotImplemented."""
        m = _make_match()
        assert m.__eq__("not a match") is NotImplemented

    def test_lt(self) -> None:
        """A match at an earlier offset is less than one at a later offset."""
        text = "This is noot okay, and also baaad."
        positions = four_byte_char_positions(text)
        m_early = Match(
            _make_attrib(
                offset=0,
                length=_DEFAULT_LENGTH,
                context_text=text,
                context_offset=0,
                sentence=text,
            ),
            positions,
        )
        m_later = Match(
            _make_attrib(
                offset=_DEFAULT_OFFSET,
                length=_DEFAULT_LENGTH,
                context_text=text,
                context_offset=_DEFAULT_OFFSET,
                sentence=text,
            ),
            positions,
        )
        assert m_early < m_later

    def test_lt_not_implemented_for_non_match(self) -> None:
        """Less-than comparison with a non-Match returns NotImplemented."""
        m = _make_match()
        assert m.__lt__("not a match") is NotImplemented


class TestMatchIter:
    """Tests for Match.__iter__() field-value iterator."""

    def test_iter_yields_all_values(self) -> None:
        """Iterating a match yields exactly _NUM_MATCH_FIELDS values."""
        m = _make_match()
        values = list(m)
        assert len(values) == _NUM_MATCH_FIELDS

    def test_iter_first_is_rule_id(self) -> None:
        """The first value yielded by the iterator is the rule_id."""
        m = _make_match()
        assert next(iter(m)) == "MORFOLOGIK_RULE_EN_US"


class TestMatchSetAttr:
    """Tests for Match.__setattr__() type-coercing setter."""

    def test_setattr_known_key_coerces_type(self) -> None:
        """Setting a known field with a string coerces it to the declared type."""
        m = _make_match()
        new_offset = 5
        m.offset = "5"  # type: ignore[assignment]
        assert m.offset == new_offset
        assert isinstance(m.offset, int)

    def test_setattr_unknown_key_is_ignored(self) -> None:
        """Setting an unknown field is silently ignored."""
        m = _make_match()
        m.__setattr__("nonexistent_key", "value")
        assert not hasattr(m, "nonexistent_key")


class TestMatchGetAttr:
    """Tests for Match.__getattr__() unknown-attribute guard."""

    def test_getattr_unknown_key_raises(self) -> None:
        """Accessing an unknown attribute raises AttributeError."""
        m = _make_match()
        with pytest.raises(AttributeError, match="no attribute"):
            _ = m.completely_unknown
