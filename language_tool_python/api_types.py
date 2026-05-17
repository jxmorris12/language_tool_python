"""Typed representations of LanguageTool API responses."""

from __future__ import annotations

from typing import TypedDict

__all__ = [
    "Category",
    "CheckMatch",
    "CheckResponse",
    "Context",
    "DetectedLanguage",
    "Language",
    "LanguageInfo",
    "MatchType",
    "Replacement",
    "Rule",
    "WarningInfo",
    "is_check_response",
    "is_language_info",
]


class LanguageInfo(TypedDict):
    """Language metadata returned by the LanguageTool languages endpoint."""

    code: str
    longCode: str
    name: str


def is_language_info(value: object) -> bool:  # No TypeGuard because py3.9
    """Verify that a value is a LanguageInfo.

    :param value: The value to check.
    :type value: object
    :return: True if the value is a LanguageInfo, False otherwise.
    :rtype: bool
    """
    if not isinstance(value, dict):
        return False

    return (
        isinstance(value.get("code"), str)
        and isinstance(value.get("longCode"), str)
        and isinstance(value.get("name"), str)
    )


class _ReplacementOptional(TypedDict, total=False):
    shortDescription: str


class Replacement(_ReplacementOptional):
    """A suggested replacement returned by LanguageTool."""

    value: str


class Context(TypedDict):
    """Text context around a LanguageTool match."""

    text: str
    offset: int
    length: int


class Category(TypedDict):
    """LanguageTool rule category metadata."""

    id: str
    name: str


class _RuleOptional(TypedDict, total=False):
    sourceFile: str
    subId: str


class Rule(_RuleOptional):
    """LanguageTool rule metadata for a match."""

    id: str
    description: str
    issueType: str
    category: Category


class MatchType(TypedDict):
    """LanguageTool match type metadata."""

    typeName: str


class CheckMatch(TypedDict):
    """A raw match object returned by the LanguageTool check endpoint."""

    message: str
    shortMessage: str
    replacements: list[Replacement]
    offset: int
    length: int
    context: Context
    sentence: str
    type: MatchType
    rule: Rule
    ignoreForIncompleteSentence: bool
    contextForSureMatch: int


class DetectedLanguage(TypedDict):
    """Detected language metadata returned by LanguageTool."""

    code: str
    confidence: float
    name: str
    source: str


class Language(TypedDict):
    """Language metadata returned by the LanguageTool check endpoint."""

    code: str
    name: str
    detectedLanguage: DetectedLanguage


class WarningInfo(TypedDict):
    """Warning flags returned by LanguageTool."""

    incompleteResults: bool


class CheckResponse(TypedDict):
    """Raw JSON response returned by the LanguageTool check endpoint."""

    matches: list[CheckMatch]
    language: Language
    warnings: WarningInfo


def is_check_response(value: object) -> bool:  # No TypeGuard because py3.9
    """Verify that a value is a CheckResponse.

    :param value: The value to check.
    :type value: object
    :return: True if the value is a CheckResponse, False otherwise.
    :rtype: bool
    """
    if not isinstance(value, dict):
        return False

    return (
        isinstance(value.get("matches"), list)
        and isinstance(value.get("language"), dict)
        and isinstance(value.get("warnings"), dict)
    )
