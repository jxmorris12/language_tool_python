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


Installation
------------

You can use `pip <http://www.pip-installer.org>`_ to install or uninstall::

  $ pip install language_tool

On Windows, you can use one of the MSI binary packages provided
on the `download page
<https://bitbucket.org/spirit/language_tool/downloads>`_.


Requirements
------------

- `Python 3.2+ <http://www.python.org>`_
  (or 2.7, using `lib3to2 <https://bitbucket.org/amentajo/lib3to2>`_)
- `LanguageTool <http://www.languagetool.org>`_

The installation process should take care of downloading LanguageTool
(it may take a few minutes).
Otherwise, you can manually download `LanguageTool-stable.zip
<http://www.languagetool.org/download/LanguageTool-stable.zip>`_
and unzip it into a subdirectory inside the language_tool package.

LanguageTool requires Java 6 or later.
