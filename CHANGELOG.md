# language_tool_python Changelog

## 3.4.0 (2026-05-15)
- Corrected a bug in `language_tool_python.server.LanguageTool.check` where the LT `/check` endpoint was queried with GET instead of POST.
- Corrected a bug in `language_tool_python.config_file.LanguageToolConfig` where config keys and values could contain line breaks or end with an odd number of backslashes.
- Corrected the default LT download version (from `latest` snapshot to release `6.8`).
- Added SHA-256 verification for downloaded LT zip files.
- Added a bundled `language_tool_python/integrity.toml` manifest containing SHA-256 checksums for LT release/archive downloads.
- Added new env variables for LT download verification:
    - `LTP_DOWNLOAD_SHA256_<VERSION>`
    - `LTP_DOWNLOAD_SHA256`
    - `LTP_BYPASS_VERIFIED_DOWNLOADS`
- Added a maximum download size limit for LT zip files, configurable with `LTP_MAX_DOWNLOAD_BYTES`.
- Added `language_tool_python.safe_zip.SafeZipExtractor` and `language_tool_python.safe_zip.SafeZipLimits` to extract ZIP files safely.
- Edited LT ZIP extraction to reject unsafe paths, symlinks, unsupported member types, duplicate paths, file/directory conflicts, oversized archives/members, suspicious compression ratios and overwrites of existing paths.
- Added new env variables for safe ZIP extraction limits:
    - `LTP_SAFE_ZIP_MAX_ARCHIVE_BYTES`
    - `LTP_SAFE_ZIP_MAX_EXTRACTED_BYTES`
    - `LTP_SAFE_ZIP_MAX_MEMBERS`
    - `LTP_SAFE_ZIP_MAX_MEMBER_EXTRACTED_BYTES`
    - `LTP_SAFE_ZIP_MAX_MEMBER_COMPRESSION_RATIO`
    - `LTP_SAFE_ZIP_MAX_TOTAL_COMPRESSION_RATIO`
- Added the possibility to download LT releases 6.7 and newer from the new release page.
- Added `LTP_DOWNLOAD_HOST_NEW_RELEASES` to override the new LT release download host.
- Added `language_tool_python.utils.get_env_int` and `language_tool_python.utils.get_env_float`.

## 3.3.1 (2026-05-10)
- Edited the LanguageTool snapshot current version (from 6.8-SNAPSHOT to 6.9-SNAPSHOT) to allow users to retrieve automatically the latest snapshot version of LT.

## 3.3.0 (2026-03-07)
- Corrected a bug in `language_tool_python.server.LanguageTool._get_valid_spelling_file_path` where the spelling file was always the one for English, even when the LT instance was configured for a different language.
- Corrected a bug in `language_tool_python.server.LanguageTool` where, even if you specified a `language_tool_download_version`, the used LT version was always the latest one present on the system (the download was working correctly, but the downloaded version was not used).
- Corrected the necessary java version for old LT releases (from 1.8 to 1.9).
- Added an abstract class `LocalLanguageTool` that expose an common interface for subclasses who implements some type of LT download.
- Added `ReleaseLocalLanguageTool` class (implementation of `LocalLanguageTool`) that implements the downloading of LT from release/archive page.
- Added `SnapshotLocalLanguageTool` class (implementation of `LocalLanguagetool`) that implements the downloading of LT from snapshot page.
- Edited the low limit of the supported LT version (now at release 4.0).
- Deprecated some funcs (they remain available until version 4.0.0):
    - `language_tool_python.download_lt.get_common_prefix`
    - `language_tool_python.download_lt.http_get`
    - `language_tool_python.download_lt.unzip_file`
    - `language_tool_python.download_lt.download_zip`
    - `language_tool_python.download_lt.download_lt`
    - `language_tool_python.utils.find_existing_language_tool_downloads`
    - `language_tool_python.utils._extract_version`
    - `language_tool_python.utils.get_language_tool_directory`
    - `language_tool_python.utils.get_server_cmd`
    - `language_tool_python.utils.get_jar_info`

## 3.2.2 (2026-01-02)
- Corrected a bug in `language_tool_python.download_lt.http_get` by adding proper handling of HTTP 403 and other non 200 status codes by raising `language_tool_python.exceptions.PathError`. Previously, in case of such status codes, the function would download an HTML error page instead of the expected zip file, leading to an error when attempting to unzip it.

## 3.2.1 (2025-12-30)
- Corrected a bug in `language_tool_python.server._kill_processes` where processes were not being properly waited for after being killed, potentially leading to zombie processes.

## 3.2.0 (2025-12-18)
- Added a `check_matching_regions` method in `language_tool_python.server.LanguageTool`.

## 3.1.0 (2025-11-23)
- Added an optional parameter to `LanguageTool` (`proxies`).
- Added an `proxies` attribute to `LanguageTool` (This attribute is used by the `LanguageTool._query_server` method).
- Added new read-only properties to `LanguageTool`:
    - `url`
    - `is_remote`
    - `host`
    - `port`
- Edited the documentation of the `LanguageTool` class to improve clarity.

## 3.0.0 (2025-11-20)

### What's New:
- Corrected a bug when the default locale is POSIX default (C).
- Corrected a bug when closing `LanguageTool` instances (deadlocks).
- Corrected a bug when comparing LT versions (e.g., '5.8' vs '5.10').
- Added new possible values in LT config (`trustXForwardForHeader`, `suggestionsEnabled` and lang keys).
- Added a warning if you forget to explicitly close a `LanguageTool` instance.
- Added online documentation for the package.
- Added logging (and logs) in the package.
- Added raising `exceptions.TimeoutError` in `download_lt.http_get`.
- Added `packaging` as a dependency.
- Moved exception classes to a separate `exceptions` module (no more importable from `utils`).
- Edited raised exceptions in some methods/functions:
    - from `AssertionError` to `ValueError` in `config_file.LanguageToolConfig.__init__`
    - from `AssertionError` to `exceptions.PathError` in `download_lt.download_lt`
    - from `AssertionError` to `ValueError` in `download_lt.download_lt`
    - from `AssertionError` to `ValueError` in `server.LanguageTool.__init__`
    - from `AssertionError` to `ValueError` in `utils.kill_process_force`
- Edited some camelCase attributes/methods to snake_case:
    - `server.LanguageTool.motherTongue` to `server.LanguageTool.mother_tongue`
    - `server.LanguageTool.newSpellings` to `server.LanguageTool.new_spellings`
    - `match.Match.ruleId` to `match.Match.rule_id`
    - `match.Match.offsetInContext` to `match.Match.offset_in_context`
    - `match.Match.errorLength` to `match.Match.error_length`
    - `match.Match.ruleIssueType` to `match.Match.rule_issue_type`
    - `match.Match.matchedText` to `match.Match.matched_text`
- Edited types of some params:
    - `directory_to_extract_to` in `dowload_lt.unzip_file` from `str` to `Path`
    - `directory` in `download_lt.download_zip` from `str` to `Path`
    - `download_folder` in `utils.find_existing_language_tool_downloads` from `str` to `Path`
- Edited return types of some methods/functions:
    - from `str` to `Path` in `utils.get_language_tool_download_path`
    - from `list[str]` to `list[Path]` in `utils.find_existing_language_tool_downloads`
    - from `str` to `Path` in `utils.get_language_tool_directory`
    - from `tuple[str, str]` to `tuple[Path, Path]` in `utils.get_jar_info`
