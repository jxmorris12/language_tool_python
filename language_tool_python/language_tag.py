import re
from typing import Iterable, Any
from functools import total_ordering

@total_ordering
class LanguageTag:
    """Language tag supported by LanguageTool."""
    _LANGUAGE_RE = re.compile(r"^([a-z]{2,3})(?:[_-]([a-z]{2}))?$", re.I)

    def __init__(self, tag: str, languages: Iterable[str]) -> None:
        self.tag = tag
        self.languages = languages
        self.normalized_tag = self._normalize(tag)

    def __eq__(self, other: Any) -> bool:
        return self.normalized_tag == self._normalize(other_tag)

    def __lt__(self, other: Any) -> bool:
        return str(self) < self._normalize(other)

    def __str__(self) -> str:
        return self.normalized_tag

    def __repr__(self) -> str:
        return f'<LanguageTag "{str(self)}">'

    def _normalize(self, tag: str) -> str:
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
