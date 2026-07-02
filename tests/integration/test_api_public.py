"""Integration tests for the public API functionality."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

import language_tool_python
from language_tool_python.exceptions import RateLimitError

if TYPE_CHECKING:
    from language_tool_python.match import Match

_ES_TEXT = (
    "Escriba un texto aquí. LanguageTool le ayudará a afrentar "
    "algunas dificultades propias de la escritura. Se a hecho un esfuerzo "
    "para detectar errores tipográficos, ortograficos y incluso "
    "gramaticales. También algunos errores de estilo, a grosso modo."
)


@pytest.fixture(scope="module")
def es_matches() -> list[Match]:
    """Check ``_ES_TEXT`` once against the public API and share the result.

    The check is only performed once (module-scoped) to limit the number of
    requests sent to the public API. If the request is rate-limited, every test
    depending on this fixture is skipped silently rather than failing.
    """
    try:
        with language_tool_python.LanguageToolPublicAPI("es") as tool:
            return tool.check(_ES_TEXT)
    except RateLimitError:
        pytest.skip("Rate limit exceeded for public API.")


@pytest.mark.parametrize(
    ("rule_id", "category", "offset"),
    [
        ("AFRENTAR_DIFICULTADES", "INCORRECT_EXPRESSIONS", 49),
        ("PRON_HABER_PARTICIPIO", "MISSPELLING", 107),
        ("MORFOLOGIK_RULE_ES", "TYPOS", 163),
        ("Y_E_O_U", "GRAMMAR", 176),
        ("GROSSO_MODO", "GRAMMAR", 235),
    ],
)
def test_remote_es(
    es_matches: list[Match],
    rule_id: str,
    category: str,
    offset: int,
) -> None:
    """Test that the public API detects a specific known error in Spanish text.

    LanguageTool rules can change over time, so this asserts on individual match
    fields (rule_id, category, offset) rather than requiring the entire response
    to match a frozen snapshot exactly.

    :raises AssertionError: If no match with the expected fields is found.
    """
    assert any(
        m.rule_id == rule_id and m.category == category and m.offset == offset
        for m in es_matches
    )
