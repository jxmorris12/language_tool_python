"""LanguageTool API for Python."""

__all__ = [
    'LanguageTool',
    'LanguageToolPublicAPI',
    'LanguageTag',
    'Match',
    'utils',
]

from .language_tag import LanguageTag
from .match import Match
from .server import LanguageTool, LanguageToolPublicAPI
from . import utils