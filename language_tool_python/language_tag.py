import re

from functools import total_ordering

@total_ordering
class LanguageTag:
    """Language tag supported by LanguageTool."""
    _LANGUAGE_RE = re.compile(r"^([a-z]{2,3})(?:[_-]([a-z]{2}))?$", re.I)

    def __init__(self, tag, languages):
        self.tag = tag
        self.languages = languages
        self.normalized_tag = self._normalize(tag)

    def __eq__(self, other_tag):
        return self.normalized_tag == self._normalize(other_tag)

    def __lt__(self, other_tag):
        return str(self) < self._normalize(other)

    def __str__(self):
        return self.normalized_tag

    def __repr__(self):
        return '<LanguageTag "{}">'.format(str(self))

    def _normalize(self, tag):
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
                raise ValueError('unsupported language: {!r}'.format(tag))
