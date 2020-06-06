import language_tool_python

s = 'Wat is wrong with the spll chker'

tool = language_tool_python.LanguageTool('en-GB')

print('Correcting "{}" ...'.format(s))
print(tool.correct(s))

tool.disable_spellchecking()

print('Correcting "{}" without spellchecking...'.format(s))
print(tool.correct(s))