language_tool – LanguageTool through server mode
================================================


Example usage
-------------

>>> import language_tool
>>> lang_tool = language_tool.LanguageTool("en-US")
>>> text = "A sentence with a error in the Hitchhiker’s Guide tot he Galaxy"
>>> matches = lang_tool.check(text)
>>> len(matches)
2


Check out some ``Match`` object attributes:

>>> matches[0].fromy, matches[0].fromx
(0, 16)
>>> matches[0].ruleId, matches[0].replacements
('EN_A_VS_AN', ['an'])
>>> matches[1].fromy, matches[1].fromx
(0, 50)
>>> matches[1].ruleId, matches[1].replacements
('TOT_HE', ['to the'])


Print a ``Match`` object:

>>> print(matches[1])
Line 1, column 51, Rule ID: TOT_HE[1]
Message: Did you mean 'to the'?
Suggestion: to the
... with a error in the Hitchhiker’s Guide tot he Galaxy
                                           ^^^^^^


Automatically apply suggestions to the text:

>>> language_tool.correct(text, matches)
'A sentence with an error in the Hitchhiker’s Guide to the Galaxy'


Installation
------------

To install the package for Python 3, use::

  $ ./setup.py install

To install the package for Python 2, use::

  $ python2 setup.py install

On Windows, you may use one of the MSI binary packages provided on the
`download page <https://bitbucket.org/spirit/language_tool/downloads>`_.


Prerequisites
-------------

- `Python 3.2+ <http://www.python.org>`_ (or 2.7)
- `LanguageTool <http://www.languagetool.org>`_
- `lib3to2 <https://bitbucket.org/amentajo/lib3to2>`_
  (if installing for Python 2)


The installation process should take care of downloading LanguageTool
(it may take a few minutes).
Otherwise, you can manually download `LanguageTool-stable.zip
<http://www.languagetool.org/download/LanguageTool-stable.zip>`_
and unzip it into where the ``language_tool`` package resides.

LanguageTool requires Java 6 or later.
