import language_tool_python
tool = language_tool_python.LanguageToolPublicAPI('es')
es_text = 'Escriba un texto aquí. LanguageTool le ayudará a afrentar algunas dificultades propias de la escritura. Se a hecho un esfuerzo para detectar errores tipográficos, ortograficos y incluso gramaticales. También algunos errores de estilo, a grosso modo.'

print('Spell-checking in [ES] using LanguageTool Public API:')
matches = tool.check(es_text)
print(matches)