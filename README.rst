language_tool – LanguageTool through server mode
================================================


Example usage
-------------

>>> import language_tool
>>> lang_tool = language_tool.LanguageTool("en-US")
>>> text = "but it’s suppose to be all yellowy."
>>> matches = lang_tool.check(text)
>>> len(matches)
2


Check out some ``Match`` object attributes:

>>> matches[0].fromy, matches[0].fromx
(0, 0)
>>> matches[0].ruleId, matches[0].replacements
('UPPERCASE_SENTENCE_START', ['But'])
>>> matches[1].fromy, matches[1].fromx
(0, 9)
>>> matches[1].ruleId, matches[1].replacements
('SUPPOSE_TO', ['supposed'])


Print a ``Match`` object:

>>> print(matches[1])
Line 1, column 10, Rule ID: SUPPOSE_TO[1]
Message: Probably you should use a past participle here: 'supposed'.
Suggestion: supposed
but it’s suppose to be all yellowy.
         ^^^^^^^


Automatically apply suggestions to the text:

>>> language_tool.correct(text, matches)
'But it’s supposed to be all yellowy.'


Installation
------------

You can use the ``setup.py`` script::

  $ ./setup.py install

On Windows, you can use one of the MSI binary packages provided on the
`download page <https://bitbucket.org/spirit/language_tool/downloads>`_.


Requirements
------------

- `Python 3.2+ <http://www.python.org>`_
  (or 2.7, using `lib3to2 <https://bitbucket.org/amentajo/lib3to2>`_)
- `LanguageTool <http://www.languagetool.org>`_

The installation process should take care of downloading LanguageTool
(it may take a few minutes).
Otherwise, you can manually download `LanguageTool-stable.zip
<http://www.languagetool.org/download/LanguageTool-stable.zip>`_
and unzip it into a subdirectory inside the ``language_tool`` package.

LanguageTool requires Java 6 or later.
