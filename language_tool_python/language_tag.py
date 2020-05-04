import re

from .utils import get_languages

from functools import total_ordering

@total_ordering
class LanguageTag(str):

    """Language tag supported by LanguageTool."""
    _LANGUAGE_RE = re.compile(r"^([a-z]{2,3})(?:[_-]([a-z]{2}))?$", re.I)

    def __new__(cls, tag):
        # Can't use super() here because of 3to2.
        return str.__new__(cls, cls._normalize(tag))

    def __eq__(self, other):
        try:
            other = self._normalize(other)
        except ValueError:
            pass
        return str(self) == other

    def __lt__(self, other):
        try:
            other = self._normalize(other)
        except ValueError:
            pass
        return str(self) < other

    @classmethod
    def _normalize(cls, tag):
        if not tag:
            raise ValueError('empty language tag')
        languages = {language.lower().replace('-', '_'): language
                     for language in get_languages()}
        try:
            return languages[tag.lower().replace('-', '_')]
        except KeyError:
            try:
                return languages[cls._LANGUAGE_RE.match(tag).group(1).lower()]
            except (KeyError, AttributeError):
                raise ValueError('unsupported language: {!r}'.format(tag))
