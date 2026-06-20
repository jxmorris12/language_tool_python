Installation and quick start
============================

Installation
------------

.. code-block:: bash

   pip install --upgrade language_tool_python

**Requirements**

- Python ``>=3.10`` (tested up to 3.15).
- Java ``>=9`` for LanguageTool ``4.0`` to ``6.5``, ``>=17`` for LanguageTool ``>=6.6`` (default).

.. note::

   LanguageTool is downloaded automatically on first use. The default downloaded version is :data:`~language_tool_python.download_lt.LTP_DOWNLOAD_VERSION`. To use a different version, see :ref:`pinning-lt-version`.

Quick start
-----------

.. code-block:: python

   import language_tool_python

   with language_tool_python.LanguageTool("en-US") as tool:
       text = "A sentence with a error in the Hitchhiker's Guide tot he Galaxy"
       matches = tool.check(text)

   print(matches[0].message)
   # → Use “an” instead of ‘a’ if the following word starts with a vowel sound, e.g. ‘an article’, ‘an hour’.
   print(matches[0].replacements)
   # → ['an']

   with language_tool_python.LanguageTool("en-US") as tool:
       corrected = tool.correct(text)

   print(corrected)
   # → A sentence with an error in the Hitchhiker's Guide to the Galaxy
