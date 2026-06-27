"""Configuration for the property-based test suite."""

from __future__ import annotations

from pathlib import Path

import pytest


def pytest_collection_modifyitems(
    items: list[pytest.Item],
) -> None:
    """Apply the 'property' marker to all tests collected from this directory."""
    property_dir = Path(__file__).parent
    for item in items:
        if item.path.is_relative_to(property_dir):
            item.add_marker(pytest.mark.property)
