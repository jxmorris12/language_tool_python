"""Configuration for the benchmark test suite."""

from __future__ import annotations

from pathlib import Path

import pytest


def pytest_collection_modifyitems(
    items: list[pytest.Item],
) -> None:
    """Apply the 'perf' marker to all tests collected from this directory."""
    benchmarks_dir = Path(__file__).parent
    for item in items:
        if item.path.is_relative_to(benchmarks_dir):
            item.add_marker(pytest.mark.perf)
