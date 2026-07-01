# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/2.0.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Added `-D`/`--disable-categories` and `-E`/`--enable-categories` CLI options to disable or enable LanguageTool rule categories (e.g. `TYPOS`, `GRAMMAR`). `--enabled-only` now also applies to categories specified via `--enable-categories`.
- Added `premium_key` property to `language_tool_python.server.LanguageTool` to attach a premium API key for LanguageTool API requests.
- Added `premium_username` property to `language_tool_python.server.LanguageTool` to attach a username for premium LanguageTool API requests.
- Added `language_tool_python.match.is_check_match` type guard function to verify that a value is a `CheckMatch` (type from `language_tool_python._internals`).
- Added `language_tool_python.config_file.ConfigValue` public type alias representing all accepted value types for `LanguageToolConfig`.

### Changed
- HTTP requests to the LanguageTool server now reuse a persistent `requests.Session`, reducing TCP connection overhead for repeated calls to `.check()`.
- **Breaking:** Dropped Python 3.9 support, now supports Python 3.10-3.15.
- **Breaking:** Moved internal utilities to a private `_internals` subpackage:
    - `language_tool_python.safe_zip` -> `language_tool_python._internals.safe_zip`
    - `language_tool_python.utils.parse_url` -> `language_tool_python._internals.utils.parse_url`
    - `language_tool_python.utils.get_env_int` -> `language_tool_python._internals.utils.get_env_int`
    - `language_tool_python.utils.get_env_float` -> `language_tool_python._internals.utils.get_env_float`
    - `language_tool_python.utils.get_language_tool_download_path` -> `language_tool_python._internals.utils.get_language_tool_download_path`
    - `language_tool_python.utils.get_locale_language` -> `language_tool_python._internals.utils.get_locale_language`
    - `language_tool_python.utils.kill_process_force` -> `language_tool_python._internals.utils.kill_process_force`
- Removed `packaging` as a runtime dependency.
- **Breaking:** Narrowed the type of the `config` parameter of `language_tool_python.config_file.LanguageToolConfig.__init__` from `dict[str, Any]` to `Mapping[str, ConfigValue]`.
- **Breaking:** Changed return type of `language_tool_python.download_lt.LocalLanguageTool.version_into` and `language_tool_python.download_lt.ReleaseLocalLanguageTool.version_into` from `packaging.version.Version` to `tuple[int, int]`.
- Replaced `toml` dependency with `tomli` for Python < 3.11 (fallback for the stdlib `tomllib`).
- Added `typing_extensions` as a dependency for Python < 3.13 (fallback for the stdlib `warnings.deprecated`).

### Fixed
- Corrected a bug in `language_tool_python.config_file.LanguageToolConfig` where directory paths were incorrectly rejected by the path validator.
- Fixed a bug in `LanguageTool._start_server_on_free_port` where `_url` was not updated when retrying on a different port, causing all subsequent server requests to target the wrong (original) port.
- Fixed a bug in `LanguageTool._query_server` where `RateLimitError` was only raised when the rate-limit response body was invalid JSON, a valid JSON body with status 426 was silently returned as data instead (for now, the body from LanguageTool for rate-limiting responses is "Upgrade Required", which is not valid JSON, but this may change in the future).

### Removed
- **Breaking:** Removed all functions and classes previously deprecated in v3.3.0:
    - `language_tool_python.download_lt.get_common_prefix`
    - `language_tool_python.download_lt.http_get`
    - `language_tool_python.download_lt.unzip_file`
    - `language_tool_python.download_lt.download_zip`
    - `language_tool_python.download_lt.download_lt`
    - `language_tool_python.utils.find_existing_language_tool_downloads`
    - `language_tool_python.utils.get_language_tool_directory`
    - `language_tool_python.utils.get_server_cmd`
    - `language_tool_python.utils.get_jar_info`
    - `language_tool_python.match.auto_type`

## [3.4.0] - 2026-05-15

> Security hardening for LT downloads: SHA-256 integrity verification, safe ZIP extraction, configurable size limits, and support for LT releases 6.7+.

### Added
- Added SHA-256 verification for downloaded LT zip files.
- Added a bundled `language_tool_python/integrity.toml` manifest containing SHA-256 checksums for LT release/archive downloads.
- Added new env variables for LT download verification:
    - `LTP_DOWNLOAD_SHA256_<VERSION>`
    - `LTP_DOWNLOAD_SHA256`
    - `LTP_BYPASS_VERIFIED_DOWNLOADS`
- Added a maximum download size limit for LT zip files, configurable with `LTP_MAX_DOWNLOAD_BYTES`.
- Added `language_tool_python.safe_zip.SafeZipExtractor` and `language_tool_python.safe_zip.SafeZipLimits` to extract ZIP files safely.
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

### Changed
- Edited the default LT download version (from `latest` snapshot to release `6.8`).
- Edited LT ZIP extraction to reject unsafe paths, symlinks, unsupported member types, duplicate paths, file/directory conflicts, oversized archives/members, suspicious compression ratios and overwrites of existing paths.

### Fixed
- Corrected a bug in `language_tool_python.server.LanguageTool.check` where the LT `/check` endpoint was queried with GET instead of POST.
- Corrected a bug in `language_tool_python.config_file.LanguageToolConfig` where config keys and values could contain line breaks or end with an odd number of backslashes.

## [3.3.1] - 2026-05-10

### Changed
- Edited the LanguageTool snapshot current version (from 6.8-SNAPSHOT to 6.9-SNAPSHOT) to allow users to retrieve automatically the latest snapshot version of LT.

## [3.3.0] - 2026-03-07

### Added
- Added an abstract class `LocalLanguageTool` that expose an common interface for subclasses who implements some type of LT download.
- Added `ReleaseLocalLanguageTool` class (implementation of `LocalLanguageTool`) that implements the downloading of LT from release/archive page.
- Added `SnapshotLocalLanguageTool` class (implementation of `LocalLanguagetool`) that implements the downloading of LT from snapshot page.

### Changed
- Edited the low limit of the supported LT version (now at release 4.0).

### Deprecated
- Deprecated some funcs (they remain available until version 4.0.0):
    - `language_tool_python.download_lt.get_common_prefix`
    - `language_tool_python.download_lt.http_get`
    - `language_tool_python.download_lt.unzip_file`
    - `language_tool_python.download_lt.download_zip`
    - `language_tool_python.download_lt.download_lt`
    - `language_tool_python.utils.find_existing_language_tool_downloads`
    - `language_tool_python.utils.get_language_tool_directory`
    - `language_tool_python.utils.get_server_cmd`
    - `language_tool_python.utils.get_jar_info`

### Fixed
- Corrected a bug in `language_tool_python.server.LanguageTool._get_valid_spelling_file_path` where the spelling file was always the one for English, even when the LT instance was configured for a different language.
- Corrected a bug in `language_tool_python.server.LanguageTool` where, even if you specified a `language_tool_download_version`, the used LT version was always the latest one present on the system (the download was working correctly, but the downloaded version was not used).
- Corrected the necessary java version for old LT releases (from 1.8 to 1.9).

## [3.2.2] - 2026-01-02

### Fixed
- Corrected a bug in `language_tool_python.download_lt.http_get` by adding proper handling of HTTP 403 and other non 200 status codes by raising `language_tool_python.exceptions.PathError`. Previously, in case of such status codes, the function would download an HTML error page instead of the expected zip file, leading to an error when attempting to unzip it.

## [3.2.1] - 2025-12-30

### Fixed
- Corrected a bug in `language_tool_python.server._kill_processes` where processes were not being properly waited for after being killed, potentially leading to zombie processes.

## [3.2.0] - 2025-12-18

### Added
- Added a `check_matching_regions` method in `language_tool_python.server.LanguageTool`.

## [3.1.0] - 2025-11-23

### Added
- Added an optional parameter to `LanguageTool` (`proxies`).
- Added an `proxies` attribute to `LanguageTool` (This attribute is used by the `LanguageTool._query_server` method).
- Added new read-only properties to `LanguageTool`:
    - `url`
    - `is_remote`
    - `host`
    - `port`

### Changed
- Edited the documentation of the `LanguageTool` class to improve clarity.

## [3.0.0] - 2025-11-20

> Major rewrite: snake_case naming conventions, strict Python types, dedicated `exceptions` module, logging, and online documentation.

### Added
- Added new possible values in LT config (`trustXForwardForHeader`, `suggestionsEnabled` and lang keys).
- Added a warning if you forget to explicitly close a `LanguageTool` instance.
- Added online documentation for the package.
- Added logging (and logs) in the package.
- Added raising `exceptions.TimeoutError` in `download_lt.http_get`.
- Added `packaging` as a dependency.

### Changed
- **Breaking:** Moved exception classes to a separate `exceptions` module (no more importable from `utils`).
- **Breaking:** Edited raised exceptions in some methods/functions:
    - from `AssertionError` to `ValueError` in `config_file.LanguageToolConfig.__init__`
    - from `AssertionError` to `exceptions.PathError` in `download_lt.download_lt`
    - from `AssertionError` to `ValueError` in `download_lt.download_lt`
    - from `AssertionError` to `ValueError` in `server.LanguageTool.__init__`
    - from `AssertionError` to `ValueError` in `utils.kill_process_force`
- **Breaking:** Edited some camelCase attributes/methods to snake_case:
    - `server.LanguageTool.motherTongue` to `server.LanguageTool.mother_tongue`
    - `server.LanguageTool.newSpellings` to `server.LanguageTool.new_spellings`
    - `match.Match.ruleId` to `match.Match.rule_id`
    - `match.Match.offsetInContext` to `match.Match.offset_in_context`
    - `match.Match.errorLength` to `match.Match.error_length`
    - `match.Match.ruleIssueType` to `match.Match.rule_issue_type`
    - `match.Match.matchedText` to `match.Match.matched_text`
- **Breaking:** Edited types of some params:
    - `directory_to_extract_to` in `dowload_lt.unzip_file` from `str` to `Path`
    - `directory` in `download_lt.download_zip` from `str` to `Path`
    - `download_folder` in `utils.find_existing_language_tool_downloads` from `str` to `Path`
- **Breaking:** Edited return types of some methods/functions:
    - from `str` to `Path` in `utils.get_language_tool_download_path`
    - from `list[str]` to `list[Path]` in `utils.find_existing_language_tool_downloads`
    - from `str` to `Path` in `utils.get_language_tool_directory`
    - from `tuple[str, str]` to `tuple[Path, Path]` in `utils.get_jar_info`

### Fixed
- Corrected a bug when the default locale is POSIX default (C).
- Corrected a bug when closing `LanguageTool` instances (deadlocks).
- Corrected a bug when comparing LT versions (e.g., '5.8' vs '5.10').

[Unreleased]: https://github.com/jxmorris12/language_tool_python/compare/3.4.0...HEAD
[3.4.0]: https://github.com/jxmorris12/language_tool_python/compare/3.3.1...3.4.0
[3.3.1]: https://github.com/jxmorris12/language_tool_python/compare/3.3.0...3.3.1
[3.3.0]: https://github.com/jxmorris12/language_tool_python/compare/3.2.2...3.3.0
[3.2.2]: https://github.com/jxmorris12/language_tool_python/compare/3.2.1...3.2.2
[3.2.1]: https://github.com/jxmorris12/language_tool_python/compare/3.2.0...3.2.1
[3.2.0]: https://github.com/jxmorris12/language_tool_python/compare/3.1.0...3.2.0
[3.1.0]: https://github.com/jxmorris12/language_tool_python/compare/3.0.0...3.1.0
[3.0.0]: https://github.com/jxmorris12/language_tool_python/compare/2.9.5...3.0.0
