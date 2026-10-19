"""Basic tests to ensure package can be imported and has correct metadata.

ADR: 2025-12-11-duckdb-removal-clickhouse

test_processor_instantiation needs ClickHouse (see the `clickhouse` marker in conftest.py).
"""

import pytest

import exness_data_preprocess as edp


def test_package_import():
    """Test that package can be imported."""
    assert edp.__name__ == "exness_data_preprocess"


def test_version_exists():
    """Test that package has version attribute."""
    assert hasattr(edp, "__version__")
    assert isinstance(edp.__version__, str)


def test_processor_class_exists():
    """Test that ExnessDataProcessor class exists."""
    assert hasattr(edp, "ExnessDataProcessor")
    assert callable(edp.ExnessDataProcessor)


@pytest.mark.clickhouse
def test_processor_instantiation():
    """Test that ExnessDataProcessor can be instantiated."""
    processor = edp.ExnessDataProcessor()
    assert processor is not None
    # v2.0.0: ClickHouse-only backend, no base_dir
    assert processor.DATABASE == "exness"
    processor.close()
