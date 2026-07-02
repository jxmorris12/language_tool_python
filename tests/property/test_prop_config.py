"""Property-based tests for LanguageToolConfig input validation.

These tests use Hypothesis to verify that injection-protection invariants
hold for any input, not just the handwritten examples in unit tests.
"""

import string

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from language_tool_python.config_file import (
    _CONFIG_SCHEMA,
    LanguageToolConfig,
    _bool_encoder,
    _encode_config,
    _int_encoder,
    _is_lang_key,
)

_LINEBREAK_CHARS = ["\n", "\r", "\r\n"]

_INT_KEYS = [
    key for key, spec in _CONFIG_SCHEMA.items() if spec.encoder is _int_encoder
]
_BOOL_KEYS = [
    key for key, spec in _CONFIG_SCHEMA.items() if spec.encoder is _bool_encoder
]


@given(
    before=st.text(),
    linebreak=st.sampled_from(_LINEBREAK_CHARS),
    after=st.text(),
)
@settings(max_examples=200)
def test_prop_config_value_with_linebreak_always_raises(
    before: str,
    linebreak: str,
    after: str,
) -> None:
    """Any config value containing CR or LF must raise ValueError.

    The string is constructed as ``before + linebreak + after`` to guarantee
    the presence of a line-break character without relying on filter().

    :param before: Arbitrary text before the line-break.
    :param linebreak: A CR, LF, or CRLF sequence.
    :param after: Arbitrary text after the line-break.
    :raises AssertionError: If ValueError is not raised.
    """
    value = before + linebreak + after
    with pytest.raises(ValueError, match="line breaks"):
        LanguageToolConfig({"blockedReferrers": value})


@given(
    prefix=st.text(alphabet=st.characters(blacklist_characters="\r\n\\")),
    count=st.integers(min_value=1, max_value=5),
)
@settings(max_examples=200)
def test_prop_config_odd_trailing_backslashes_always_raise(
    prefix: str,
    count: int,
) -> None:
    r"""Any config value ending with an odd number of backslashes must raise ValueError.

    The value is constructed as ``prefix + '\\\\' * (2*count - 1)`` to guarantee
    the trailing backslash count is always odd (1, 3, 5, 7, or 9).

    :param prefix: A string with no backslashes or line-break characters.
    :param count: Determines the odd backslash count: ``2*count - 1``.
    :raises AssertionError: If ValueError is not raised.
    """
    value = prefix + "\\" * (2 * count - 1)
    with pytest.raises(ValueError, match="backslash"):
        LanguageToolConfig({"blockedReferrers": value})


@given(
    key_before=st.text(alphabet=st.characters(blacklist_characters="\r\n")),
    linebreak=st.sampled_from(_LINEBREAK_CHARS),
    key_after=st.text(alphabet=st.characters(blacklist_characters="\r\n")),
)
@settings(max_examples=200)
def test_prop_config_key_with_linebreak_always_raises(
    key_before: str,
    linebreak: str,
    key_after: str,
) -> None:
    """Any config key containing CR or LF must raise ValueError.

    :param key_before: Text before the line-break in the key.
    :param linebreak: A CR, LF, or CRLF sequence.
    :param key_after: Text after the line-break in the key.
    :raises AssertionError: If ValueError is not raised.
    """
    key = key_before + linebreak + key_after
    with pytest.raises(ValueError, match="line breaks"):
        LanguageToolConfig({key: "valid_value"})


@given(code=st.text(alphabet=string.ascii_lowercase, min_size=1, max_size=10))
@settings(max_examples=200)
def test_prop_is_lang_key_accepts_any_lang_prefixed_code(code: str) -> None:
    """Any 'lang-<code>' key is recognized as a language key.

    :param code: Non-empty lowercase code with no '-' inside it.
    :raises AssertionError: If _is_lang_key does not accept the generated key.
    """
    assert _is_lang_key(f"lang-{code}") is True


@given(key=st.text().filter(lambda s: not s.startswith("lang-")))
@settings(max_examples=200)
def test_prop_is_lang_key_rejects_non_lang_prefixed_keys(key: str) -> None:
    """Any key not starting with 'lang-' is never recognized as a language key.

    :param key: Arbitrary text not starting with the 'lang-' prefix.
    :raises AssertionError: If _is_lang_key incorrectly accepts the generated key.
    """
    assert _is_lang_key(key) is False


@given(
    key=st.sampled_from(_INT_KEYS),
    value=st.integers(min_value=-1_000_000, max_value=1_000_000),
)
@settings(max_examples=200)
def test_prop_int_schema_key_round_trips_through_encode_config(
    key: str,
    value: int,
) -> None:
    """Any int-typed schema key round-trips through _encode_config as str(value).

    :param key: A schema key whose encoder is _int_encoder.
    :param value: An arbitrary integer value.
    :raises AssertionError: If the encoded value does not equal str(value).
    """
    result = _encode_config({key: value})
    assert result[key] == str(value)


@given(key=st.sampled_from(_BOOL_KEYS), value=st.booleans())
@settings(max_examples=200)
def test_prop_bool_schema_key_round_trips_through_encode_config(
    key: str,
    value: bool,
) -> None:
    """Any bool-typed schema key round-trips through _encode_config as 'true'/'false'.

    :param key: A schema key whose encoder is _bool_encoder.
    :param value: An arbitrary boolean value.
    :raises AssertionError: If the encoded value does not match the expected string.
    """
    result = _encode_config({key: value})
    assert result[key] == ("true" if value else "false")


@given(
    key=st.text(alphabet=string.ascii_letters, min_size=1, max_size=20).filter(
        lambda s: not s.startswith("lang-") and s not in _CONFIG_SCHEMA,
    ),
)
@settings(max_examples=200)
def test_prop_unknown_key_always_raises(key: str) -> None:
    """Any key that is neither lang-* nor in the schema always raises ValueError.

    :param key: A generated key guaranteed to be outside lang-* and the schema.
    :raises AssertionError: If ValueError is not raised for the unknown key.
    """
    with pytest.raises(ValueError, match="unexpected key"):
        _encode_config({key: "value"})
