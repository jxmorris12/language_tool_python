
def test_langtool_load():
	import language_tool_python
	lang_tool = language_tool_python.LanguageTool("en-US")
	matches = lang_tool.check('ain\'t nothin but a thang')
	assert str(matches) == """[Match({'ruleId': 'UPPERCASE_SENTENCE_START', 'message': 'This sentence does not start with an uppercase letter', 'replacements': ['Ain'], 'context': "ain't nothin but a thang", 'offset': 0, 'errorLength': 3, 'category': 'CASING', 'ruleIssueType': 'typographical'}), Match({'ruleId': 'MORFOLOGIK_RULE_EN_US', 'message': 'Possible spelling mistake found.', 'replacements': ['nothing', 'no thin'], 'context': "ain't nothin but a thang", 'offset': 6, 'errorLength': 6, 'category': 'TYPOS', 'ruleIssueType': 'misspelling'}), Match({'ruleId': 'MORFOLOGIK_RULE_EN_US', 'message': 'Possible spelling mistake found.', 'replacements': ['than', 'thing', 'hang', 'thank', 'Chang', 'tang', 'thong', 'twang', 'Thant', 'thane', 'Thanh', 't hang', 'than g', 'Shang', 'Zhang'], 'context': "ain't nothin but a thang", 'offset': 19, 'errorLength': 5, 'category': 'TYPOS', 'ruleIssueType': 'misspelling'})]"""

def test_match():
	import language_tool_python
	tool = language_tool_python.LanguageTool('en-US')
	text = u'A sentence with a error in the Hitchhiker’s Guide tot he Galaxy'
	matches = tool.check(text)
	assert len(matches) == 2
	assert str(matches[0]) == 'Offset 16, length 1, Rule ID: EN_A_VS_AN\nMessage: Use "an" instead of \'a\' if the following word starts with a vowel sound, e.g. \'an article\', \'an hour\'\nSuggestion: an\nA sentence with a error in the Hitchhiker’s Guide tot he ...\n                ^'


def test_remote_es():
	import language_tool_python
	tool = language_tool_python.LanguageToolPublicAPI('es')
	es_text = 'Escriba un texto aquí. LanguageTool le ayudará a afrentar algunas dificultades propias de la escritura. Se a hecho un esfuerzo para detectar errores tipográficos, ortograficos y incluso gramaticales. También algunos errores de estilo, a grosso modo.'

	print('Spell-checking in [ES] using LanguageTool Public API:')
	matches = tool.check(es_text)
	print('num es matches:', len(matches))
	assert str(matches) == """[Match({'ruleId': 'AFRENTAR_DIFICULTADES', 'message': 'La forma correcta es usando el verbo «afrontar»: "afrontar algunas dificultades""', 'replacements': ['afrontar algunas dificultades'], 'context': '...n texto aquí. LanguageTool le ayudará a afrentar algunas dificultades propias de la escritura. Se a hecho un ...', 'offset': 49, 'errorLength': 29, 'category': 'INCORRECT_EXPRESSIONS', 'ruleIssueType': 'grammar'}), Match({'ruleId': 'PRON_HABER_PARTICIPIO', 'message': "El v. 'haber' se escribe con hache.", 'replacements': ['ha'], 'context': '...ificultades propias de la escritura. Se a hecho un esfuerzo para detectar errores...', 'offset': 107, 'errorLength': 1, 'category': 'MISSPELLING', 'ruleIssueType': 'misspelling'}), Match({'ruleId': 'MORFOLOGIK_RULE_ES', 'message': 'Se ha encontrado un posible error ortográfico.', 'replacements': ['ortográficos', 'ortográficas', 'ortográfico', 'orográficos', 'ortografiaos', 'ortografíeos'], 'context': '...rzo para detectar errores tipográficos, ortograficos y incluso gramaticales. También algunos...', 'offset': 163, 'errorLength': 12, 'category': 'TYPOS', 'ruleIssueType': 'misspelling'}), Match({'ruleId': 'Y_E', 'message': 'Cuando precede a palabras que comienzan por «i-» (o «hi-»), la conjunción «y» se transforma en «e».', 'replacements': ['e incluso'], 'context': '...ctar errores tipográficos, ortograficos y incluso gramaticales. También algunos errores d...', 'offset': 176, 'errorLength': 9, 'category': 'GRAMMAR', 'ruleIssueType': 'grammar'}), Match({'ruleId': 'GROSSO_MODO', 'message': 'Esta expresión latina se usa sin preposición.', 'replacements': ['grosso modo'], 'context': '...les. También algunos errores de estilo, a grosso modo.', 'offset': 235, 'errorLength': 13, 'category': 'GRAMMAR', 'ruleIssueType': 'grammar'})]"""

def test_correct_en_us():
	import language_tool_python
	tool = language_tool_python.LanguageTool('en-US')

	matches = tool.check('cz of this brand is awsome,,i love this brand very much')
	assert len(matches) == 4
	assert str(matches) == """[Match({'ruleId': 'UPPERCASE_SENTENCE_START', 'message': 'This sentence does not start with an uppercase letter', 'replacements': ['Cz'], 'context': 'cz of this brand is awsome,,i love this br...', 'offset': 0, 'errorLength': 2, 'category': 'CASING', 'ruleIssueType': 'typographical'}), Match({'ruleId': 'MORFOLOGIK_RULE_EN_US', 'message': 'Possible spelling mistake found.', 'replacements': ['awesome', 'aw some'], 'context': 'cz of this brand is awsome,,i love this brand very much', 'offset': 20, 'errorLength': 6, 'category': 'TYPOS', 'ruleIssueType': 'misspelling'}), Match({'ruleId': 'DOUBLE_PUNCTUATION', 'message': 'Two consecutive commas', 'replacements': [','], 'context': 'cz of this brand is awsome,,i love this brand very much', 'offset': 26, 'errorLength': 2, 'category': 'PUNCTUATION', 'ruleIssueType': 'typographical'}), Match({'ruleId': 'I_LOWERCASE', 'message': 'Is this the personal pronoun "I"? It is spelled uppercase.', 'replacements': ['I'], 'context': 'cz of this brand is awsome,,i love this brand very much', 'offset': 28, 'errorLength': 1, 'category': 'TYPOS', 'ruleIssueType': 'misspelling'})]"""

	assert tool.correct('cz of this brand is awsome,,i love this brand very much') == 'Cz of this brand is awesome,I love this brand very much'

def test_spellcheck_en_gb():
	import language_tool_python

	s = 'Wat is wrong with the spll chker'

	# Correct a sentence with spell-checking
	tool = language_tool_python.LanguageTool('en-GB')
	assert tool.correct(s) == "Was is wrong with the sell cheer"

	# Correct a sentence without spell-checking
	tool.disable_spellchecking()
	assert tool.correct(s) == "Wat is wrong with the spll chker"