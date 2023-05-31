# `language_tool_python`: a grammar checker for Python 📝

![language tool python on pypi](https://badge.fury.io/py/language-tool-python.svg)

![Test with PyTest](https://github.com/jxmorris12/language_tool_python/workflows/Test%20with%20PyTest/badge.svg)

Current LanguageTool version: **5.5**

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
'Department of medicine Colombia University closed on August 1 Melinda Sam'
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
...
>>> tool.close() # Call `close()` to shut off the server when you're done.
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

## Closing LanguageTool

`language_tool_python` runs a LanguageTool Java server in the background. It will shut the server off when garbage collected, for example when a created `language_tool_python.LanguageTool` object goes out of scope. However, if garbage collection takes awhile, the process might not get deleted right away. If you're seeing lots of processes get spawned and not get deleted, you can explicitly close them:


```python
import language_tool_python
tool = language_tool_python.LanguageToolPublicAPI('de-DE') # starts a process
# do stuff with `tool`
tool.close() # explicitly shut off the LanguageTool
```

You can also use a context manager (`with .. as`) to explicitly control when the server is started and stopped:

```python
import language_tool_python

with language_tool_python.LanguageToolPublicAPI('de-DE') as tool:
  # do stuff with `tool`
# no need to call `close() as it will happen at the end of the with statement
```

## Client-Server Model

You can run LanguageTool on one host and connect to it from another.  This is useful in some distributed scenarios. Here's a simple example:

#### server

```python
>>> import language_tool_python
>>> tool = language_tool_python.LanguageTool('en-US', host='0.0.0.0')
>>> tool._url
'http://0.0.0.0:8081/v2/'
```

#### client
```python
>>> import language_tool_python
>>> lang_tool = language_tool_python.LanguageTool('en-US', remote_server='http://0.0.0.0:8081')
>>>
>>>
>>> lang_tool.check('helo darknes my old frend')
[Match({'ruleId': 'UPPERCASE_SENTENCE_START', 'message': 'This sentence does not start with an uppercase letter.', 'replacements': ['Helo'], 'offsetInContext': 0, 'context': 'helo darknes my old frend', 'offset': 0, 'errorLength': 4, 'category': 'CASING', 'ruleIssueType': 'typographical', 'sentence': 'helo darknes my old frend'}), Match({'ruleId': 'MORFOLOGIK_RULE_EN_US', 'message': 'Possible spelling mistake found.', 'replacements': ['darkness', 'darkens', 'darkies'], 'offsetInContext': 5, 'context': 'helo darknes my old frend', 'offset': 5, 'errorLength': 7, 'category': 'TYPOS', 'ruleIssueType': 'misspelling', 'sentence': 'helo darknes my old frend'}), Match({'ruleId': 'MORFOLOGIK_RULE_EN_US', 'message': 'Possible spelling mistake found.', 'replacements': ['friend', 'trend', 'Fred', 'freed', 'Freud', 'Friend', 'fend', 'fiend', 'frond', 'rend', 'fr end'], 'offsetInContext': 20, 'context': 'helo darknes my old frend', 'offset': 20, 'errorLength': 5, 'category': 'TYPOS', 'ruleIssueType': 'misspelling', 'sentence': 'helo darknes my old frend'})]
>>>
```

## Configuration

LanguageTool offers lots of built-in configuration options. 

### Example: Enabling caching
Here's an example of using the configuration options to enable caching. Some users have reported that this helps performance a lot.
```python
import language_tool_python
tool = language_tool_python.LanguageTool('en-US', config={ 'cacheSize': 1000, 'pipelineCaching': True })
```


### Example: Setting maximum text length

Here's an example showing how to configure LanguageTool to set a maximum length on grammar-checked text. Will throw an error (which propagates to Python as a `language_tool_python.LanguageToolError`) if text is too long.
```python
import language_tool_python
tool = language_tool_python.LanguageTool('en-US', config={ 'maxTextLength': 100 })
```

### Full list of configuration options

Here's a full list of configuration options. See the LanguageTool [HTTPServerConfig](https://languagetool.org/development/api/org/languagetool/server/HTTPServerConfig.html) documentation for details.

```
'maxTextLength' - maximum text length, longer texts will cause an error (optional)
'maxTextHardLength' - maximum text length, applies even to users with a special secret 'token' parameter (optional)
'secretTokenKey' - secret JWT token key, if set by user and valid, maxTextLength can be increased by the user (optional)
'maxCheckTimeMillis' - maximum time in milliseconds allowed per check (optional)
'maxErrorsPerWordRate' - checking will stop with error if there are more rules matches per word (optional)
'maxSpellingSuggestions' - only this many spelling errors will have suggestions for performance reasons (optional,
                          affects Hunspell-based languages only)
'maxCheckThreads' - maximum number of threads working in parallel (optional)
'cacheSize' - size of internal cache in number of sentences (optional, default: 0)
'cacheTTLSeconds' - how many seconds sentences are kept in cache (optional, default: 300 if 'cacheSize' is set)
'requestLimit' - maximum number of requests per requestLimitPeriodInSeconds (optional)
'requestLimitInBytes' - maximum aggregated size of requests per requestLimitPeriodInSeconds (optional)
'timeoutRequestLimit' - maximum number of timeout request (optional)
'requestLimitPeriodInSeconds' - time period to which requestLimit and timeoutRequestLimit applies (optional)
'languageModel' - a directory with '1grams', '2grams', '3grams' sub directories which contain a Lucene index
                  each with ngram occurrence counts; activates the confusion rule if supported (optional)
'word2vecModel' - a directory with word2vec data (optional), see
https://github.com/languagetool-org/languagetool/blob/master/languagetool-standalone/CHANGES.md#word2vec
'fasttextModel' - a model file for better language detection (optional), see
                  https://fasttext.cc/docs/en/language-identification.html
'fasttextBinary' - compiled fasttext executable for language detection (optional), see
                  https://fasttext.cc/docs/en/support.html
'maxWorkQueueSize' - reject request if request queue gets larger than this (optional)
'rulesFile' - a file containing rules configuration, such as .langugagetool.cfg (optional)
'warmUp' - set to 'true' to warm up server at start, i.e. run a short check with all languages (optional)
'blockedReferrers' - a comma-separated list of HTTP referrers (and 'Origin' headers) that are blocked and will not be served (optional)
'premiumOnly' - activate only the premium rules (optional)
'disabledRuleIds' - a comma-separated list of rule ids that are turned off for this server (optional)
'pipelineCaching' - set to 'true' to enable caching of internal pipelines to improve performance
'maxPipelinePoolSize' - cache size if 'pipelineCaching' is set
'pipelineExpireTimeInSeconds' - time after which pipeline cache items expire
'pipelinePrewarming' - set to 'true' to fill pipeline cache on start (can slow down start a lot)
```

## Installation

To install via pip:

```bash
$ pip install --upgrade language_tool_python
```

### What rules does LanguageTool have?

Searching for a specific rule to enable or disable? Curious the breadth of rules LanguageTool applies? This page contains a massive list of all 5,000+ grammatical rules that are programmed into LanguageTool: https://community.languagetool.org/rule/list?lang=en&offset=30&max=10

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

- [Python 3.6+](https://www.python.org)
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
