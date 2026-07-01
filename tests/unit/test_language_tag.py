"""Unit tests for LanguageTag normalization and comparison."""

import pytest

from language_tool_python.language_tag import LanguageTag

_LANGS = ["en-US", "en-GB", "en", "de-DE", "fr-FR", "pt-BR"]

_SET_SIZE_TWO = 2


def _tag(tag: str, languages: list[str] = _LANGS) -> LanguageTag:
    """Construct a LanguageTag against _LANGS by default."""
    return LanguageTag(tag, languages)


class TestInit:
    """Tests for basic LanguageTag initialization and normalization."""

    def test_exact_match(self) -> None:
        """An exact match in the language list is returned unchanged."""
        lt = _tag("en-US")
        assert lt.normalized_tag == "en-US"

    def test_underscore_normalized_to_dash(self) -> None:
        """Underscore locale separators are converted to dashes."""
        lt = _tag("en_US")
        assert lt.normalized_tag == "en-US"

    def test_case_insensitive(self) -> None:
        """Tag lookup is case-insensitive."""
        lt = _tag("EN-us")
        assert lt.normalized_tag == "en-US"

    def test_tag_stored(self) -> None:
        """The original (pre-normalization) tag is preserved."""
        lt = _tag("en-US")
        assert lt.tag == "en-US"

    def test_languages_stored(self) -> None:
        """The language list is accessible on the tag object."""
        lt = _tag("en-US")
        assert "en-US" in lt.languages


class TestNormalizePosix:
    """Tests for POSIX/C locale fallback behaviour."""

    @pytest.mark.parametrize(
        "tag",
        ["C", "POSIX", "C.UTF-8"],
        ids=["c_locale", "posix_locale", "c_dot_variant"],
    )
    def test_posix_like_tag_falls_back_to_en_us(self, tag: str) -> None:
        """POSIX-like locale tags resolve to en-US when available."""
        lt = _tag(tag)
        assert lt.normalized_tag == "en-US"

    def test_posix_prefers_en_gb_when_no_en_us(self) -> None:
        """'C' locale falls back to en-GB when en-US is absent."""
        lt = LanguageTag("C", ["en-GB", "fr-FR"])
        assert lt.normalized_tag == "en-GB"

    def test_posix_falls_to_en_when_no_en_us_or_gb(self) -> None:
        """'C' locale falls back to bare 'en' when no regional variant exists."""
        lt = LanguageTag("C", ["en", "fr-FR"])
        assert lt.normalized_tag == "en"

    def test_posix_raises_when_no_english(self) -> None:
        """'C' locale raises ValueError when no English variant is available."""
        with pytest.raises(ValueError, match="unsupported language"):
            LanguageTag("C", ["de-DE", "fr-FR"])


class TestNormalizeFallback:
    """Tests for regex-based region-stripping fallback."""

    @pytest.mark.parametrize(
        ("tag", "expected"),
        [("en", "en"), ("pt-BR", "pt-BR")],
        ids=["language_only_matches_base", "regex_fallback_to_base_language"],
    )
    def test_normalizes_against_default_languages(
        self, tag: str, expected: str
    ) -> None:
        """A bare or exact-match tag normalizes as expected against _LANGS."""
        lt = _tag(tag)
        assert lt.normalized_tag == expected

    def test_regex_fallback_strips_region(self) -> None:
        """A tag with an unavailable region falls back to the base language."""
        lt = LanguageTag("en-AU", ["en", "de-DE"])
        assert lt.normalized_tag == "en"

    @pytest.mark.parametrize(
        ("tag", "match"),
        [
            ("", "empty language tag"),
            ("zz-ZZ", "unsupported language"),
            ("123invalid", "unsupported language"),
        ],
        ids=["empty_tag", "unsupported_tag", "unmatched_pattern"],
    )
    def test_invalid_tag_raises(self, tag: str, match: str) -> None:
        """Empty, unsupported, or unmatched tags all raise ValueError."""
        with pytest.raises(ValueError, match=match):
            _tag(tag)


class TestComparisons:
    """Tests for LanguageTag equality, ordering, and hashing."""

    def test_eq_same_tag(self) -> None:
        """Two tags with the same value are equal."""
        assert _tag("en-US") == _tag("en-US")

    def test_eq_with_string(self) -> None:
        """A LanguageTag equals its normalized string."""
        assert _tag("en-US") == "en-US"

    def test_eq_not_equal(self) -> None:
        """Tags with different values are not equal."""
        assert _tag("en-US") != _tag("de-DE")

    def test_eq_not_implemented_for_non_str(self) -> None:
        """Comparing with a non-string returns NotImplemented."""
        assert _tag("en-US").__eq__(42) is NotImplemented

    def test_lt_ordering(self) -> None:
        """Tags are ordered lexicographically by their normalized value."""
        assert _tag("de-DE") < _tag("en-US")

    def test_lt_not_implemented_for_non_str(self) -> None:
        """Less-than comparison with a non-string returns NotImplemented."""
        assert _tag("en-US").__lt__(42) is NotImplemented

    def test_hash_equal_tags(self) -> None:
        """Equal tags produce the same hash."""
        assert hash(_tag("en-US")) == hash(_tag("en-US"))

    def test_hash_different_tags(self) -> None:
        """Different tags produce different hashes (high probability)."""
        assert hash(_tag("en-US")) != hash(_tag("de-DE"))

    def test_in_set(self) -> None:
        """Two distinct tags result in a two-element set."""
        s = {_tag("en-US"), _tag("de-DE")}
        assert len(s) == _SET_SIZE_TWO


class TestStrRepr:
    """Tests for LanguageTag string representations."""

    def test_str_returns_normalized(self) -> None:
        """str() returns the normalized tag."""
        assert str(_tag("en-US")) == "en-US"

    def test_repr_format(self) -> None:
        """repr() uses the canonical angle-bracket format."""
        assert repr(_tag("en-US")) == '<LanguageTag "en-US">'

    def test_total_ordering_gt(self) -> None:
        """Greater-than comparison works via total_ordering."""
        assert _tag("en-US") > _tag("de-DE")
