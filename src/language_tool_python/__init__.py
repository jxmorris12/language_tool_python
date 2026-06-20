"""LanguageTool API for Python."""

__all__ = [
    "LanguageTag",
    "LanguageTool",
    "LanguageToolPublicAPI",
    "Match",
    "exceptions",
    "utils",
]

import logging

from . import exceptions, utils
from .language_tag import LanguageTag
from .match import Match
from .server import LanguageTool, LanguageToolPublicAPI

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())
