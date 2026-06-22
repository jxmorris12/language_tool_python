Command-line interface
======================

``language_tool_python`` can be invoked directly from the command line, without writing
any Python code.

Usage
-----

.. code-block:: text

   language_tool_python [OPTIONS] FILE [FILE ...]

Use ``-`` as the file argument to read from stdin.

Options
-------

.. list-table::
   :header-rows: 1
   :widths: 35 65

   * - Option
     - Description
   * - ``FILE [FILE ...]``
     - One or more plain-text files to check. Use ``-`` to read from stdin.
   * - ``-c, --encoding ENCODING``
     - Input file encoding (default: system locale).
   * - ``-l, --language CODE``
     - BCP 47 language code to use (e.g. ``en-US``, ``de-DE``). Pass ``auto`` for
       automatic language detection.
   * - ``-m, --mother-tongue CODE``
     - First-language code. Enables *false-friend* detection between the target language
       and the mother tongue.
   * - ``-d, --disable RULES``
     - Comma-separated list of rule IDs to disable.
   * - ``-e, --enable RULES``
     - Comma-separated list of rule IDs to enable.
   * - ``-D, --disable-categories CATEGORIES``
     - Comma-separated list of category IDs to disable (e.g. ``TYPOS``, ``GRAMMAR``).
   * - ``-E, --enable-categories CATEGORIES``
     - Comma-separated list of category IDs to enable.
   * - ``--enabled-only``
     - Run only the rules listed with ``--enable`` and the categories listed with
       ``--enable-categories``, ignoring all others.
   * - ``-p, --picky``
     - Enable stricter (picky) checking mode.
   * - ``-a, --apply``
     - Automatically apply the first suggestion for each match and print the corrected
       text.
   * - ``-s, --spell-check-off``
     - Disable all spell-checking rules.
   * - ``--ignore-lines REGEX``
     - Skip lines that match the given regular expression.
   * - ``--remote-host HOST``
     - Hostname of a remote LanguageTool server to connect to instead of starting a
       local one.
   * - ``--remote-port PORT``
     - Port of the remote LanguageTool server.
   * - ``--verbose``
     - Enable debug logging.
   * - ``--version``
     - Print the ``language_tool_python`` version and exit.

Exit codes
----------

.. list-table::
   :header-rows: 1
   :widths: 15 85

   * - Code
     - Meaning
   * - ``0``
     - No issues found.
   * - ``2``
     - At least one issue was found.

Examples
--------

.. code-block:: bash

   # Check a file
   language_tool_python -l en-US README.md

   # Check stdin
   echo "This are bad." | language_tool_python -l en-US -

   # Auto-apply suggestions and print the result
   language_tool_python -l en-US --apply input.txt

   # Disable spell checking
   language_tool_python -l en-US --spell-check-off input.txt

   # Disable specific rules
   language_tool_python -l en-US -d RULE_ID1,RULE_ID2 input.txt

   # Disable an entire category
   language_tool_python -l en-US -D TYPOS input.txt

   # Disable multiple categories
   language_tool_python -l en-US -D TYPOS,GRAMMAR input.txt

   # Run only one specific rule
   language_tool_python -l en-US --enabled-only -e MORFOLOGIK_RULE_EN_US input.txt

   # Use a remote LanguageTool server
   language_tool_python -l en-US --remote-host 127.0.0.1 --remote-port 8081 input.txt

   # Picky mode with mother-tongue detection
   language_tool_python -l de-DE -m en --picky input.txt
