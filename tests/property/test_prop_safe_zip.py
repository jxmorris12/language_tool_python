"""Property-based tests for the safe ZIP extractor path-traversal protection."""

import contextlib
import io
import shutil
import uuid
import zipfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from language_tool_python._internals.safe_zip import SafeZipExtractor
from language_tool_python.exceptions import PathError

_TRAVERSAL_PREFIXES = ["../", "..\\", "/", "C:/", "..\\..\\"]


def _make_zip_payload(files: dict[str, bytes]) -> bytes:
    """Create an in-memory ZIP payload for testing."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in files.items():
            zf.writestr(name, data)
    return buf.getvalue()


@contextmanager
def _temp_dir() -> Iterator[Path]:
    """Create a temporary dir inside the project workspace to avoid perm issues."""
    root = Path.cwd() / ".test_prop_safe_zip_tmp"
    path = root / uuid.uuid4().hex
    path.mkdir(parents=True)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)
        with contextlib.suppress(OSError):
            root.rmdir()


@given(
    traversal=st.sampled_from(_TRAVERSAL_PREFIXES),
    suffix=st.text(
        alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Nd")),
        min_size=1,
    ),
)
@settings(max_examples=300)
def test_prop_safe_zip_path_traversal_always_rejected(
    traversal: str,
    suffix: str,
) -> None:
    """Any ZIP member whose name begins with a path-traversal prefix must be rejected.

    Checks that ``SafeZipExtractor`` raises ``PathError`` for filenames like
    ``../evil``, ``/etc/passwd``, or ``C:/Windows/file`` regardless of the suffix.

    :param traversal: A path-traversal prefix (e.g. ``../``, ``/``).
    :param suffix: Alphanumeric suffix appended after the traversal prefix.
    :raises AssertionError: If ``PathError`` is not raised for the unsafe member name.
    """
    filename = traversal + suffix
    payload = _make_zip_payload({filename: b"payload"})

    with (
        _temp_dir() as dest,
        zipfile.ZipFile(io.BytesIO(payload)) as zf,
        pytest.raises(PathError, match="Unsafe ZIP member"),
    ):
        SafeZipExtractor().extractall(zf, dest)
