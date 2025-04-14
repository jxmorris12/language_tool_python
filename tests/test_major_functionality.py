import re
import subprocess
import time

import pytest

from language_tool_python.utils import LanguageToolError, RateLimitError


# THESE TESTS ARE SUPPOSED TO BE RUN WITH 6.7-SNAPSHOT VERSION OF LT SERVER


def test_langtool_load():
    import language_tool_python
    with language_tool_python.LanguageTool("en-US") as tool:
        matches = tool.check('ain\'t nothin but a thang')

        expected_matches = [
            {
                'ruleId': 'UPPERCASE_SENTENCE_START',
                'message': 'This sentence does not start with an uppercase letter.',
                'replacements': ['Ai'],
                'offsetInContext': 0,
                'context': "ain't nothin but a thang",
                'offset': 0, 'errorLength': 2,
                'category': 'CASING', 'ruleIssueType': 'typographical',
                'sentence': "ain't nothin but a thang"
            },
            {
                'ruleId': 'MORFOLOGIK_RULE_EN_US',
                'message': 'Possible spelling mistake found.',
                'replacements': ['nothing', 'no thin'],
                'offsetInContext': 6,
                'context': "ain't nothin but a thang",
                'offset': 6, 'errorLength': 6,
                'category': 'TYPOS', 'ruleIssueType': 'misspelling',
                'sentence': "ain't nothin but a thang"
            },
            {
                'ruleId': 'MORFOLOGIK_RULE_EN_US',
                'message': 'Possible spelling mistake found.',
                'replacements': [
                    'than', 'thing', 'Zhang', 'hang', 'thank', 'Chang', 'tang', 'thong',
                    'twang', 'Thant', 'thane', 'Jhang', 'Shang', 'Thanh', 'bhang',
                ],
                'offsetInContext': 19,
                'context': "ain't nothin but a thang",
                'offset': 19, 'errorLength': 5,
                'category': 'TYPOS', 'ruleIssueType': 'misspelling',
                'sentence': "ain't nothin but a thang"
            }
        ]

        assert len(matches) == len(expected_matches)
        for match_i, match in enumerate(matches):
            assert isinstance(match, language_tool_python.Match)
            for key in [
                'ruleId', 'message', 'offsetInContext',
                'context', 'offset', 'errorLength', 'category', 'ruleIssueType',
                'sentence'
            ]:
                assert expected_matches[match_i][key] == getattr(match, key)

            # For replacements we allow some flexibility in the order
            # of the suggestions depending on the version of LT.
            for key in [
                'replacements',
            ]:
                assert (
                    set(expected_matches[match_i][key]) == set(getattr(match, key))
                )


def test_process_starts_and_stops_in_context_manager():
    import language_tool_python
    with language_tool_python.LanguageTool("en-US") as tool:
        proc: subprocess.Popen = tool._server
        # Make sure process is running before killing language tool object.
        assert proc.poll() is None, "tool._server not running after creation"
    # Make sure process stopped after close() was called.
    assert proc.poll() is not None, "tool._server should stop running after deletion"


def test_process_starts_and_stops_on_close():
    import language_tool_python
    tool = language_tool_python.LanguageTool("en-US")
    proc: subprocess.Popen = tool._server
    # Make sure process is running before killing language tool object.
    assert proc.poll() is None, "tool._server not running after creation"
    tool.close()  # Explicitly close() object so process stops before garbage collection.
    del tool
    # Make sure process stopped after close() was called.
    assert proc.poll() is not None, "tool._server should stop running after deletion"
    # remember --> if poll is None: # p.subprocess is alive


def test_local_client_server_connection():
    import language_tool_python
    with language_tool_python.LanguageTool('en-US', host='127.0.0.1') as tool1:
        url = 'http://{}:{}/'.format(tool1._host, tool1._port)
        with language_tool_python.LanguageTool('en-US', remote_server=url) as tool2:
            assert len(tool2.check('helo darknes my old frend'))


def test_config_text_length():
    import language_tool_python
    with language_tool_python.LanguageTool('en-US', config={'maxTextLength': 12 }) as tool:
        # With this config file, checking text with >12 characters should raise an error.
        error_msg = re.escape("Error: Your text exceeds the limit of 12 characters (it's 27 characters). Please submit a shorter text.")
        with pytest.raises(LanguageToolError, match=error_msg):
            tool.check('Hello darkness my old frend')
        # But checking shorter text should work fine.
        # (should have 1 match for this one)
        assert len(tool.check('Hello darkne'))


def test_config_caching():
    import language_tool_python
    with language_tool_python.LanguageTool('en-US', config={'cacheSize': 1000, 'pipelineCaching': True}) as tool:
        s = 'hello darkness my old frend'
        t1 = time.time()
        tool.check(s)
        t2 = time.time()
        tool.check(s)
        t3 = time.time()

        # This is a silly test that says: caching should speed up a grammary-checking by a factor
        # of speed_factor when checking the same sentence twice. It theoretically could be very flaky.
        # But in practice I've observed speedup of around 250x (6.76s to 0.028s).
        speedup_factor = 10.0
        assert (t2 - t1) / speedup_factor > (t3 - t2)


def test_langtool_languages():
    import language_tool_python
    with language_tool_python.LanguageTool("en-US") as tool:
        assert tool._get_languages().issuperset(
            {
                'es-AR', 'ast-ES', 'fa', 'ar', 'ja', 'pl', 'en-ZA', 'sl', 'be-BY',
                'gl', 'de-DE-x-simple-language-DE', 'ga', 'da-DK',
                'ca-ES-valencia', 'eo', 'pt-PT', 'ro', 'fr-FR', 'sv-SE', 'br-FR',
                'es-ES', 'be', 'de-CH', 'pl-PL', 'it-IT',
                'de-DE-x-simple-language', 'en-NZ', 'sv', 'auto', 'km', 'pt',
                'da', 'ta-IN', 'de', 'fa-IR', 'ca', 'de-AT', 'de-DE', 'sk', 'ta',
                'uk', 'en-US', 'zh', 'uk-UA', 'pt-AO', 'el-GR', 'br',
                'ca-ES-balear', 'fr', 'sk-SK', 'pt-BR', 'ro-RO', 'it', 'es',
                'ru-RU', 'km-KH', 'en-GB', 'sl-SI', 'gl-ES', 'pt-MZ', 'nl', 'el',
                'ca-ES', 'zh-CN', 'de-LU', 'nl-NL', 'ja-JP', 'ast', 'tl', 'ga-IE',
                'en-AU', 'en', 'ru', 'nl-BE', 'en-CA', 'tl-PH'
            }
        )


def test_match():
    import language_tool_python
    with language_tool_python.LanguageTool('en-US') as tool:
        text = u'A sentence with a error in the Hitchhiker’s Guide tot he Galaxy'
        matches = tool.check(text)
        assert len(matches) == 2
        assert str(matches[0]) == (
            'Offset 16, length 1, Rule ID: EN_A_VS_AN\n'
            'Message: Use “an” instead of ‘a’ if the following word starts with a vowel sound, e.g. ‘an article’, ‘an hour’.\n'
            'Suggestion: an\n'
            'A sentence with a error in the Hitchhiker’s Guide tot he ...'
            '\n                ^'
        )


def test_uk_typo():
    import language_tool_python
    with language_tool_python.LanguageTool("en-UK") as tool:
        sentence1 = "If you think this sentence is fine then, your wrong."
        results1 = tool.check(sentence1)
        assert len(results1) == 1
        assert language_tool_python.utils.correct(sentence1, results1) == "If you think this sentence is fine then, you're wrong."

        results2 = tool.check("You're mum is called Emily, is that right?")
        assert len(results2) == 0


def test_remote_es():
    import language_tool_python
    try:
        with language_tool_python.LanguageToolPublicAPI('es') as tool:
            es_text = 'Escriba un texto aquí. LanguageTool le ayudará a afrentar algunas dificultades propias de la escritura. Se a hecho un esfuerzo para detectar errores tipográficos, ortograficos y incluso gramaticales. También algunos errores de estilo, a grosso modo.'
            matches = tool.check(es_text)
            assert str(matches) == """[Match({'ruleId': 'AFRENTAR_DIFICULTADES', 'message': 'Confusión entre «afrontar» y «afrentar».', 'replacements': ['afrontar'], 'offsetInContext': 43, 'context': '...n texto aquí. LanguageTool le ayudará a afrentar algunas dificultades propias de la escr...', 'offset': 49, 'errorLength': 8, 'category': 'INCORRECT_EXPRESSIONS', 'ruleIssueType': 'grammar', 'sentence': 'LanguageTool le ayudará a afrentar algunas dificultades propias de la escritura.'}), Match({'ruleId': 'PRON_HABER_PARTICIPIO', 'message': 'El v. ‘haber’ se escribe con hache.', 'replacements': ['ha'], 'offsetInContext': 43, 'context': '...ificultades propias de la escritura. Se a hecho un esfuerzo para detectar errores...', 'offset': 107, 'errorLength': 1, 'category': 'MISSPELLING', 'ruleIssueType': 'misspelling', 'sentence': 'Se a hecho un esfuerzo para detectar errores tipográficos, ortograficos y incluso gramaticales.'}), Match({'ruleId': 'MORFOLOGIK_RULE_ES', 'message': 'Se ha encontrado un posible error ortográfico.', 'replacements': ['ortográficos', 'ortográficas', 'ortográfico', 'orográficos', 'ortografiaos', 'ortografíeos'], 'offsetInContext': 43, 'context': '...rzo para detectar errores tipográficos, ortograficos y incluso gramaticales. También algunos...', 'offset': 163, 'errorLength': 12, 'category': 'TYPOS', 'ruleIssueType': 'misspelling', 'sentence': 'Se a hecho un esfuerzo para detectar errores tipográficos, ortograficos y incluso gramaticales.'}), Match({'ruleId': 'Y_E_O_U', 'message': 'Cuando precede a palabras que comienzan por ‘i’, la conjunción ‘y’ se transforma en ‘e’.', 'replacements': ['e'], 'offsetInContext': 43, 'context': '...ctar errores tipográficos, ortograficos y incluso gramaticales. También algunos e...', 'offset': 176, 'errorLength': 1, 'category': 'GRAMMAR', 'ruleIssueType': 'grammar', 'sentence': 'Se a hecho un esfuerzo para detectar errores tipográficos, ortograficos y incluso gramaticales.'}), Match({'ruleId': 'GROSSO_MODO', 'message': 'Esta expresión latina se usa sin preposición.', 'replacements': ['grosso modo'], 'offsetInContext': 43, 'context': '...les. También algunos errores de estilo, a grosso modo.', 'offset': 235, 'errorLength': 13, 'category': 'GRAMMAR', 'ruleIssueType': 'grammar', 'sentence': 'También algunos errores de estilo, a grosso modo.'})]"""
    except RateLimitError:
        print("Rate limit error: skipping test about public API.")
        return


def test_correct_en_us():
    import language_tool_python
    with language_tool_python.LanguageTool('en-US') as tool:
        matches = tool.check('cz of this brand is awsome,,i love this brand very much')
        assert len(matches) == 4

        assert tool.correct('cz of this brand is awsome,,i love this brand very much') == 'CZ of this brand is awesome,I love this brand very much'


def test_spellcheck_en_gb():
    import language_tool_python

    s = 'Wat is wrong with the spll chker'

    # Correct a sentence with spell-checking
    with language_tool_python.LanguageTool('en-GB') as tool:
        assert tool.correct(s) == "Was is wrong with the sell cheer"

        # Correct a sentence without spell-checking
        tool.disable_spellchecking()
        assert tool.correct(s) == "Wat is wrong with the spll chker"


def test_session_only_new_spellings():
    import os
    import hashlib
    import language_tool_python
    library_path = language_tool_python.utils.get_language_tool_directory()
    spelling_file_path = os.path.join(
        library_path, "org/languagetool/resource/en/hunspell/spelling.txt"
    )
    with open(spelling_file_path, 'r') as spelling_file:
        initial_spelling_file_contents = spelling_file.read()
    initial_checksum = hashlib.sha256(initial_spelling_file_contents.encode())

    new_spellings = ["word1", "word2", "word3"]
    with language_tool_python.LanguageTool(
        'en-US', newSpellings=new_spellings, new_spellings_persist=False
    ) as tool:
        tool.enabled_rules_only = True
        tool.enabled_rules = {'MORFOLOGIK_RULE_EN_US'}
        matches = tool.check(" ".join(new_spellings))

    with open(spelling_file_path, 'r') as spelling_file:
        subsequent_spelling_file_contents = spelling_file.read()
    subsequent_checksum = hashlib.sha256(
        subsequent_spelling_file_contents.encode()
    )

    if initial_checksum != subsequent_checksum:
        with open(spelling_file_path, 'w') as spelling_file:
            spelling_file.write(initial_spelling_file_contents)

    assert not matches
    assert initial_checksum.hexdigest() == subsequent_checksum.hexdigest()


def test_disabled_rule_in_config():
    import language_tool_python
    GRAMMAR_TOOL_CONFIG = {
        'disabledRuleIds': ['MORFOLOGIK_RULE_EN_US']
    }
    with language_tool_python.LanguageTool('en-US', config=GRAMMAR_TOOL_CONFIG) as tool:
        text = "He realised that the organization was in jeopardy."
        matches = tool.check(text)
        assert len(matches) == 0

def test_special_char_in_text():
    import language_tool_python
    with language_tool_python.LanguageTool('en-US') as tool:
        text = "The sun was seting 🌅, casting a warm glow over the park. Birds chirpped softly 🐦 as the day slowly fade into night."
        assert tool.correct(text) == "The sun was setting 🌅, casting a warm glow over the park. Birds chipped softly 🐦 as the day slowly fade into night."

def test_install_inexistent_version():
    import language_tool_python
    with pytest.raises(LanguageToolError):
        language_tool_python.LanguageTool(language_tool_download_version="0.0")
    
def test_inexistant_language():
    import language_tool_python
    with language_tool_python.LanguageTool("en-US") as tool:
        with pytest.raises(ValueError):
            language_tool_python.LanguageTag("xx-XX", tool._get_languages())


def test_debug_mode():
    from language_tool_python.server import DEBUG_MODE
    assert DEBUG_MODE is False
