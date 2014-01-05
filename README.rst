language-check
==============

Python wrapper for LanguageTool.

.. image:: https://travis-ci.org/myint/language-check.png?branch=master
    :target: https://travis-ci.org/myint/language-check
    :alt: Build status

This is a fork of
https://bitbucket.org/spirit/language_tool that produces more easily parsable
results from the command-line.

Example usage
-------------

>>> import language_check
>>> lang_check = language_check.LanguageTool("en-US")
>>> text = "A sentence with a error in the Hitchhiker’s Guide tot he Galaxy"
>>> matches = lang_check.check(text)
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

>>> language_check.correct(text, matches)
'A sentence with an error in the Hitchhiker’s Guide to the Galaxy'


Installation
------------

To install the package for Python 3, use::

    $ ./setup.py install


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
and unzip it into where the ``language_check`` package resides.

LanguageTool requires Java 6 or later.
