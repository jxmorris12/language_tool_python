Examples
========

This page provides practical examples for using ``language_tool_python``.
For advanced patterns (resource management, client/server, error handling, pinning the
LT version) see :doc:`advanced`. For CLI usage see :doc:`cli`. For environment variables
see :doc:`env_vars`. For local server configuration see :doc:`config`.

Basic usage
-----------

Checking text for errors
~~~~~~~~~~~~~~~~~~~~~~~~~

Use :class:`~language_tool_python.server.LanguageTool` to check a piece of text. The
:meth:`~language_tool_python.server.LanguageTool.check` method returns a list of
:class:`~language_tool_python.match.Match` objects, each describing a detected issue.

.. code-block:: python

   import language_tool_python

   with language_tool_python.LanguageTool("en-US") as tool:
       matches = tool.check("A sentence with a error in the Hitchhiker's Guide tot he Galaxy")

   print(len(matches))
   # → 2
   print(matches[0].message)
   # → 'Use "an" instead of "a" if the following word starts with a vowel sound'
   print(matches[0].replacements)
   # → ['an']
   print(matches[0].offset)
   # → 16

Correcting text automatically
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

:meth:`~language_tool_python.server.LanguageTool.correct` applies the first suggestion
for each detected issue and returns the fixed text.

.. code-block:: python

   import language_tool_python

   with language_tool_python.LanguageTool("en-US") as tool:
       corrected = tool.correct("A sentence with a error in the Hitchhiker's Guide tot he Galaxy")

   print(corrected)
   # → A sentence with an error in the Hitchhiker's Guide to the Galaxy

You can also call :func:`~language_tool_python.utils.correct` directly with a custom
list of :class:`~language_tool_python.match.Match` objects if you need to filter them first.

.. code-block:: python

   import language_tool_python
   from language_tool_python.utils import correct

   with language_tool_python.LanguageTool("en-US") as tool:
       text = "This are wrong."
       matches = tool.check(text)

   print([match.rule_id for match in matches])
   # → ['THIS_NNS', 'THAT_SOUND_GREAT']
   print(correct(text, matches))
   # → These is wrong.

   matches = [m for m in matches if m.rule_id != "THIS_NNS"]
   print(correct(text, matches))
   # → This is wrong.
   # Ignore the first match

Applying a specific suggestion
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

:meth:`~language_tool_python.server.LanguageTool.correct` always picks the first
suggestion. To choose a different one, call
:meth:`~language_tool_python.match.Match.select_replacement` before passing the match to
:func:`~language_tool_python.utils.correct`:

.. code-block:: python

   import language_tool_python
   from language_tool_python.utils import correct

   text = "There is a bok on the table."
   with language_tool_python.LanguageTool("en-US") as tool:
       matches = tool.check(text)

   print(matches[0].replacements)
   # → ['BOK', 'OK', 'book', 'box', 'boy', 'Bob', 'bow', 'beak', ...]
   matches[0].select_replacement(2)  # pick the third suggestion instead of the first
   patched = correct(text, matches)
   print(patched)
   # → There is a book on the table.

Using the public API (no local server)
---------------------------------------

:class:`~language_tool_python.server.LanguageToolPublicAPI` connects to the hosted
LanguageTool service instead of starting a local Java server. No Java installation is
required, but requests are subject to rate limits.

.. code-block:: python

   import language_tool_python

   with language_tool_python.LanguageToolPublicAPI("en-US") as tool:
       matches = tool.check("This are wrong.")

   print(len(matches))
   # → 2

.. note::

   The public API is subject to rate limits. If you need to check multiple texts or
   large documents, consider using :class:`~language_tool_python.server.LanguageTool`
   with a local server instead, or authenticating with a premium key (see
   :doc:`advanced`).

Checking only specific regions of text
---------------------------------------

:meth:`~language_tool_python.server.LanguageTool.check_matching_regions` restricts
checking to the parts of the text that match a regular expression. This is useful when
the text contains markup, code blocks, or other sections that should be skipped.

.. code-block:: python

   import language_tool_python
   from language_tool_python.utils import correct

   text = 'He seid "I has a problem" but she replied "It are fine".'

   with language_tool_python.LanguageTool("en-US") as tool:
       matches = tool.check_matching_regions(
           text,
           r'"[^"]*"',  # only check text inside double quotes
       )

   print(correct(text, matches))
   # → He seid "I have a problem" but she replied "It is fine".
   # "seid" is not corrected because it is outside the quoted regions.


Controlling rules
-----------------

Disabling specific rules
~~~~~~~~~~~~~~~~~~~~~~~~~

Pass rule IDs to :attr:`~language_tool_python.server.LanguageTool.disabled_rules` to
suppress individual rules, or call
:meth:`~language_tool_python.server.LanguageTool.disable_spellchecking` to turn off
all spell-check categories at once.

.. code-block:: python

   import language_tool_python

   text = "Thiss is false."

   with language_tool_python.LanguageTool("en-US") as tool:
       matches = tool.check(text)
       print(len(matches))
       # → 1

   with language_tool_python.LanguageTool("en-US") as tool:
       tool.disabled_rules = {"MORFOLOGIK_RULE_EN_US"}
       matches = tool.check(text)
       print(len(matches))
       # → 0
       # The rule "MORFOLOGIK_RULE_EN_US" is disabled, so the spelling error is ignored.

   with language_tool_python.LanguageTool("en-US") as tool:
       tool.disable_spellchecking()
       matches = tool.check(text)
       print(len(matches))
       # → 0
       # The spellchecking is disabled, so the spelling error is ignored.

Enabling only specific rules
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Set :attr:`~language_tool_python.server.LanguageTool.enabled_rules_only` to ``True``
to run exclusively the rules listed in
:attr:`~language_tool_python.server.LanguageTool.enabled_rules`.

.. code-block:: python

   import language_tool_python

   text = "This are wrong."

   with language_tool_python.LanguageTool("en-US") as tool:
       matches = tool.check(text)
       print([match.rule_id for match in matches])
       # → ['THIS_NNS', 'THAT_SOUND_GREAT']
       print(tool.correct(text))
       # → These is wrong.

   with language_tool_python.LanguageTool("en-US") as tool:
       tool.enabled_rules = {"THIS_NNS"}
       tool.enabled_rules_only = True
       print(tool.correct(text))
       # → These are wrong.
       # Only the THIS_NNS rule is applied

Controlling categories
~~~~~~~~~~~~~~~~~~~~~~~

Use :attr:`~language_tool_python.server.LanguageTool.disabled_categories` and
:attr:`~language_tool_python.server.LanguageTool.enabled_categories` to enable or
disable entire rule categories at once. `Here is a list of all categories`_.

.. _`Here is a list of all categories`: https://github.com/languagetool-org/languagetool/blob/master/languagetool-core/src/main/java/org/languagetool/rules/Categories.java

.. code-block:: python

   import language_tool_python

   text = "I wentt to new york last week."

   with language_tool_python.LanguageTool("en-US") as tool:
       matches = tool.check(text)
       print([match.category for match in matches])
       # → ['TYPOS', 'CASING']
       print(tool.correct(text))
       # → I went to New York last week.

   with language_tool_python.LanguageTool("en-US") as tool:
       tool.enabled_categories = {"CASING"}
       tool.enabled_rules_only = True
       matches = tool.check(text)
       print([match.category for match in matches])
       # → ['CASING']
       print(tool.correct(text))
       # → I wentt to New York last week.

Picky mode (stricter checking)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Enable :attr:`~language_tool_python.server.LanguageTool.picky` for additional style
rules that are too strict for casual writing.

Preferred language variants
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

:attr:`~language_tool_python.server.LanguageTool.preferred_variants` lets you specify
which dialect to prefer when you use the "auto" language. LanguageTool can detect the
language that is used in the text, but you have to specify variants in case of
a language with multiple dialects (e.g. English) is detected.

.. code-block:: python

   import language_tool_python

   text = "The colour of the sky."

   with language_tool_python.LanguageTool("auto") as tool:
       tool.preferred_variants = {"en-US"}
       print(tool.correct(text))
       # → The color of the sky.

   with language_tool_python.LanguageTool("auto") as tool:
       tool.preferred_variants = {"en-GB"}
       print(tool.correct(text))
       # → The colour of the sky.

Mother tongue detection
------------------------

Setting :attr:`~language_tool_python.server.LanguageTool.mother_tongue` helps
LanguageTool detect *false friends* (words that look similar across two languages but
carry different meanings). It works only with ngrams data installed (see :doc:`config`).

.. code-block:: python

   import language_tool_python

   config = {
       "languageModel": "/path/to/ngrams"
   }

   with language_tool_python.LanguageTool("en-US", config=config) as tool:
       matches = tool.check("My handy is broken.")
       print(matches)
       # → []

   with language_tool_python.LanguageTool("en-US", mother_tongue="de", config=config) as tool:
       matches = tool.check("My handy is broken.")
       print(matches[0].message)
       # → “handy” (English) means “praktisch”, “handlich” (German). Did you maybe mean “cell phone”, “mobile phone”?

Classifying matches
--------------------

:func:`~language_tool_python.utils.classify_matches` categorises a list of matches as:

- :attr:`~language_tool_python.utils.TextStatus.CORRECT` - no matches found.
- :attr:`~language_tool_python.utils.TextStatus.FAULTY` - at least one match has replacement suggestions.
- :attr:`~language_tool_python.utils.TextStatus.GARBAGE` - matches exist but none have suggestions (unrecognisable input).

.. code-block:: python

   import language_tool_python
   from language_tool_python.utils import classify_matches

   with language_tool_python.LanguageTool("en-US") as tool:
       matches = tool.check("This sentence is correct.")
       print(classify_matches(matches))
       # → TextStatus.CORRECT
       matches = tool.check("This are wrong.")
       print(classify_matches(matches))
       # → TextStatus.FAULTY
       matches = tool.check("fnekknfzn")
       print(classify_matches(matches))
       # → TextStatus.GARBAGE

Custom spellings
----------------

Pass a list of words via ``new_spellings`` to add them to the local LanguageTool
dictionary. By default they persist across sessions (``new_spellings_persist=True``).

.. code-block:: python

   import language_tool_python

   with language_tool_python.LanguageTool(
       "en-US",
   ) as tool:
       matches = tool.check("Welcome to the compani.")
       print(len(matches))
       # → 1
       # "compani" is not a known word, so LanguageTool suggests "company" as a correction

   with language_tool_python.LanguageTool(
       "en-US",
       new_spellings=["compani"],
       new_spellings_persist=False,
   ) as tool:
       matches = tool.check("Welcome to the compani.")
       print(len(matches))
       # → 0
       # "compani" is now a known word, so LanguageTool does not suggest any corrections

Pass ``new_spellings_persist=False`` to keep the words for the current session only,
they are removed when :meth:`~language_tool_python.server.LanguageTool.close` is called.

Using a remote LanguageTool server
------------------------------------

Point :class:`~language_tool_python.server.LanguageTool` at a self-hosted LanguageTool
server with the ``remote_server`` parameter.

.. code-block:: python

   import language_tool_python

   with language_tool_python.LanguageTool(
       "en-US",
       remote_server="http://my-languagetool-server:8081",
   ) as tool:
       print(tool.correct("I has a problem."))
       # → I have a problem.

You can also route requests through an HTTP proxy:

.. code-block:: python

   import language_tool_python

   with language_tool_python.LanguageTool(
       "en-US",
       remote_server="http://my-languagetool-server:8081",
       proxies={"http": "http://proxy:3128", "https": "http://proxy:3128"},
   ) as tool:
       print(tool.correct("I has a problem."))
       # → I have a problem

.. note::

   ``proxies`` can only be used together with ``remote_server``. Passing ``proxies``
   without ``remote_server`` raises ``ValueError``.

Inspecting a Match object
--------------------------

Each :class:`~language_tool_python.match.Match` object exposes the following attributes:

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Attribute
     - Description
   * - ``rule_id``
     - Identifier of the triggered rule (e.g. ``"MORFOLOGIK_RULE_EN_US"``).
   * - ``message``
     - Human-readable description of the issue.
   * - ``replacements``
     - Ordered list of suggested corrections (may be empty).
   * - ``offset``
     - Start character position in the original text.
   * - ``error_length``
     - Number of characters covered by the error.
   * - ``context``
     - Short excerpt of text surrounding the error.
   * - ``offset_in_context``
     - Position of the error within ``context``.
   * - ``category``
     - Rule category (e.g. ``"TYPOS"``, ``"GRAMMAR"``).
   * - ``rule_issue_type``
     - Issue type string (e.g. ``"misspelling"``, ``"grammar"``).
   * - ``sentence``
     - Full sentence containing the error.

.. code-block:: python

   import language_tool_python

   with language_tool_python.LanguageTool("en-US") as tool:
       matches = tool.check("This are wrong.")

   m = matches[0]
   print(m.rule_id)
   # → THIS_NNS
   print(m.message)
   # → The singular demonstrative pronoun ‘this’ does not agree with the plural verb ‘are’. Did you mean “these”?
   print(m.replacements)
   # → ['These']
   print(m.offset)
   # → 0
   print(m.error_length)
   # → 4
   print(m.context)
   # → 'This are wrong.'
   print(m.offset_in_context)
   # → 0
   print(m.category)
   # → GRAMMAR
   print(m.rule_issue_type)
   # → grammar
   print(m.sentence)
   # → 'This are wrong.'
