"""Tests for the local server functionality of LanguageTool."""

import subprocess
import time
from typing import Optional


def test_process_starts_and_stops_in_context_manager() -> None:
    """
    Test that the LanguageTool server process starts and stops correctly with context manager.
    This test verifies that when using LanguageTool as a context manager, the server process
    is running while inside the context and is properly terminated when exiting the context.

    :raises AssertionError: If the server process is not running after creation or
                           if it continues running after context manager exit.
    """
    import language_tool_python

    with language_tool_python.LanguageTool("en-US") as tool:
        proc: Optional[subprocess.Popen[str]] = tool._server
        if proc is None:
            raise AssertionError("tool._server is None after creation")
        # Make sure process is running before killing language tool object.
        assert proc.poll() is None, "tool._server not running after creation"
    time.sleep(0.5)  # Give some time for process to stop after context manager exit.
    # Make sure process stopped after close() was called.
    assert proc.poll() is not None, "tool._server should stop running after deletion"


def test_process_starts_and_stops_on_close() -> None:
    """
    Test that the LanguageTool server process starts and stops correctly with explicit close().
    This test verifies that when explicitly calling close() on a LanguageTool instance,
    the server process is properly terminated before object deletion.

    :raises AssertionError: If the server process is not running after creation or
                           if it continues running after close() is called.
    """
    import language_tool_python

    tool = language_tool_python.LanguageTool("en-US")
    proc: Optional[subprocess.Popen[str]] = tool._server
    if proc is None:
        raise AssertionError("tool._server is None after creation")
    # Make sure process is running before killing language tool object.
    assert proc.poll() is None, "tool._server not running after creation"
    tool.close()  # Explicitly close() object so process stops before garbage collection.
    del tool
    # Make sure process stopped after close() was called.
    time.sleep(0.5)  # Give some time for process to stop after close() call.
    assert proc.poll() is not None, "tool._server should stop running after deletion"
    # remember --> if poll is None: # p.subprocess is alive


def test_local_client_server_connection() -> None:
    """
    Test client-server connection between two LanguageTool instances.
    This test verifies that a LanguageTool instance can act as a server and another
    instance can successfully connect to it as a remote client, allowing grammar checking
    to be performed through the client-server architecture.

    :raises AssertionError: If the client cannot successfully check text through the server.
    """
    import language_tool_python

    with language_tool_python.LanguageTool("en-US", host="127.0.0.1") as tool1:
        url = "http://{}:{}/".format(tool1._host, tool1._port)
        with language_tool_python.LanguageTool("en-US", remote_server=url) as tool2:
            assert len(tool2.check("helo darknes my old frend"))


def test_session_only_new_spellings() -> None:
    """
    Test that session-only new spellings do not persist to the spelling file.
    This test verifies that when new_spellings_persist is set to False, custom spellings
    added during a session are recognized by the tool but do not modify the permanent
    spelling dictionary file.

    :raises AssertionError: If the spelling file is modified or if new spellings are not
                           recognized during the session.
    """
    import hashlib

    import language_tool_python

    library_path = language_tool_python.utils.get_language_tool_directory()
    spelling_file_path = (
        library_path
        / "org"
        / "languagetool"
        / "resource"
        / "en"
        / "hunspell"
        / "spelling.txt"
    )
    with open(spelling_file_path, "r") as spelling_file:
        initial_spelling_file_contents = spelling_file.read()
    initial_checksum = hashlib.sha256(initial_spelling_file_contents.encode())

    new_spellings = ["word1", "word2", "word3"]
    with language_tool_python.LanguageTool(
        "en-US",
        new_spellings=new_spellings,
        new_spellings_persist=False,
    ) as tool:
        tool.enabled_rules_only = True
        tool.enabled_rules = {"MORFOLOGIK_RULE_EN_US"}
        matches = tool.check(" ".join(new_spellings))

    with open(spelling_file_path, "r") as spelling_file:
        subsequent_spelling_file_contents = spelling_file.read()
    subsequent_checksum = hashlib.sha256(subsequent_spelling_file_contents.encode())

    if initial_checksum != subsequent_checksum:
        with open(spelling_file_path, "w") as spelling_file:
            spelling_file.write(initial_spelling_file_contents)

    assert not matches
    assert initial_checksum.hexdigest() == subsequent_checksum.hexdigest()


def test_uk_typo() -> None:
    """
    Test grammar checking and correction with UK English language rules.
    This test verifies that LanguageTool correctly identifies and corrects grammar errors
    specific to UK English, including proper handling of contractions like "you're" and "your",
    while respecting UK English conventions where "You're" can mean "Your" in certain contexts.

    :raises AssertionError: If the detected errors or corrections do not match expected UK English rules.
    """
    import language_tool_python

    with language_tool_python.LanguageTool("en-UK") as tool:
        sentence1 = "If you think this sentence is fine then, your wrong."
        results1 = tool.check(sentence1)
        assert len(results1) == 1
        assert (
            language_tool_python.utils.correct(sentence1, results1)
            == "If you think this sentence is fine then, you're wrong."
        )

        results2 = tool.check("You're mum is called Emily, is that right?")
        assert len(results2) == 0
