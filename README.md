# `language_tool_python`: a grammar checker for Python 📝

![language tool python on pypi](https://badge.fury.io/py/language-tool-python.svg)

![Test with PyTest](https://github.com/jxmorris12/language_tool_python/workflows/Test%20with%20PyTest/badge.svg)

Current LanguageTool version: **5.1**

This is a Python wrapper for [LanguageTool](https://languagetool.org). LanguageTool is open-source grammar tool, also known as the spellchecker for OpenOffice. This library allows you to make to detect grammar errors and spelling mistakes through a Python script or through a command-line interface.

## Local and Remote Servers

By default, `language_tool_python` will download a LanguageTool server `.jar` and run that in the background to detect grammar errors locally. However, LanguageTool also offers a [Public HTTP Proofreading API](https://dev.languagetool.org/public-http-api) that is supported as well. Follow the link for rate limiting details. (Running locally won't have the same restrictions.)

### Using `language_tool_python` locally

Local server is the default setting. To use this, just initialize a LanguageTool object:

```python
import language_tool_python
tool = language_tool_python.LanguageTool('en-US')  # use a local server (automatically set up), language English
```

### Using `language_tool_python` with the public LanguageTool remote server

There is also a built-in class for querying LanguageTool's public servers. Initialize it like this:

```python
import language_tool_python
tool = language_tool_python.LanguageToolPublicAPI('es') # use the public API, language Spanish
```

### Using `language_tool_python` with the another remote server

Finally, you're able to pass in your own remote server as an argument to the `LanguageTool` class:

```python
import language_tool_python
tool = language_tool_python.LanguageTool('ca-ES', remote_server='https://language-tool-api.mywebsite.net')  # use a remote server API, language Catalan
```

### Apply a custom list of matches with `utils.correct`

If you want to decide which `Match` objects to apply to your text, use `tool.check` (to generate the list of matches) in conjunction with `language_tool_python.utils.correct` (to apply the list of matches to text). Here is an example of generating, filtering, and applying a list of matches. In this case, spell-checking suggestions for uppercase words are ignored:

```python
>>> s = "Department of medicine Colombia University closed on August 1 Milinda Samuelli"
>>> is_bad_rule = lambda rule: rule.message == 'Possible spelling mistake found.' and len(rule.replacements) and rule.replacements[0][0].isupper()
>>> import language_tool_python
>>> tool = language_tool_python.LanguageTool('en-US')
>>> matches = tool.check(s)
>>> matches = [rule for rule in matches if not is_bad_rule(rule)]
>>> language_tool_python.utils.correct(s, matches)
'Department of medicine Colombia University closed on August 1 Melinda Sam
```

## Example usage

From the interpreter:

```python
>>> import language_tool_python
>>> tool = language_tool_python.LanguageTool('en-US')
>>> text = 'A sentence with a error in the Hitchhiker’s Guide tot he Galaxy'
>>> matches = tool.check(text)
>>> len(matches)
2
```

Check out some ``Match`` object attributes:

```python
>>> matches[0].ruleId, matches[0].replacements # ('EN_A_VS_AN', ['an'])
('EN_A_VS_AN', ['an'])
>>> matches[1].ruleId, matches[1].replacements
('TOT_HE', ['to the'])
```

Print a ``Match`` object:

```python
>>> print(matches[1])
Line 1, column 51, Rule ID: TOT_HE[1]
Message: Did you mean 'to the'?
Suggestion: to the
...
```

Automatically apply suggestions to the text:

```python
>>> tool.correct(text)
'A sentence with an error in the Hitchhiker’s Guide to the Galaxy'
```

From the command line:

```bash
$ echo 'This are bad.' > example.txt
$ language_tool_python example.txt
example.txt:1:1: THIS_NNS[3]: Did you mean 'these'?
```

## Installation

To install via pip:

```bash
$ pip install --upgrade language_tool_python
```

### Customizing Download URL or Path

To overwrite the host part of URL that is used to download LanguageTool-{version}.zip:

```bash
$ export LTP_DOWNLOAD_HOST = [alternate URL]
```

This can be used to downgrade to an older version, for example, or to download from a mirror. 

And to choose the specific folder to download the server to:

```bash
$ export LTP_PATH = /path/to/save/language/tool
```

The default download path is `~/.cache/language_tool_python/`. The LanguageTool server is about 200 MB, so take that into account when choosing your download folder. (Or, if you you can't spare the disk space, use a remote URL!)

## Prerequisites

- [Python 3.5+](https://www.python.org)
- [LanguageTool](https://www.languagetool.org) (Java 8.0 or higher)


The installation process should take care of downloading LanguageTool (it may
take a few minutes). Otherwise, you can manually download
[LanguageTool-stable.zip](https://www.languagetool.org/download/LanguageTool-stable.zip) and unzip it
into where the ``language_tool_python`` package resides.

### LanguageTool Version

As of April 2020, `language_tool_python` was forked from `language-check` and no longer supports LanguageTool versions lower than 4.0.

### Acknowledgements 
This is a fork of https://github.com/myint/language-check/ that produces more easily parsable
results from the command-line.
