"""Property-based tests for LanguageToolConfig input validation.

These tests use Hypothesis to verify that injection-protection invariants
hold for any input, not just the handwritten examples in unit tests.
"""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from language_tool_python.config_file import LanguageToolConfig

_LINEBREAK_CHARS = ["\n", "\r", "\r\n"]


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
