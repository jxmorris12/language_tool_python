"""Property-based tests for LanguageTag normalization and ordering."""

from __future__ import annotations

import string

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from language_tool_python.language_tag import LanguageTag

_LANGS = ["en-US", "en-GB", "en", "de-DE", "fr-FR", "pt-BR"]

_valid_tags = st.sampled_from(_LANGS)


@given(tag=_valid_tags)
@settings(max_examples=200)
def test_prop_normalize_is_idempotent(tag: str) -> None:
    """Normalizing an already-normalized tag returns the same normalized tag.

    :param tag: A tag drawn from the supported language list.
    :raises AssertionError: If re-normalizing the normalized tag changes it.
    """
    first = LanguageTag(tag, _LANGS)
    second = LanguageTag(first.normalized_tag, _LANGS)
    assert second.normalized_tag == first.normalized_tag


@given(
    tag=_valid_tags,
    upper=st.booleans(),
    use_underscore=st.booleans(),
)
@settings(max_examples=200)
def test_prop_normalize_invariant_to_case_and_separator(
    tag: str,
    upper: bool,
    use_underscore: bool,
) -> None:
    """Case and -/_ separator variants of a supported tag normalize identically.

    :param tag: A tag drawn from the supported language list.
    :param upper: Whether to uppercase the variant before normalizing.
    :param use_underscore: Whether to replace '-' with '_' in the variant.
    :raises AssertionError: If the variant normalizes differently from the original.
    """
    variant = tag.upper() if upper else tag.lower()
    if use_underscore:
        variant = variant.replace("-", "_")
    baseline = LanguageTag(tag, _LANGS)
    variant_tag = LanguageTag(variant, _LANGS)
    assert variant_tag.normalized_tag == baseline.normalized_tag


@given(a=_valid_tags, b=_valid_tags, c=_valid_tags)
@settings(max_examples=200)
def test_prop_total_ordering_is_consistent(a: str, b: str, c: str) -> None:
    """__lt__/__eq__/__hash__ satisfy total-ordering invariants for any triplet.

    Checks irreflexivity of '<', consistency between '==' and '<', hash equality
    for equal tags, and transitivity of '<'.

    :param a: First tag drawn from the supported language list.
    :param b: Second tag drawn from the supported language list.
    :param c: Third tag drawn from the supported language list.
    :raises AssertionError: If any total-ordering invariant is violated.
    """
    tag_a = LanguageTag(a, _LANGS)
    tag_b = LanguageTag(b, _LANGS)
    tag_c = LanguageTag(c, _LANGS)

    assert not (tag_a < tag_a)  # noqa: PLR0124  # irreflexivity check, not a typo

    if tag_a == tag_b:
        assert not (tag_a < tag_b)
        assert not (tag_b < tag_a)
        assert hash(tag_a) == hash(tag_b)
    else:
        assert (tag_a < tag_b) != (tag_b < tag_a)  # trichotomy for distinct tags

    if tag_a < tag_b < tag_c:
        assert tag_a < tag_c  # transitivity


@st.composite
def _unsupported_tag(draw: st.DrawFn) -> str:
    """Generate a string guaranteed to be rejected by LanguageTag(..., _LANGS).

    A 4-6 letter lowercase word with no '-'/'_' separator can never satisfy
    ``LanguageTag._LANGUAGE_RE`` (which requires the whole tag to be either a bare
    2-3 letter code, or a 2-3 letter code plus a '-'/'_' plus a 2-letter region),
    and is also excluded from the POSIX/C-locale special case.
    """
    word = draw(
        st.text(alphabet=string.ascii_lowercase, min_size=4, max_size=6),
    )
    if word == "posix":
        word = "posixx"
    return word


@given(tag=_unsupported_tag())
@settings(max_examples=200)
def test_prop_unsupported_tag_always_rejected(tag: str) -> None:
    """A tag outside the supported set (and outside the LANGUAGE_RE shape) always
    raises ValueError.

    :param tag: An adversarially generated, guaranteed-unsupported tag.
    :raises AssertionError: If ValueError is not raised for the unsupported tag.
    """  # noqa: D205
    with pytest.raises(ValueError, match="unsupported language"):
        LanguageTag(tag, _LANGS)
