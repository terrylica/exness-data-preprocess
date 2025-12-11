"""
Pytest configuration and fixtures for exness-data-preprocess tests.

ADR: 2025-12-11-duckdb-removal-clickhouse

End-to-end testing with ClickHouse backend - no mocking.
"""

import shutil
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def temp_dir():
    """Create temporary directory for testing.

    SLO-AV-1: 100% cleanup success.
    SLO-MA-5: 100% cleanup success (no orphaned temp files).
    """
    temp_path = Path(tempfile.mkdtemp())
    yield temp_path
    # Cleanup
    if temp_path.exists():
        shutil.rmtree(temp_path)


@pytest.fixture
def fixtures_dir():
    """Path to test fixtures directory containing real Exness-format ZIP files."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def processor_with_clickhouse():
    """Create ExnessDataProcessor with ClickHouse backend.

    SLO-MA-1: Fixture reusable across test files.
    Requires: ClickHouse running on localhost:8123
    """
    import socket

    # Check if ClickHouse is available
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(("localhost", 8123))
        sock.close()
        if result != 0:
            pytest.skip("ClickHouse not running on localhost:8123")
    except Exception:
        pytest.skip("ClickHouse not available")

    from exness_data_preprocess.processor import ExnessDataProcessor

    processor = ExnessDataProcessor()
    yield processor
    processor.close()


# Legacy fixture aliases for backward compatibility during migration
@pytest.fixture
def processor_with_temp_dir(processor_with_clickhouse):
    """Legacy fixture - now uses ClickHouse backend.

    Kept for backward compatibility with existing tests.
    """
    return processor_with_clickhouse


@pytest.fixture
def processor_with_real_data(processor_with_clickhouse):
    """Legacy fixture - now uses ClickHouse backend.

    Kept for backward compatibility with existing tests.
    """
    return processor_with_clickhouse
