language-check
==============

Python wrapper for LanguageTool.

.. image:: https://travis-ci.org/myint/language-check.svg?branch=master
    :target: https://travis-ci.org/myint/language-check
    :alt: Build status

This is a fork of
https://bitbucket.org/spirit/language_tool that produces more easily parsable
results from the command-line.

Example usage
-------------

From the interpreter:

>>> import language_check
>>> tool = language_check.LanguageTool('en-US')
>>> text = u'A sentence with a error in the Hitchhiker’s Guide tot he Galaxy'
>>> matches = tool.check(text)
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
...

Automatically apply suggestions to the text:

>>> language_check.correct(text, matches)
'A sentence with an error in the Hitchhiker’s Guide to the Galaxy'

From the command line::

    $ echo 'This are bad.' > example.txt

    $ language-check example.txt
    example.txt:1:1: THIS_NNS[3]: Did you mean 'these'?


Installation
------------

To install via pip::

    $ pip install --upgrade language-check

If you are using Python 2, you'll need to install 3to2 beforehand::

    $ pip install --upgrade 3to2

To overwrite the host part of URL that is used to download LanguageTool-{version}.zip::

    - SET LANGUAGE_CHECK_DOWNLOAD_HOST = [alternate URL]


Prerequisites
-------------

- `Python 3.3+ <https://www.python.org>`_ (or 2.7)
- `lib3to2 <https://bitbucket.org/amentajo/lib3to2>`_
  (if installing for Python 2)
- `LanguageTool <https://www.languagetool.org>`_ (Java 6.0+)


The installation process should take care of downloading LanguageTool (it may
take a few minutes). Otherwise, you can manually download
`LanguageTool-stable.zip
<https://www.languagetool.org/download/LanguageTool-stable.zip>`_ and unzip it
into where the ``language_check`` package resides.

Vim plugin
----------

To use language-check in Vim, install Syntastic_ and use the following
settings:

.. code-block:: vim

    let g:syntastic_text_checkers = ['language_check']
    let g:syntastic_text_language_check_args = '--language=en-US'

Customize your language as appropriate.

.. _Syntastic: https://github.com/scrooloose/syntastic
