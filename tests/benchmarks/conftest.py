"""Configuration for the benchmark test suite."""

from __future__ import annotations

from pathlib import Path

import pytest


def pytest_collection_modifyitems(
    config: pytest.Config,
    items: list[pytest.Item],
) -> None:
    """Apply the 'perf' marker to all tests collected from this directory.

    Benchmarks require a running JVM and are slow, so they're opt-in: skipped
    unless explicitly selected with ``-m perf`` (or a markexpr referencing it).
    """
    benchmarks_dir = Path(__file__).parent
    markexpr: str = config.getoption("markexpr")
    run_perf = "perf" in markexpr
    skip_perf = pytest.mark.skip(
        reason="Benchmarks are opt-in, run with -m perf to include them."
    )
    for item in items:
        if item.path.is_relative_to(benchmarks_dir):
            item.add_marker(pytest.mark.perf)
            if not run_perf:
                item.add_marker(skip_perf)
