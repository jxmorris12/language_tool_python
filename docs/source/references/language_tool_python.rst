language\_tool\_python package (full API reference)
===================================================

Available modules
-----------------

The following modules make up the public interface of ``language_tool_python``.

Core - :mod:`language_tool_python.server`
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Contains :class:`~language_tool_python.server.LanguageTool`, the main class for interacting
with a local LanguageTool server, and
:class:`~language_tool_python.server.LanguageToolPublicAPI`, a subclass that targets the
hosted public API instead.

.. automodule:: language_tool_python.server
   :members:
   :show-inheritance:
   :undoc-members:

Match - :mod:`language_tool_python.match`
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Contains the :class:`~language_tool_python.match.Match` class that wraps a single language
issue returned by LanguageTool.

.. automodule:: language_tool_python.match
   :members:
   :show-inheritance:
   :undoc-members:

Utilities - :mod:`language_tool_python.utils`
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Standalone helper functions:
:func:`~language_tool_python.utils.correct` applies match suggestions to a text, and
:func:`~language_tool_python.utils.classify_matches` categorises a list of matches as
:attr:`~language_tool_python.utils.TextStatus.CORRECT`,
:attr:`~language_tool_python.utils.TextStatus.FAULTY`, or
:attr:`~language_tool_python.utils.TextStatus.GARBAGE`.

.. automodule:: language_tool_python.utils
   :members:
   :show-inheritance:
   :undoc-members:

Exceptions - :mod:`language_tool_python.exceptions`
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

All custom exceptions raised by the library. Every exception inherits from
:class:`~language_tool_python.exceptions.LanguageToolError`, so a single
``except LanguageToolError`` clause is sufficient to catch all library errors.

.. automodule:: language_tool_python.exceptions
   :members:
   :show-inheritance:
   :undoc-members:

Language tags - :mod:`language_tool_python.language_tag`
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

:class:`~language_tool_python.language_tag.LanguageTag` normalises BCP 47 language
tags (e.g. ``"en-US"``, ``"de-DE"``) to the format expected by LanguageTool, and
handles POSIX locale fallbacks.

.. automodule:: language_tool_python.language_tag
   :members:
   :show-inheritance:
   :undoc-members:

Server configuration - :mod:`language_tool_python.config_file`
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

:class:`~language_tool_python.config_file.LanguageToolConfig` accepts a
:data:`~language_tool_python.config_file.ConfigValue` dictionary and writes it to a
temporary file that is passed to the LanguageTool Java process via ``--config``.

.. automodule:: language_tool_python.config_file
   :members:
   :show-inheritance:
   :undoc-members:

Advanced
--------

Download management - :mod:`language_tool_python.download_lt`
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Handles downloading and caching the LanguageTool JAR. Exposed for advanced use cases
such as pinning a specific LanguageTool version or working with snapshot builds.
The default download version is given by :data:`~language_tool_python.download_lt.LTP_DOWNLOAD_VERSION`.

.. automodule:: language_tool_python.download_lt
   :members:
   :show-inheritance:
   :undoc-members:

Internal utilities - :mod:`language_tool_python._internals`
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Only the types from this private module that surface in the public API are documented
here. :class:`~language_tool_python._internals.api_types.CheckMatch` in particular
appears in the :class:`~language_tool_python.match.Match` constructor signature.
Note that if you have to perform type checking against :class:`~language_tool_python._internals.api_types.CheckMatch` (if you need to construct a :class:`~language_tool_python.match.Match` manually, for example), you can use the function :func:`~language_tool_python.match.is_check_match` as a type guard (this function is in the public API). :class:`~language_tool_python._internals.utils.SupportsBool` is also used in the public API, as it is in the alias type :data:`~language_tool_python.config_file.ConfigValue`. Stuff from this module is not intended for public use, and may change or be removed without notice.

.. autoclass:: language_tool_python._internals.api_types.CheckMatch

.. autoclass:: language_tool_python._internals.api_types.Replacement

.. autoclass:: language_tool_python._internals.api_types.ReplacementOptional

.. autoclass:: language_tool_python._internals.api_types.Context

.. autoclass:: language_tool_python._internals.api_types.MatchType

.. autoclass:: language_tool_python._internals.api_types.Rule

.. autoclass:: language_tool_python._internals.api_types.RuleOptional

.. autoclass:: language_tool_python._internals.api_types.Category

.. autoclass:: language_tool_python._internals.utils.SupportsBool
