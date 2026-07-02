"""Benchmark tests for LanguageTool grammar checking performance.

Run with: pytest tests/benchmarks/ -v

A JVM is required to run these benchmarks. If the local LanguageTool JAR cache is
empty, the first ``LanguageTool(...)`` call in this module triggers a real download
of the LanguageTool archive over the network.
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
    """Provide a LanguageTool instance shared across benchmarks in this module.

    Performs one warm-up ``check()`` call before yielding, since pytest.ini does
    not configure ``--benchmark-warmup``: without it, whichever benchmark happens
    to run first in this module would absorb the server's cold-start JIT cost.
    """
    with language_tool_python.LanguageTool("en-US") as t:
        t.check("warm-up")
        yield t


@pytest.fixture(scope="module")
def cached_tool() -> Generator[language_tool_python.LanguageTool, None, None]:
    """Provide a pipeline-caching LanguageTool instance for cache benchmarks.

    ``cacheSize=1000`` sets the maximum number of previously checked sentences the
    server keeps in memory, ``pipelineCaching=True`` additionally caches the
    internal per-language analysis pipeline (tokenizer, tagger, etc.) so it is not
    rebuilt on every request. Together they let repeated checks of the same
    sentence skip most of the analysis work.

    Performs one warm-up ``check()`` call (on text distinct from the benchmarked
    sentence, so it does not itself pre-populate the cache for that sentence)
    before yielding, for the same cold-start reason as the ``tool`` fixture above.
    """
    with language_tool_python.LanguageTool(
        "en-US",
        config={"cacheSize": 1000, "pipelineCaching": True},
    ) as t:
        t.check("warm-up, unrelated to any benchmarked sentence")
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

    Every round checks the same ``_SHORT_TEXT`` on the same server instance, so
    (after the fixture's warm-up call) all rounds but the very first are cache
    hits. Compare the resulting numbers with ``test_bench_check_short_text``
    (same text, no caching configured) to estimate the cache's speedup, this
    test alone does not exercise a cache miss/hit contrast within itself.
    """
    benchmark(cached_tool.check, _SHORT_TEXT)
