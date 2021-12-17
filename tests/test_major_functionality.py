
def test_langtool_load():
	import language_tool_python
	lang_tool = language_tool_python.LanguageTool("en-US")
	matches = lang_tool.check('ain\'t nothin but a thang')
	assert str(matches) == """[Match({'ruleId': 'UPPERCASE_SENTENCE_START', 'message': 'This sentence does not start with an uppercase letter.', 'replacements': ['Ai'], 'offsetInContext': 0, 'context': "ain't nothin but a thang", 'offset': 0, 'errorLength': 2, 'category': 'CASING', 'ruleIssueType': 'typographical', 'sentence': "ain't nothin but a thang"}), Match({'ruleId': 'MORFOLOGIK_RULE_EN_US', 'message': 'Possible spelling mistake found.', 'replacements': ['nothing', 'no thin'], 'offsetInContext': 6, 'context': "ain't nothin but a thang", 'offset': 6, 'errorLength': 6, 'category': 'TYPOS', 'ruleIssueType': 'misspelling', 'sentence': "ain't nothin but a thang"}), Match({'ruleId': 'MORFOLOGIK_RULE_EN_US', 'message': 'Possible spelling mistake found.', 'replacements': ['than', 'thing', 'hang', 'thank', 'Chang', 'tang', 'thong', 'twang', 'Thant', 'thane', 'Thanh', 'Jhang', 'Shang', 'Zhang'], 'offsetInContext': 19, 'context': "ain't nothin but a thang", 'offset': 19, 'errorLength': 5, 'category': 'TYPOS', 'ruleIssueType': 'misspelling', 'sentence': "ain't nothin but a thang"})]"""

def test_langtool_languages():
	import language_tool_python
	lang_tool = language_tool_python.LanguageTool("en-US")
	assert lang_tool._get_languages() == {'es-AR', 'ta-IN', 'en-CA', 'da', 'eo', 'pt-AO', 'de', 'gl', 'ru-RU', 'de-DE', 'en', 'br', 'en-ZA', 'pt-MZ', 'ast-ES', 'sk-SK', 'en-AU', 'ta', 'ga', 'be', 'pl', 'tl-PH', 'sl', 'ar', 'es', 'sl-SI', 'en-NZ', 'el', 'el-GR', 'ru', 'zh-CN', 'en-GB', 'be-BY', 'pl-PL', 'km-KH', 'pt', 'uk-UA', 'ca', 'de-DE-x-simple-language', 'ro', 'ca-ES', 'de-CH', 'ja-JP', 'tl', 'pt-PT', 'gl-ES', 'pt-BR', 'km', 'ga-IE', 'ja', 'sv', 'sk', 'en-US', 'de-AT', 'ca-ES-valencia', 'uk', 'it', 'zh', 'br-FR', 'da-DK', 'ast', 'fr', 'fa', 'nl', 'ro-RO', 'nl-BE'}

def test_match():
	import language_tool_python
	tool = language_tool_python.LanguageTool('en-US')
	text = u'A sentence with a error in the Hitchhiker’s Guide tot he Galaxy'
	matches = tool.check(text)
	assert len(matches) == 2
	assert str(matches[0]) == 'Offset 16, length 1, Rule ID: EN_A_VS_AN\nMessage: Use “an” instead of ‘a’ if the following word starts with a vowel sound, e.g. ‘an article’, ‘an hour’.\nSuggestion: an\nA sentence with a error in the Hitchhiker’s Guide tot he ...\n                ^'

def test_uk_typo():
	import language_tool_python
	language = language_tool_python.LanguageTool("en-UK")

	sentence1 = "If you think this sentence is fine then, your wrong."
	results1 = language.check(sentence1)
	assert len(results1) == 1
	assert language_tool_python.utils.correct(sentence1, results1) == "If you think this sentence is fine then, you're wrong."

	results2 = language.check("You're mum is called Emily, is that right?")
	assert len(results2) == 0

def test_remote_es():
	import language_tool_python
	tool = language_tool_python.LanguageToolPublicAPI('es')
	es_text = 'Escriba un texto aquí. LanguageTool le ayudará a afrentar algunas dificultades propias de la escritura. Se a hecho un esfuerzo para detectar errores tipográficos, ortograficos y incluso gramaticales. También algunos errores de estilo, a grosso modo.'
	matches = tool.check(es_text)
	assert str(matches) == """[Match({'ruleId': 'AFRENTAR_DIFICULTADES', 'message': 'Confusión entre «afrontar» y «afrentar».', 'replacements': ['afrontar'], 'offsetInContext': 43, 'context': '...n texto aquí. LanguageTool le ayudará a afrentar algunas dificultades propias de la escr...', 'offset': 49, 'errorLength': 8, 'category': 'INCORRECT_EXPRESSIONS', 'ruleIssueType': 'grammar', 'sentence': 'LanguageTool le ayudará a afrentar algunas dificultades propias de la escritura.'}), Match({'ruleId': 'PRON_HABER_PARTICIPIO', 'message': 'El v. ‘haber’ se escribe con hache.', 'replacements': ['ha'], 'offsetInContext': 43, 'context': '...ificultades propias de la escritura. Se a hecho un esfuerzo para detectar errores...', 'offset': 107, 'errorLength': 1, 'category': 'MISSPELLING', 'ruleIssueType': 'misspelling', 'sentence': 'Se a hecho un esfuerzo para detectar errores tipográficos, ortograficos y incluso gramaticales.'}), Match({'ruleId': 'MORFOLOGIK_RULE_ES', 'message': 'Se ha encontrado un posible error ortográfico.', 'replacements': ['ortográficos', 'ortográficas', 'ortográfico', 'orográficos', 'ortografiaos', 'ortografíeos'], 'offsetInContext': 43, 'context': '...rzo para detectar errores tipográficos, ortograficos y incluso gramaticales. También algunos...', 'offset': 163, 'errorLength': 12, 'category': 'TYPOS', 'ruleIssueType': 'misspelling', 'sentence': 'Se a hecho un esfuerzo para detectar errores tipográficos, ortograficos y incluso gramaticales.'}), Match({'ruleId': 'Y_E_O_U', 'message': 'Cuando precede a palabras que comienzan por ‘i’, la conjunción ‘y’ se transforma en ‘e’.', 'replacements': ['e'], 'offsetInContext': 43, 'context': '...ctar errores tipográficos, ortograficos y incluso gramaticales. También algunos e...', 'offset': 176, 'errorLength': 1, 'category': 'GRAMMAR', 'ruleIssueType': 'grammar', 'sentence': 'Se a hecho un esfuerzo para detectar errores tipográficos, ortograficos y incluso gramaticales.'}), Match({'ruleId': 'GROSSO_MODO', 'message': 'Esta expresión latina se usa sin preposición.', 'replacements': ['grosso modo'], 'offsetInContext': 43, 'context': '...les. También algunos errores de estilo, a grosso modo.', 'offset': 235, 'errorLength': 13, 'category': 'GRAMMAR', 'ruleIssueType': 'grammar', 'sentence': 'También algunos errores de estilo, a grosso modo.'})]"""

def test_correct_en_us():
	import language_tool_python
	tool = language_tool_python.LanguageTool('en-US')

	matches = tool.check('cz of this brand is awsome,,i love this brand very much')
	assert len(matches) == 4

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

def test_session_only_new_spellings():
	import os
	import hashlib
	import language_tool_python
	library_path = language_tool_python.utils.get_language_tool_directory()
	spelling_file_path = os.path.join(library_path, "org/languagetool/resource/en/hunspell/spelling.txt")
	with open(spelling_file_path, 'r') as spelling_file:
		initial_spelling_file_contents = spelling_file.read()
	initial_checksum = hashlib.sha256(initial_spelling_file_contents.encode())

	new_spellings = ["word1", "word2", "word3"]
	with language_tool_python.LanguageTool('en-US', newSpellings=new_spellings, new_spellings_persist=False) as tool:
		tool.enabled_rules_only = True
		tool.enabled_rules = {'MORFOLOGIK_RULE_EN_US'}
		matches = tool.check(" ".join(new_spellings))

	with open(spelling_file_path, 'r') as spelling_file:
		subsequent_spelling_file_contents = spelling_file.read()
	subsequent_checksum = hashlib.sha256(subsequent_spelling_file_contents.encode())

	if initial_checksum != subsequent_checksum:
		with open(spelling_file_path, 'w') as spelling_file:
			spelling_file.write(initial_spelling_file_contents)

	assert not matches
	assert initial_checksum.hexdigest() == subsequent_checksum.hexdigest()

def test_debug_mode():
    from language_tool_python.server import DEBUG_MODE
    assert DEBUG_MODE is False
