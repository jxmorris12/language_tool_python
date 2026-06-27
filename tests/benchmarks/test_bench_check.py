"""Benchmark tests for LanguageTool grammar checking performance.

Run with: pytest tests/benchmarks/ -v
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

import language_tool_python

if TYPE_CHECKING:
    from collections.abc import Generator

    from pytest_benchmark.fixture import BenchmarkFixture

_SHORT_TEXT = "This is a sentence with some erors in it. "
_MEDIUM_TEXT = (_SHORT_TEXT * 20).strip()
_LONG_TEXT = (_SHORT_TEXT * 100).strip()


@pytest.fixture(scope="module")
def tool() -> Generator[language_tool_python.LanguageTool, None, None]:
    """Provide a LanguageTool instance shared across benchmarks in this module."""
    with language_tool_python.LanguageTool("en-US") as t:
        yield t


@pytest.fixture(scope="module")
def cached_tool() -> Generator[language_tool_python.LanguageTool, None, None]:
    """Provide a pipeline-caching LanguageTool instance for cache benchmarks."""
    with language_tool_python.LanguageTool(
        "en-US",
        config={"cacheSize": 1000, "pipelineCaching": True},
    ) as t:
        yield t


def test_bench_check_short_text(
    benchmark: BenchmarkFixture,
    tool: language_tool_python.LanguageTool,
) -> None:
    """Benchmark grammar checking on a short sentence (~38 characters)."""
    benchmark(tool.check, _SHORT_TEXT)


def test_bench_check_medium_text(
    benchmark: BenchmarkFixture,
    tool: language_tool_python.LanguageTool,
) -> None:
    """Benchmark grammar checking on medium-length text (~840 characters)."""
    benchmark(tool.check, _MEDIUM_TEXT)


def test_bench_check_long_text(
    benchmark: BenchmarkFixture,
    tool: language_tool_python.LanguageTool,
) -> None:
    """Benchmark grammar checking on long text (~4200 characters)."""
    benchmark(tool.check, _LONG_TEXT)


def test_bench_correct_short_text(
    benchmark: BenchmarkFixture,
    tool: language_tool_python.LanguageTool,
) -> None:
    """Benchmark automatic text correction on a short sentence."""
    benchmark(tool.correct, _SHORT_TEXT)


def test_bench_check_with_pipeline_cache(
    benchmark: BenchmarkFixture,
    cached_tool: language_tool_python.LanguageTool,
) -> None:
    """Benchmark grammar checking with pipeline caching enabled.

    Compare with test_bench_check_short_text to measure cache speedup.
    """
    benchmark(cached_tool.check, _SHORT_TEXT)
