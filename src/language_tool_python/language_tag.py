"""LanguageTool language tag normalization module."""

import logging
import re
from collections.abc import Iterable
from functools import total_ordering

__all__ = ["LanguageTag"]

logger = logging.getLogger(__name__)


@total_ordering
class LanguageTag:
    """A class to represent and normalize language tags.

    :param tag: The language tag.
    :type tag: str
    :param languages: An iterable of supported language tags.
    :type languages: collections.abc.Iterable[str]
    :raises ValueError: If the tag is empty or unsupported.
    """

    tag: str
    """The language tag to be normalized."""

    languages: Iterable[str]
    """An iterable of supported language tags."""

    normalized_tag: str
    """The normalized language tag."""

    _LANGUAGE_RE = re.compile(r"^([a-z]{2,3})(?:[_-]([a-z]{2}))?$", re.IGNORECASE)
    """A regular expression to match language tags."""

    def __init__(self, tag: str, languages: Iterable[str]) -> None:
        """Initialize a LanguageTag instance.

        :raises ValueError: If the tag is empty or unsupported.
        """
        self.tag = tag
        self.languages = languages
        self.normalized_tag = self._normalize(tag)

    def __eq__(self, other: object) -> bool:
        """Compare this LanguageTag object with another for equality.

        :param other: The other object to compare with.
        :type other: object
        :return: True if the normalized tags are equal, False otherwise.
        :rtype: bool
        :raises ValueError: If ``other`` is a string with an unsupported language tag.
        """
        if not isinstance(other, (str, LanguageTag)):
            return NotImplemented
        return self.normalized_tag == self._normalize(str(other))

    def __lt__(self, other: object) -> bool:
        """Compare this object with another for less-than ordering.

        :param other: The object to compare with.
        :type other: object
        :return: True if this object is less than the other, False otherwise.
        :rtype: bool
        :raises ValueError: If ``other`` is a string with an unsupported language tag.
        """
        if not isinstance(other, (str, LanguageTag)):
            return NotImplemented
        return str(self) < self._normalize(str(other))

    def __str__(self) -> str:
        """Return the string representation of the object.

        :return: The normalized tag as a string.
        :rtype: str
        """
        return self.normalized_tag

    def __repr__(self) -> str:
        """Return a string representation of the LanguageTag instance.

        :return: A string in the format '<LanguageTag "language_tag_string">'
        :rtype: str
        """
        return f'<LanguageTag "{self!s}">'

    def __hash__(self) -> int:
        """Return the hash of the LanguageTag instance.

        If the normalized tag is modified, the hash will change.

        :return: The hash of the normalized tag.
        :rtype: int
        """
        return hash(self.normalized_tag)

    def _normalize(self, tag: str) -> str:
        """Normalize a language tag to a standard format.

        :param tag: The language tag to normalize.
        :type tag: str
        :raises ValueError: If the tag is empty or unsupported.
        :return: The normalized language tag.
        :rtype: str
        """
        logger.debug("Normalizing language tag: %r", tag)

        if not tag:
            err = "empty language tag"
            raise ValueError(err)
        languages = {
            language.lower().replace("-", "_"): language for language in self.languages
        }
        logger.debug("Available languages: %s", list(languages.keys()))

        # If POSIX, default to English variants
        if tag.lower() in {"c", "posix"} or tag.lower().startswith("c."):
            logger.debug("Detected POSIX/C locale for tag %r", tag)
            for candidate in ("en_us", "en_gb", "en"):
                if candidate in languages:
                    logger.debug("Using POSIX fallback language %r", candidate)
                    return languages[candidate]
            err = f"unsupported language (no default for POSIX locale): {tag!r}"
            raise ValueError(err)

        try:
            return languages[tag.lower().replace("-", "_")]
        except KeyError as e:
            logger.debug("Tag %r not found directly, attempting regex match", tag)
            try:
                match = self._LANGUAGE_RE.match(tag)
                if match is None:
                    err = "tag does not match pattern"
                    raise AttributeError(err) from e
                logger.debug("Regex match groups: %s", match.groups())
                language_start, language_end = match.span(1)
                language = tag[language_start:language_end].lower()
                return languages[language]
            except (KeyError, AttributeError) as e:
                err = f"unsupported language: {tag!r}"
                raise ValueError(err) from e
