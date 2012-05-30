language_tool – LanguageTool through server mode (for Python 3)
===============================================================


Example usage
-------------

>>> from language_tool import LanguageTool
>>> lang_tool = LanguageTool("en")
>>> text = "but it’s suppose to be all yellowy."
>>> matches = lang_tool.check(text)
>>> len(matches)
2
>>> matches[0].ruleId, matches[0].replacements
('UPPERCASE_SENTENCE_START', ['But'])
>>> matches[1].ruleId, matches[1].replacements
('SUPPOSE_TO', ['supposed'])


Requirements
------------

- `Python 3.2 <http://www.python.org/>`_
- `LanguageTool <http://www.languagetool.org/>`_

Download the LanguageTool-stable.oxt file, rename it so it ends with “.zip”,
then unzip it into a subdirectory where the language_tool package resides.

LanguageTool requires Java 6 or later.
