Advanced usage
==============

This page covers advanced usage patterns that go beyond the basic check/correct
workflow.

.. _pinning-lt-version:

Pinning the LanguageTool version
---------------------------------

By default, ``language_tool_python`` downloads LanguageTool
:data:`~language_tool_python.download_lt.LTP_DOWNLOAD_VERSION`. Use the
``language_tool_download_version`` parameter to force a specific version, useful for
reproducible results or testing against a particular release:

.. code-block:: python

   import language_tool_python

   with language_tool_python.LanguageTool(
       "en-US",
       language_tool_download_version="6.7",
   ) as tool:
       matches = tool.check("A sentence with a error in the Hitchhiker's Guide tot he Galaxy")

   print(matches[0].message)
   # → Use “an” instead of ‘a’ if the following word starts with a vowel sound, e.g. ‘an article’, ‘an hour’.

Accepted formats:

- ``"X.Y"`` - a release version (e.g. ``"6.7"``, ``"4.0"``). Versions below ``4.0``
  are not supported.
- ``"YYYYMMDD"`` - a snapshot identified by date (e.g. ``"20260201"``).
- ``"latest"`` - the most recent snapshot.

Authenticating with a premium API key
--------------------------------------

If you have a LanguageTool premium key, assign it to
:attr:`~language_tool_python.server.LanguageTool.premium_key` before calling
:meth:`~language_tool_python.server.LanguageTool.check`. The key is forwarded to the
public API as the ``apiKey`` parameter:

.. code-block:: python

   import os
   import language_tool_python

   with language_tool_python.LanguageToolPublicAPI("en-US") as tool:
       tool.premium_key = os.environ["LANGUAGETOOL_API_KEY"]
       print(tool.correct("A sentence with a error in the Hitchhiker's Guide tot he Galaxy"))
       # → A sentence with an error in the Hitchhiker's Guide to the Galaxy

Client/server pattern
----------------------

You can start the LanguageTool Java process once and connect to it from multiple client
instances, avoiding the per-check startup overhead:

.. code-block:: python

   import language_tool_python

   # Start the server once, this launches the Java process
   server_tool = language_tool_python.LanguageTool("en-US")

   # Connect as a lightweight client using the server's port
   client_tool = language_tool_python.LanguageTool(
       "en-US",
       remote_server=f"http://127.0.0.1:{server_tool.port}",
   )

   print(client_tool.correct("A sentence with a error in the Hitchhiker's Guide tot he Galaxy"))
   # → A sentence with an error in the Hitchhiker's Guide to the Galaxy
   server_tool.close()

This pattern is also useful to share a single server across multiple threads or
processes.

Resource management
--------------------

When using a local server, the LanguageTool Java process must be terminated explicitly.
The recommended approach is a context manager, which calls
:meth:`~language_tool_python.server.LanguageTool.close` automatically on exit:

.. code-block:: python

   import language_tool_python

   with language_tool_python.LanguageTool("en-US") as tool:
       print(tool.correct("A sentence with a error in the Hitchhiker's Guide tot he Galaxy"))
       # → A sentence with an error in the Hitchhiker's Guide to the Galaxy
   # Java process is terminated here

For longer-lived instances, call
:meth:`~language_tool_python.server.LanguageTool.close` explicitly:

.. code-block:: python

   import language_tool_python

   tool = language_tool_python.LanguageTool("en-US")
   try:
       print(tool.correct("A sentence with a error in the Hitchhiker's Guide tot he Galaxy"))
       # → A sentence with an error in the Hitchhiker's Guide to the Galaxy
   finally:
       tool.close()

.. warning::

   Forgetting to call ``close()`` (or not using a context manager) leaves the Java
   process running until the Python interpreter exits.

Error handling
--------------

All library exceptions inherit from
:class:`~language_tool_python.exceptions.LanguageToolError`, so a single ``except``
clause is enough to catch any library error:

.. code-block:: python

   import language_tool_python
   from language_tool_python.exceptions import LanguageToolError

   try:
       with language_tool_python.LanguageTool("en-US") as tool:
           print(tool.correct("A sentence with a error in the Hitchhiker's Guide tot he Galaxy"))
           # → A sentence with an error in the Hitchhiker's Guide to the Galaxy
   except LanguageToolError as exc:
       print(f"LanguageTool error: {exc}")

More specific exception classes (all in :mod:`language_tool_python.exceptions`):

- :class:`~language_tool_python.exceptions.ServerError` - the Java server failed to
  start or crashed.
- :class:`~language_tool_python.exceptions.JavaError` - Java is not installed or the
  version is incompatible.
- :class:`~language_tool_python.exceptions.PathError` - a path-like config value does
  not point to an existing file.
- :class:`~language_tool_python.exceptions.RateLimitError` - the public API rate limit
  was exceeded.
