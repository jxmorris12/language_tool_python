"""Utility functions for the LanguageTool library."""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .match import Match

__all__ = ["TextStatus", "classify_matches", "correct"]


class TextStatus(Enum):
    """Status classification for matches."""

    CORRECT = "correct"
    FAULTY = "faulty"
    GARBAGE = "garbage"


def classify_matches(matches: list[Match]) -> TextStatus:
    """Classify matches as CORRECT, FAULTY, or GARBAGE.

    This function checks the status of the matches and returns a corresponding
    :class:`TextStatus` value.

    :param matches: A list of Match objects to be classified.
    :type matches: list[Match]
    :return: The classification of the matches as a :class:`TextStatus` value.
    :rtype: TextStatus
    """
    if not len(matches):
        return TextStatus.CORRECT
    matches = [match for match in matches if match.replacements]
    if not matches:
        return TextStatus.GARBAGE
    return TextStatus.FAULTY


def correct(text: str, matches: list[Match]) -> str:
    """Corrects the given text based on the provided matches.

    Only the first replacement for each match is applied to the text.

    :param text: The original text to be corrected.
    :type text: str
    :param matches: A list of Match objects that contain the positions and replacements
        for errors in the text.
    :type matches: list[Match]
    :return: The corrected text.
    :rtype: str
    """
    ltext = list(text)
    matches = [match for match in matches if match.replacements]
    errors = [
        ltext[match.offset : match.offset + match.error_length] for match in matches
    ]
    correct_offset = 0
    for n, match in enumerate(matches):
        frompos, topos = (
            correct_offset + match.offset,
            correct_offset + match.offset + match.error_length,
        )
        if ltext[frompos:topos] != errors[n]:
            continue
        repl = match.replacements[0]
        ltext[frompos:topos] = list(repl)
        correct_offset += len(repl) - len(errors[n])
    return "".join(ltext)
