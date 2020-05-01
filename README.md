# `language_tool_python`: a grammar checker for Python 📝

This is a Python wrapper for [LanguageTool](languagetool.org). LanguageTool is open-source grammar tool, also known as the spellchecker for OpenOffice. This library allows you to make to detect grammar errors and spelling mistakes through a Python script or through a command-line interface.

## Example usage

From the interpreter:

    > import language_tool_python
    > tool = language_tool_python.LanguageTool('en-US')
    > text = u'A sentence with a error in the Hitchhiker’s Guide tot he Galaxy'
    > matches = tool.check(text)
    > len(matches)
    2

Check out some ``Match`` object attributes:

    > matches[0].fromy, matches[0].fromx
    (0, 16)
    > matches[0].ruleId, matches[0].replacements
    ('EN_A_VS_AN', ['an'])
    > matches[1].fromy, matches[1].fromx
    (0, 50)
    > matches[1].ruleId, matches[1].replacements
    ('TOT_HE', ['to the'])

Print a ``Match`` object:

    print(matches[1])
    Line 1, column 51, Rule ID: TOT_HE[1]
    Message: Did you mean 'to the'?
    Suggestion: to the
    ...

Automatically apply suggestions to the text:

    language_tool_python.correct(text, matches)
    'A sentence with an error in the Hitchhiker’s Guide to the Galaxy'

From the command line::

    $ echo 'This are bad.' > example.txt

    $ language_tool_python example.txt
    example.txt:1:1: THIS_NNS[3]: Did you mean 'these'?


## Installation

To install via pip::

    $ pip install --upgrade language_tool_python


To overwrite the host part of URL that is used to download LanguageTool-{version}.zip::

    - SET language_tool_python_DOWNLOAD_HOST = [alternate URL]


## Prerequisites

- `Python 3.3+ <https://www.python.org>`_ (or 2.7)
- `lib3to2 <https://bitbucket.org/amentajo/lib3to2>`_
  (if installing for Python 2)
- `LanguageTool <https://www.languagetool.org>`_ (Java 6.0+)


The installation process should take care of downloading LanguageTool (it may
take a few minutes). Otherwise, you can manually download
`LanguageTool-stable.zip
<https://www.languagetool.org/download/LanguageTool-stable.zip>`_ and unzip it
into where the ``language_tool_python`` package resides.

### LanguageTool Version

As of April 2020, `language_tool_python` was forked from `language-check` and no longer supports LanguageTool versions lower than 4.0.

### Acknowledgements 
This is a fork of https://github.com/myint/language-check/ (which is a fork of
https://bitbucket.org/spirit/language_tool) that produces more easily parsable
results from the command-line.
