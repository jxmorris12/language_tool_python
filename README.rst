language_tool – LanguageTool through server mode
================================================


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

- `LanguageTool <http://www.languagetool.org/>`_

The installation process should take care of downloading LanguageTool.
Otherwise, you can manually download `LanguageTool-stable.oxt
<http://www.languagetool.org/download/LanguageTool-stable.oxt>`_,
rename it so it ends with “.zip”, then unzip it into a subdirectory
inside the language_tool package.

LanguageTool requires Java 6 or later.
