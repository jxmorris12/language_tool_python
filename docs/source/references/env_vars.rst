Environment variables
=====================

The following environment variables control runtime behaviour without requiring code
changes.

Download and cache
------------------

.. list-table::
   :header-rows: 1
   :widths: 45 55

   * - Variable
     - Description
   * - ``LTP_PATH``
     - Directory used to store downloaded LanguageTool packages.
       Default: ``~/.cache/language_tool_python/``.
   * - ``LTP_JAR_DIR_PATH``
     - Path to an existing local LanguageTool installation directory. When set, the
       automatic download is skipped entirely.
   * - ``LTP_DOWNLOAD_HOST_SNAPSHOT``
     - Override the snapshot download host.
       Default: ``https://internal1.languagetool.org/snapshots/``.
   * - ``LTP_DOWNLOAD_HOST_NEW_RELEASES``
     - Override the release download host for LanguageTool ≥ 6.7.
       Default: ``https://github.com/jxmorris12/language_tool_python/releases/download/LanguageTool-{version}/``.
   * - ``LTP_DOWNLOAD_HOST_RELEASE``
     - Override the release download host for LanguageTool 6.0–6.6.
       Default: ``https://languagetool.org/download/``.
   * - ``LTP_DOWNLOAD_HOST_ARCHIVE``
     - Override the archive download host for LanguageTool 4.0–5.9.
       Default: ``https://languagetool.org/download/archive/``.
   * - ``LTP_MAX_DOWNLOAD_BYTES``
     - Maximum ZIP download size in bytes.
       Default: ``536870912`` (512 MiB).

Integrity verification
----------------------

Downloaded ZIPs are verified with SHA-256 when a checksum is available. Checksums are
resolved in this order:

1. ``LTP_DOWNLOAD_SHA256_<VERSION>`` - version-specific checksum. Non-alphanumeric
   characters in the version string are replaced with ``_`` and uppercased
   (e.g. ``LTP_DOWNLOAD_SHA256_6_8`` for version ``6.8``).
2. ``LTP_DOWNLOAD_SHA256`` - fallback checksum applied to any version.
3. The bundled ``language_tool_python/_ressources/integrity.toml`` manifest, which
   covers release and archive downloads. Snapshots are not included.

If none of the above resolves to a checksum, the download proceeds without verification.

.. list-table::
   :header-rows: 1
   :widths: 45 55

   * - Variable
     - Description
   * - ``LTP_DOWNLOAD_SHA256_<VERSION>``
     - Expected SHA-256 for a specific LanguageTool version
       (e.g. ``LTP_DOWNLOAD_SHA256_6_8=<hash>``).
   * - ``LTP_DOWNLOAD_SHA256``
     - Fallback SHA-256 for any downloaded archive.
   * - ``LTP_BYPASS_VERIFIED_DOWNLOADS``
     - Set to ``true`` to skip SHA-256 verification entirely.

Safe ZIP extraction limits
--------------------------

.. list-table::
   :header-rows: 1
   :widths: 45 55

   * - Variable
     - Description
   * - ``LTP_SAFE_ZIP_MAX_ARCHIVE_BYTES``
     - Maximum total compressed size in bytes.
       Default: ``536870912`` (512 MiB).
   * - ``LTP_SAFE_ZIP_MAX_EXTRACTED_BYTES``
     - Maximum total extracted size in bytes.
       Default: ``805306368`` (768 MiB).
   * - ``LTP_SAFE_ZIP_MAX_MEMBERS``
     - Maximum number of members in the ZIP archive.
       Default: ``5000``.
   * - ``LTP_SAFE_ZIP_MAX_MEMBER_EXTRACTED_BYTES``
     - Maximum extracted size for a single member in bytes.
       Default: ``134217728`` (128 MiB).
   * - ``LTP_SAFE_ZIP_MAX_MEMBER_COMPRESSION_RATIO``
     - Maximum compression ratio for a single member.
       Default: ``100.0``.
   * - ``LTP_SAFE_ZIP_MAX_TOTAL_COMPRESSION_RATIO``
     - Maximum compression ratio for the whole archive.
       Default: ``10.0``.

Example
-------

.. code-block:: bash

   # Use a custom cache directory
   export LTP_PATH=/path/to/cache

   # Skip download and use an existing installation
   export LTP_JAR_DIR_PATH=/path/to/LanguageTool-6.8

   # Verify a specific release
   export LTP_DOWNLOAD_SHA256_6_8=<sha256>

   # Or bypass verification entirely (not recommended)
   export LTP_BYPASS_VERIFIED_DOWNLOADS=true
