"""Tests for the public API functionality."""

from language_tool_python.exceptions import RateLimitError


def test_remote_es() -> None:
    """
    Test the public API with Spanish language text.
    This test verifies that the LanguageToolPublicAPI correctly identifies
    various errors in a Spanish text sample.

    :raises AssertionError: If the detected matches do not match the expected output.
    """
    import language_tool_python

    try:
        with language_tool_python.LanguageToolPublicAPI("es") as tool:
            es_text = "Escriba un texto aquí. LanguageTool le ayudará a afrentar algunas dificultades propias de la escritura. Se a hecho un esfuerzo para detectar errores tipográficos, ortograficos y incluso gramaticales. También algunos errores de estilo, a grosso modo."
            matches = tool.check(es_text)
            assert (
                str(matches)
                == """[Match({'rule_id': 'AFRENTAR_DIFICULTADES', 'message': 'Confusión entre «afrontar» y «afrentar».', 'replacements': ['afrontar'], 'offset_in_context': 43, 'context': '...n texto aquí. LanguageTool le ayudará a afrentar algunas dificultades propias de la escr...', 'offset': 49, 'error_length': 8, 'category': 'INCORRECT_EXPRESSIONS', 'rule_issue_type': 'grammar', 'sentence': 'LanguageTool le ayudará a afrentar algunas dificultades propias de la escritura.'}), Match({'rule_id': 'PRON_HABER_PARTICIPIO', 'message': 'El v. ‘haber’ se escribe con hache.', 'replacements': ['ha'], 'offset_in_context': 43, 'context': '...ificultades propias de la escritura. Se a hecho un esfuerzo para detectar errores...', 'offset': 107, 'error_length': 1, 'category': 'MISSPELLING', 'rule_issue_type': 'misspelling', 'sentence': 'Se a hecho un esfuerzo para detectar errores tipográficos, ortograficos y incluso gramaticales.'}), Match({'rule_id': 'MORFOLOGIK_RULE_ES', 'message': 'Se ha encontrado un posible error ortográfico.', 'replacements': ['ortográficos', 'ortográficas', 'ortográfico', 'orográficos', 'ortografiaos', 'ortografíeos'], 'offset_in_context': 43, 'context': '...rzo para detectar errores tipográficos, ortograficos y incluso gramaticales. También algunos...', 'offset': 163, 'error_length': 12, 'category': 'TYPOS', 'rule_issue_type': 'misspelling', 'sentence': 'Se a hecho un esfuerzo para detectar errores tipográficos, ortograficos y incluso gramaticales.'}), Match({'rule_id': 'Y_E_O_U', 'message': 'Cuando precede a palabras que comienzan por ‘i’, la conjunción ‘y’ se transforma en ‘e’.', 'replacements': ['e'], 'offset_in_context': 43, 'context': '...ctar errores tipográficos, ortograficos y incluso gramaticales. También algunos e...', 'offset': 176, 'error_length': 1, 'category': 'GRAMMAR', 'rule_issue_type': 'grammar', 'sentence': 'Se a hecho un esfuerzo para detectar errores tipográficos, ortograficos y incluso gramaticales.'}), Match({'rule_id': 'GROSSO_MODO', 'message': 'Esta expresión latina se usa sin preposición.', 'replacements': ['grosso modo'], 'offset_in_context': 43, 'context': '...les. También algunos errores de estilo, a grosso modo.', 'offset': 235, 'error_length': 13, 'category': 'GRAMMAR', 'rule_issue_type': 'grammar', 'sentence': 'También algunos errores de estilo, a grosso modo.'})]"""
            )
    except RateLimitError:
        print("Rate limit error: skipping test about public API.")
        return
