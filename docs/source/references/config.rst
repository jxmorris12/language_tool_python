Local server configuration
==========================

When using a local LanguageTool server you can tune its behaviour by passing a ``config``
dictionary to :class:`~language_tool_python.server.LanguageTool`. Internally, the
dictionary is validated and written to a temporary ``*.cfg`` file that is passed to the
Java process via ``--config``.

.. note::

   ``config`` is only available for local servers. Combining ``config`` with
   ``remote_server`` raises ``ValueError``.

Quick example
-------------

.. code-block:: python

   import language_tool_python

   with language_tool_python.LanguageTool(
       "en-US",
       config={
           "cacheSize": 1000,
           "cacheTTLSeconds": 300,
           "maxTextLength": 100_000,
           "pipelineCaching": True,
       },
   ) as tool:
       print(tool.correct("A sentence with a error in the Hitchhiker's Guide tot he Galaxy"))
       # → A sentence with an error in the Hitchhiker's Guide to the Galaxy

Accepted keys
-------------

Limits
~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 35 15 50

   * - Key
     - Type
     - Description
   * - ``maxTextLength``
     - ``int``
     - Maximum number of characters accepted per request. Requests exceeding this limit
       are rejected.
   * - ``maxTextHardLength``
     - ``int``
     - Hard character limit that applies even to privileged users with a special token.
       Requests exceeding this limit are rejected.
   * - ``maxCheckTimeMillis``
     - ``int``
     - Maximum time in milliseconds allowed for a single check request.
   * - ``maxErrorsPerWordRate``
     - ``int | float``
     - If the ratio of errors to words exceeds this value, the check is aborted.
   * - ``maxSpellingSuggestions``
     - ``int``
     - Maximum number of spelling suggestions returned per error. Applies to
       Hunspell-based languages only.
   * - ``maxCheckThreads``
     - ``int``
     - Maximum number of threads used concurrently for checking.
   * - ``maxWorkQueueSize``
     - ``int``
     - Maximum number of requests that can queue up before new requests are rejected.

Rate limiting
~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 35 15 50

   * - Key
     - Type
     - Description
   * - ``requestLimit``
     - ``int``
     - Maximum number of requests allowed within ``requestLimitPeriodInSeconds``.
   * - ``requestLimitInBytes``
     - ``int``
     - Maximum total request body size in bytes within the rate-limit window.
   * - ``timeoutRequestLimit``
     - ``int``
     - Maximum number of timed-out requests before the server starts rejecting new ones.
   * - ``requestLimitPeriodInSeconds``
     - ``int``
     - Duration of the rate-limiting window in seconds.

Pipeline caching
~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 35 15 50

   * - Key
     - Type
     - Description
   * - ``cacheSize``
     - ``int``
     - Number of sentences to keep in the internal cache (default: 0, disabled).
   * - ``cacheTTLSeconds``
     - ``int``
     - How many seconds sentences are kept in the cache (default: 300 if ``cacheSize``
       is set).
   * - ``pipelineCaching``
     - ``bool | int``
     - Enable internal pipeline caching for faster repeated checks.
   * - ``maxPipelinePoolSize``
     - ``int``
     - Maximum number of cached pipelines.
   * - ``pipelineExpireTimeInSeconds``
     - ``int``
     - Expiry time for cached pipelines in seconds.
   * - ``pipelinePrewarming``
     - ``bool | int``
     - Fill the pipeline cache on startup to reduce first-request latency. Can
       significantly slow down server start.

External models
~~~~~~~~~~~~~~~

All path values must point to existing files or directories, the path is validated when
:class:`~language_tool_python.config_file.LanguageToolConfig` is instantiated.

.. list-table::
   :header-rows: 1
   :widths: 35 15 50

   * - Key
     - Type
     - Description
   * - ``languageModel``
     - ``str | Path``
     - Path to a directory containing ``1grams``, ``2grams``, and ``3grams``
       sub-directories (one Lucene index each) per language. Activates the confusion
       rule for supported languages.
   * - ``fasttextModel``
     - ``str | Path``
     - Path to a fastText language-identification model file.
   * - ``fasttextBinary``
     - ``str | Path``
     - Path to the fastText binary executable.
   * - ``rulesFile``
     - ``str | Path``
     - Path to an XML file containing custom rules.

Access control
~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 35 15 50

   * - Key
     - Type
     - Description
   * - ``blockedReferrers``
     - ``str | list | tuple | set``
     - Comma-separated referrer URLs (or a collection) that are blocked from using the
       server.
   * - ``premiumOnly``
     - ``bool | int``
     - Activate only the premium rules, ignoring all free rules.
   * - ``trustXForwardForHeader``
     - ``bool | int``
     - Trust the ``X-Forwarded-For`` header for rate limiting (use only behind a
       trusted reverse proxy).

Miscellaneous
~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 35 15 50

   * - Key
     - Type
     - Description
   * - ``disabledRuleIds``
     - ``str | list | tuple | set``
     - Comma-separated rule IDs (or a collection) that are disabled globally for all
       requests.
   * - ``suggestionsEnabled``
     - ``bool | int``
     - Whether to compute replacement suggestions. Disabling this speeds up checking
       when suggestions are not needed.

Language-specific keys
----------------------

In addition to the keys above, you can configure per-language spell-checking by using
keys of the form ``lang-<code>`` or ``lang-<code>-dictPath``:

.. list-table::
   :header-rows: 1
   :widths: 35 15 50

   * - Key pattern
     - Type
     - Description
   * - ``lang-<code>``
     - ``str``
     - Display name of the language (e.g. ``lang-tr=Turkish``). Registers a
       spellcheck-only language that LT does not natively support.
   * - ``lang-<code>-dictPath``
     - ``str | Path``
     - Absolute path to the Hunspell ``.dic`` file for the given language code
       (e.g. ``lang-tr-dictPath``). The same directory must also contain a
       ``common_words.txt`` file listing the 10,000 most common words (used for
       language detection). The path must point to an existing file.

API reference
-------------

See :class:`~language_tool_python.config_file.LanguageToolConfig` for the full class
documentation.
