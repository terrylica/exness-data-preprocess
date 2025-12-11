"""Basic tests to ensure package can be imported and has correct metadata.

ADR: 2025-12-11-duckdb-removal-clickhouse

Note: test_processor_instantiation requires ClickHouse running on localhost:8123.
"""

import socket

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


def clickhouse_available() -> bool:
    """Check if ClickHouse is running on localhost:8123."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(("localhost", 8123))
        sock.close()
        return result == 0
    except Exception:
        return False


@pytest.mark.skipif(
    not clickhouse_available(),
    reason="ClickHouse not running on localhost:8123",
)
def test_processor_instantiation():
    """Test that ExnessDataProcessor can be instantiated.

    Requires ClickHouse running on localhost:8123.
    """
    processor = edp.ExnessDataProcessor()
    assert processor is not None
    # v2.0.0: ClickHouse-only backend, no base_dir
    assert processor.DATABASE == "exness"
    processor.close()
