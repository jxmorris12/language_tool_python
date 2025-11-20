# language_tool_python Changelog

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
    - from `List[str]` to `List[Path]` in `utils.find_existing_language_tool_downloads`
    - from `str` to `Path` in `utils.get_language_tool_directory`
    - from `Tuple[str, str]` to `Tuple[Path, Path]` in `utils.get_jar_info`
