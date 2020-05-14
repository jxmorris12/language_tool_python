import language_tool_python
tool = language_tool_python.LanguageTool('en-US')
text = u'A sentence with a error in the Hitchhiker’s Guide tot he Galaxy'
matches = tool.check(text)
print('Num. matches:', len(matches))
print('First match:', matches[0])