"""LanguageTool through server mode.

    migration URL: https://languagetool.org/http-api/migration.php
"""

from .language_tag import LanguageTag
from .match import Match
from .server import LanguageTool, LanguageToolPublicAPI
from . import utils