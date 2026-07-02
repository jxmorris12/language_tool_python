"""Property-based tests for the safe ZIP extractor path-traversal protection."""

from __future__ import annotations

import io
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING

import pytest
from hypothesis import example, given, settings
from hypothesis import strategies as st

from language_tool_python._internals.safe_zip import SafeZipExtractor
from language_tool_python.exceptions import PathError

if TYPE_CHECKING:
    from hypothesis.strategies import DrawFn

_TRAVERSAL_SEGMENTS = st.sampled_from([".."] * 3 + ["."])
_SEP = st.sampled_from(["/", "\\"])
_RESERVED_LEAVES = st.sampled_from(
    [
        "CON",
        "NUL",
        "PRN",
        "AUX",
        "COM1",
        "LPT1",
        "trailing-space ",
        "trailing-dot.",
        "file.txt:stream",
    ],
)


def _make_zip_payload(files: dict[str, bytes]) -> bytes:
    """Create an in-memory ZIP payload for testing."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in files.items():
            zf.writestr(name, data)
    return buf.getvalue()


@st.composite
def adversarial_member_names(draw: DrawFn) -> str:
    """Generate adversarial ZIP member names built from unsafe path segments.

    Combines repeated ``..`` traversal segments, mixed separators, absolute
    paths, Windows drive letters, UNC paths, traversal sandwiched between
    safe-looking components, and Windows-reserved/ADS-style leaf names, so the
    strategy is not limited to a small fixed set of prefixes or to traversal
    sitting only at the start of the path.
    """
    depth = draw(st.integers(min_value=1, max_value=4))
    segs = [draw(_TRAVERSAL_SEGMENTS) for _ in range(depth)]
    sep = draw(_SEP)
    leaf = draw(
        st.text(
            alphabet=st.characters(
                exclude_categories=["Cs"],
                exclude_characters="\x00",
            ),
            min_size=1,
            max_size=20,
        ),
    )
    style = draw(
        st.sampled_from(
            ["prefix", "embedded", "nested", "absolute", "drive", "unc", "reserved"],
        ),
    )
    if style == "prefix":
        name = sep.join([*segs, leaf])
    elif style == "embedded":
        name = sep.join(["safe", *segs, leaf])
    elif style == "nested":
        # Traversal sandwiched between two otherwise-safe-looking components,
        # e.g. "safe/../../also-safe/leaf" rather than only leading traversal.
        name = sep.join(["safe", *segs, "also-safe", leaf])
    elif style == "absolute":
        name = sep + leaf
    elif style == "drive":
        name = draw(st.sampled_from("CDZ")) + ":" + sep + leaf
    elif style == "unc":
        name = sep * 2 + "server" + sep + "share" + sep + leaf
    else:
        name = sep.join(["safe", draw(_RESERVED_LEAVES)])
    return name


@given(filename=adversarial_member_names())
@settings(max_examples=300, deadline=None)
@example(filename="../../../etc/passwd")
@example(filename="..\\..\\..\\Windows\\System32\\evil.dll")
@example(filename="safe/../../../etc/passwd")
@example(filename="\\\\server\\share\\..\\..\\evil")
@example(filename="safe/CON")
@example(filename="safe/file.txt:stream")
@example(filename="safe/trailing-dot.")
def test_prop_safe_zip_path_traversal_always_rejected(filename: str) -> None:
    """Any adversarial ZIP member name must be rejected by SafeZipExtractor.

    Checks that ``SafeZipExtractor`` raises ``PathError`` for a wide range of
    unsafe filenames (traversal anywhere in the path, absolute paths, drive
    letters, UNC paths, Windows-reserved/ADS-style names) rather than a small
    fixed set of hand-picked prefixes. A handful of canonical zip-slip payloads
    are pinned via ``@example`` so they are always checked regardless of the
    Hypothesis random seed.

    A fresh temporary directory is created per example instead of using a
    pytest fixture, since function-scoped fixtures are not reset between
    Hypothesis-generated examples within the same test call.

    :param filename: An adversarially generated ZIP member name.
    :raises AssertionError: If ``PathError`` is not raised for the unsafe member name.
    """
    payload = _make_zip_payload({filename: b"payload"})

    with (
        tempfile.TemporaryDirectory() as temp_dir,
        zipfile.ZipFile(io.BytesIO(payload)) as zf,
        pytest.raises(PathError, match="Unsafe ZIP member"),
    ):
        SafeZipExtractor().extractall(zf, Path(temp_dir) / "destination")


@given(
    member_path=st.lists(
        st.text(
            alphabet=st.characters(categories=["Ll", "Lu", "Nd"]),
            min_size=1,
            max_size=10,
        ),
        min_size=1,
        max_size=5,
    ).map(lambda parts: PurePosixPath(*parts)),
)
@settings(max_examples=200)
def test_prop_zip_target_always_inside_destination(member_path: PurePosixPath) -> None:
    """``_zip_target`` must always resolve inside the given destination.

    Exercises ``_zip_target`` directly (no ZIP I/O) so a large number of
    examples can be run quickly.

    :param member_path: An already-normalized, safe relative POSIX path.
    :raises AssertionError: If the resolved target escapes the destination.
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        destination = Path(temp_dir) / "destination"
        destination.mkdir()

        target = SafeZipExtractor()._zip_target(destination, member_path)

        resolved_destination = destination.resolve(strict=True)
        resolved_target = target.resolve(strict=False)
        assert (
            resolved_target == resolved_destination
            or resolved_destination in resolved_target.parents
        )


@given(filename=adversarial_member_names())
@settings(max_examples=300)
@example(filename="../../../etc/passwd")
@example(filename="safe/../../../etc/passwd")
@example(filename="safe/CON")
@example(filename="safe/file.txt:stream")
def test_prop_normalize_member_path_always_rejects_or_stays_relative(
    filename: str,
) -> None:
    """``_normalize_member_path`` must either reject or return a safe relative path.

    Exercises ``_normalize_member_path`` directly (no ZIP or filesystem I/O),
    so a large number of adversarial examples can be checked quickly.

    :param filename: An adversarially generated ZIP member name.
    :raises AssertionError: If a returned path is absolute or escapes upward.
    """
    extractor = SafeZipExtractor()
    try:
        normalized = extractor._normalize_member_path(filename)
    except PathError:
        return
    assert not normalized.is_absolute()
    assert ".." not in normalized.parts
