"""LanguageTool API Match object representation and utility module."""

from __future__ import annotations

import logging
import unicodedata
from collections import OrderedDict
from collections import OrderedDict as OrderedDictType
from functools import total_ordering
from typing import TYPE_CHECKING, Union

from ._compat import deprecated
from .utils import SupportsFloat, SupportsInt

if TYPE_CHECKING:
    from collections.abc import Iterator

    from .api_types import CheckMatch

logger = logging.getLogger(__name__)

UTF8_4_BYTE_LENGTH = 4
CONTEXT_PREFIX_SUFFIX_LENGTH = 3
CONTEXT_WITH_ADDITIONS_MIN_LENGTH = 6
MatchValue = Union[str, int, list[str]]  # | operator not fully supported by py3.9


def get_match_ordered_dict() -> OrderedDictType[str, type]:
    """Return an ordered dictionary with predefined keys and their corresponding types.

    :return: An OrderedDict where each key is a string representing a specific attribute
             and each value is the type of that attribute.
    :rtype: OrderedDictType[str, type]

    The keys and their corresponding types are:

    - 'rule_id': str
    - 'message': str
    - 'replacements': list
    - 'offset_in_context': int
    - 'context': str
    - 'offset': int
    - 'error_length': int
    - 'category': str
    - 'rule_issue_type': str
    - 'sentence': str
    """
    return OrderedDict(
        [
            ("rule_id", str),
            ("message", str),
            ("replacements", list),
            ("offset_in_context", int),
            ("context", str),
            ("offset", int),
            ("error_length", int),
            ("category", str),
            ("rule_issue_type", str),
            ("sentence", str),
        ],
    )


@deprecated(
    "This function is no longer used internally and will be removed in 4.0.",
    stacklevel=2,
)
def auto_type(obj: SupportsInt | SupportsFloat | object) -> int | float | object:
    """Attempt to automatically convert the input object to an integer or float.

    If the conversion to an integer fails, it tries to convert to a float. If both
    conversions fail, it returns the original object.

    :param obj: The object to be converted.
    :type obj: SupportsInt | SupportsFloat | object
    :return: The converted object as an integer, float, or the original object.
    :rtype: int | float | object
    """
    if isinstance(obj, SupportsInt):
        return int(obj)
    if isinstance(obj, SupportsFloat):
        return float(obj)
    return obj


def four_byte_char_positions(text: str) -> list[int]:
    """Identify positions of 4-byte encoded characters in a UTF-8 string.

    This function scans through the input text and identifies the positions of
    characters that are encoded with 4 bytes in UTF-8. These characters are typically
    non-BMP (Basic Multilingual Plane) characters, such as certain emoji and some rare
    Chinese, Japanese, and Korean characters.

    :param text: The input string to be analyzed.
    :type text: str
    :return: A list of positions where 4-byte encoded characters are found.
    :rtype: list[int]
    """
    positions: list[int] = []
    char_index = 0
    for char in text:
        if len(char.encode("utf-8")) == UTF8_4_BYTE_LENGTH:
            positions.append(char_index)
            # Adding 1 to the index because 4 byte characters are
            # 2 bytes in length in LanguageTool, instead of 1 byte in Python.
            char_index += 1
        char_index += 1
    if positions:
        logger.debug("Found 4-byte encoded characters at positions: %s", positions)
    return positions


@total_ordering
class Match:  # noqa: PLW1641  # Doesn't implement hash because it's mutable
    """Represent a language rule violation match.

    :param attrib: A raw LanguageTool API match. It is expected to contain ``rule``
        (with ``category``, ``id``, and ``issueType``), ``context`` (with ``offset``
        and ``text``), ``replacements`` (items with ``value``), ``length``, and
        ``message``.
    :type attrib: CheckMatch
    :param text: The original text in which the error occurred (the whole text,
     not just the context).
    :type text: str

    Example of a match object received from the LanguageTool API :

    .. code-block:: python

        {
            "message": "Possible spelling mistake found.",
            "shortMessage": "Spelling mistake",
            "replacements": [
                {"value": "newt"},
                {"value": "not"},
                {"value": "new", "shortDescription": "having just been made"},
                {"value": "news"},
                {"value": "foot", "shortDescription": "singular"},
                {"value": "root", "shortDescription": "underground organ of a plant"},
                {"value": "boot"},
                {"value": "noon"},
                {"value": "loot", "shortDescription": "plunder"},
                {"value": "moot"},
                {"value": "Root"},
                {"value": "soot", "shortDescription": "carbon black"},
                {"value": "newts"},
                {"value": "nook"},
                {"value": "Lieut"},
                {"value": "coot"},
                {"value": "hoot"},
                {"value": "toot"},
                {"value": "snoot"},
                {"value": "neut"},
                {"value": "nowt"},
                {"value": "Noor"},
                {"value": "noob"},
            ],
            "offset": 8,
            "length": 4,
            "context": {"text": "This is noot okay. ", "offset": 8, "length": 4},
            "sentence": "This is noot okay.",
            "type": {"typeName": "Other"},
            "rule": {
                "id": "MORFOLOGIK_RULE_EN_US",
                "description": "Possible spelling mistake",
                "issueType": "misspelling",
                "category": {"id": "TYPOS", "name": "Possible Typo"},
            },
            "ignoreForIncompleteSentence": False,
            "contextForSureMatch": 0,
        }

    """

    PREVIOUS_MATCHES_TEXT: str | None = None
    """The text of the previous match object."""

    FOUR_BYTES_POSITIONS: list[int] | None = None
    """The positions of 4-byte encoded characters in the text, registered by the
    previous match object (kept for optimization purposes if the text is the same)."""

    rule_id: str
    """The ID of the rule that was violated."""

    message: str
    """The message describing the error."""

    replacements: list[str]
    """A list of suggested replacements for the error."""

    offset_in_context: int
    """The offset of the error in the context."""

    context: str
    """The context in which the error occurred."""

    offset: int
    """The offset of the error."""

    error_length: int
    """The length of the error."""

    category: str
    """The category of the rule that was violated."""

    rule_issue_type: str
    """The issue type of the rule that was violated."""

    sentence: str
    """The sentence that contains the rule violation."""

    def __init__(self, attrib: CheckMatch, text: str) -> None:
        """Initialize a Match object with the given attributes.

        The method processes and normalizes the attributes before storing them on the
        object. This method adjusts the positions of 4-byte encoded characters in the
        text to ensure the offsets of the matches are correct.
        """
        # Process rule.
        custom_match: dict[str, str | int | list[str]] = {}
        custom_match["category"] = attrib["rule"]["category"]["id"]
        custom_match["rule_id"] = attrib["rule"]["id"]
        custom_match["rule_issue_type"] = attrib["rule"]["issueType"]

        # Process context.
        custom_match["offset_in_context"] = attrib["context"]["offset"]
        custom_match["context"] = attrib["context"]["text"]
        # Process replacements.
        custom_match["replacements"] = [r["value"] for r in attrib["replacements"]]
        # Rename error length.
        custom_match["error_length"] = attrib["length"]
        # Normalize unicode
        custom_match["message"] = unicodedata.normalize("NFKC", attrib["message"])
        custom_match["sentence"] = attrib["sentence"]
        # Store offset before adjusting it for 4-byte characters
        custom_match["offset"] = attrib["offset"]
        # Store objects on self.
        for k, v in custom_match.items():
            setattr(self, k, v)

        if text != Match.PREVIOUS_MATCHES_TEXT:
            Match.PREVIOUS_MATCHES_TEXT = text
            Match.FOUR_BYTES_POSITIONS = four_byte_char_positions(text)
        # Get the positions of 4-byte encoded characters in the text because without
        # carrying out this step, the offsets of the matches could be incorrect.
        if Match.FOUR_BYTES_POSITIONS is not None:
            self.offset -= sum(
                1 for pos in Match.FOUR_BYTES_POSITIONS if pos < self.offset
            )

    def _ordered_items(self) -> list[tuple[str, MatchValue]]:
        """Return public match attributes in the documented order."""
        return [
            ("rule_id", self.rule_id),
            ("message", self.message),
            ("replacements", self.replacements),
            ("offset_in_context", self.offset_in_context),
            ("context", self.context),
            ("offset", self.offset),
            ("error_length", self.error_length),
            ("category", self.category),
            ("rule_issue_type", self.rule_issue_type),
            ("sentence", self.sentence),
        ]

    def __repr__(self) -> str:
        """Return a string representation of the object.

        This method provides a detailed string representation of the object, including
        its class name and a dictionary of its attributes.

        :return: A string representation of the object.
        :rtype: str
        """

        def _ordered_dict_repr() -> str:
            """Return the object's attributes as an ordered dictionary string.

            This method collects the attributes of the object, ensuring that the order
            of attributes is preserved as defined by ``get_match_ordered_dict()``.
            Attributes that are not part of the ordered dictionary are appended at the
            end. Attributes starting with an underscore are excluded from the
            representation.

            :return: A string representation of the object's attributes in an ordered
                  dictionary format.
            :rtype: str
            """
            items = ", ".join(
                f"{attr!r}: {value!r}" for attr, value in self._ordered_items()
            )
            return f"{{{items}}}"

        return f"{self.__class__.__name__}({_ordered_dict_repr()})"

    def __str__(self) -> str:
        """Return a string representation of the match object.

        The string includes the offset, error length, rule ID, message, suggestions, and
        context with a visual indicator of the error position.

        :return: A formatted string describing the match object.
        :rtype: str
        """
        rule_id = self.rule_id
        s = f"Offset {self.offset}, length {self.error_length}, Rule ID: {rule_id}"
        if self.message:
            s += f"\nMessage: {self.message}"
        if self.replacements:
            s += f"\nSuggestion: {'; '.join(self.replacements)}"
        s += (
            f"\n{self.context}\n"
            f"{' ' * self.offset_in_context + '^' * self.error_length}"
        )
        return s

    @property
    def matched_text(self) -> str:
        """Return the substring from the context that corresponds to the matched text.

        :return: The matched text from the context.
        :rtype: str
        """
        return self.context[
            self.offset_in_context : self.offset_in_context + self.error_length
        ]

    def get_line_and_column(self, original_text: str) -> tuple[int, int]:
        """Return the line and column number of the error in the context.

        :param original_text: The original text in which the error occurred. We need
            this to calculate the line and column number, because the context has no
            more newline characters.
        :type original_text: str
        :return: A tuple containing the line and column number of the error.
        :rtype: tuple[int, int]
        :raises ValueError: If the original text does not contain the match context.
        """
        context_without_additions = (
            self.context[CONTEXT_PREFIX_SUFFIX_LENGTH:-CONTEXT_PREFIX_SUFFIX_LENGTH]
            if len(self.context) > CONTEXT_WITH_ADDITIONS_MIN_LENGTH
            else self.context
        )
        if context_without_additions not in original_text.replace("\n", " "):
            err = "The original text does not match the context of the error"
            raise ValueError(err)
        line = original_text.count("\n", 0, self.offset)
        column = self.offset - original_text.rfind("\n", 0, self.offset)
        return line + 1, column

    def select_replacement(self, index: int) -> None:
        """Keep only the replacement selected by the given index.

        :param index: The index of the replacement to select.
        :type index: int
        :raises ValueError: If there are no replacement suggestions.
        :raises ValueError: If the index is out of the valid range.
        """
        if not self.replacements:
            err = "This Match has no suggestions"
            raise ValueError(err)
        if index < 0 or index >= len(self.replacements):
            err = (
                f"This Match's suggestions are numbered from 0"
                f"to {len(self.replacements) - 1}"
            )
            raise ValueError(err)
        self.replacements = [self.replacements[index]]

    def __eq__(self, other: object) -> bool:
        """Compare this object with another for equality.

        :param other: The object to compare with.
        :type other: object
        :return: True if both objects are equal, False otherwise.
        :rtype: bool
        """
        if not isinstance(other, Match):
            return NotImplemented
        return list(self) == list(other)

    def __lt__(self, other: object) -> bool:
        """Compare this object with another object for less-than ordering.

        :param other: The object to compare with.
        :type other: object
        :return: True if this object is less than the other object, False otherwise.
        :rtype: bool
        """
        if not isinstance(other, Match):
            return NotImplemented
        return list(self) < list(other)

    def __iter__(self) -> Iterator[MatchValue]:
        """Return an iterator over the attributes of the match object.

        This method allows the match object to be iterated over, yielding the values of
        its attributes in the order defined by ``get_match_ordered_dict()``.

        :return: An iterator over the attribute values of the match object.
        :rtype: Iterator[str | int | list[str]]
        """
        return iter(value for _, value in self._ordered_items())

    def __setattr__(self, key: str, value: MatchValue) -> None:
        """Set an attribute on the instance.

        This method overrides the default behavior of setting an attribute. It attempts
        to transform the value using a function from ``get_match_ordered_dict()`` based
        on the provided key. If the key is not found in the dictionary, the attribute is
        not set.

        :param key: The name of the attribute to set.
        :type key: str
        :param value: The value to set the attribute to.
        :type value: str | int | list[str]
        """
        try:
            # Ex: if key is "offset", get_match_ordered_dict()[key] will return int, so
            # the value will be transformed to int
            value = get_match_ordered_dict()[key](value)
        except KeyError:
            return
        super().__setattr__(key, value)

    def __getattr__(self, name: str) -> None:
        """Handle attribute access for undefined attributes.

        This method is called when an attribute lookup has not found the attribute in
        the usual places (i.e., it is not an instance attribute nor is it found in the
        class tree for self). This method checks if the attribute name is in the ordered
        dictionary returned by ``get_match_ordered_dict()``. If the attribute name is
        not found, it raises an AttributeError.

        :param name: The name of the attribute being accessed.
        :type name: str
        :return: None for known unset match fields.
        :rtype: None
        :raises AttributeError: If the attribute does not exist.
        """
        if name not in get_match_ordered_dict():
            err = f"{self.__class__.__name__!r} object has no attribute {name!r}"
            raise AttributeError(err)
