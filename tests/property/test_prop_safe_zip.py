"""Property-based tests for the safe ZIP extractor path-traversal protection."""

from __future__ import annotations

import io
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from language_tool_python._internals.safe_zip import SafeZipExtractor
from language_tool_python.exceptions import PathError

if TYPE_CHECKING:
    from hypothesis.strategies import DrawFn

_TRAVERSAL_SEGMENTS = st.sampled_from([".."] * 3 + ["."])
_SEP = st.sampled_from(["/", "\\"])


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
    paths, Windows drive letters, and UNC paths, so the strategy is not limited
    to a small fixed set of prefixes.
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
    style = draw(st.sampled_from(["prefix", "embedded", "absolute", "drive", "unc"]))
    if style == "prefix":
        return sep.join([*segs, leaf])
    if style == "embedded":
        return sep.join(["safe", *segs, leaf])
    if style == "absolute":
        return sep + leaf
    if style == "drive":
        return draw(st.sampled_from("CDZ")) + ":" + sep + leaf
    return "\\\\server\\share\\" + leaf


@given(filename=adversarial_member_names())
@settings(max_examples=300, deadline=None)
def test_prop_safe_zip_path_traversal_always_rejected(filename: str) -> None:
    """Any adversarial ZIP member name must be rejected by SafeZipExtractor.

    Checks that ``SafeZipExtractor`` raises ``PathError`` for a wide range of
    unsafe filenames (traversal, absolute paths, drive letters, UNC paths)
    rather than a small fixed set of hand-picked prefixes.

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
