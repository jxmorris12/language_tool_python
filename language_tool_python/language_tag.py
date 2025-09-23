"""LanguageTool language tag normalization module."""

import re
from typing import Iterable, Any
from functools import total_ordering

@total_ordering
class LanguageTag:
    """
    A class to represent and normalize language tags.

    :param tag: The language tag.
    :type tag: str
    :param languages: An iterable of supported language tags.
    :type languages: Iterable[str]

    Attributes:
        tag (str): The language tag to be normalized.
        languages (Iterable[str]): An iterable of supported language tags.
        normalized_tag (str): The normalized language tag.
        _LANGUAGE_RE (re.Pattern): A regular expression to match language tags. 
    """
    _LANGUAGE_RE = re.compile(r"^([a-z]{2,3})(?:[_-]([a-z]{2}))?$", re.I)

    def __init__(self, tag: str, languages: Iterable[str]) -> None:
        """
        Initialize a LanguageTag instance.
        """
        self.tag = tag
        self.languages = languages
        self.normalized_tag = self._normalize(tag)

    def __eq__(self, other: Any) -> bool:
        """
        Compare this LanguageTag object with another for equality.

        :param other: The other object to compare with.
        :type other: Any
        :return: True if the normalized tags are equal, False otherwise.
        :rtype: bool
        """
        return self.normalized_tag == self._normalize(other)

    def __lt__(self, other: Any) -> bool:
        """
        Compare this object with another for less-than ordering.

        :param other: The object to compare with.
        :type other: Any
        :return: True if this object is less than the other, False otherwise.
        :rtype: bool
        """
        return str(self) < self._normalize(other)

    def __str__(self) -> str:
        """
        Returns the string representation of the object.

        :return: The normalized tag as a string.
        :rtype: str
        """
        return self.normalized_tag

    def __repr__(self) -> str:
        """
        Return a string representation of the LanguageTag instance.

        :return: A string in the format '<LanguageTag "language_tag_string">'
        :rtype: str
        """
        return f'<LanguageTag "{str(self)}">'

    def _normalize(self, tag: str) -> str:
        """
        Normalize a language tag to a standard format.

        :param tag: The language tag to normalize.
        :type tag: str
        :raises ValueError: If the tag is empty or unsupported.
        :return: The normalized language tag.
        :rtype: str
        """
        if not tag:
            raise ValueError('empty language tag')
        languages = {language.lower().replace('-', '_'): language
                     for language in self.languages}
        try:
            return languages[tag.lower().replace('-', '_')]
        except KeyError:
            try:
                return languages[self._LANGUAGE_RE.match(tag).group(1).lower()]
            except (KeyError, AttributeError):
                raise ValueError(f'unsupported language: {tag!r}')
