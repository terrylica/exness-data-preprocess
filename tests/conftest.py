"""
Pytest configuration and fixtures for exness-data-preprocess tests.

End-to-end testing with real Exness-format data - no mocking.
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
def processor_with_temp_dir(temp_dir):
    """Create ExnessDataProcessor with temporary directory.

    SLO-MA-1: Fixture reusable across test files.
    """
    from exness_data_preprocess.processor import ExnessDataProcessor

    return ExnessDataProcessor(base_dir=temp_dir)


@pytest.fixture
def processor_with_real_data(temp_dir):
    """Create ExnessDataProcessor with true end-to-end data download.

    End-to-end: Downloads real data from https://ticks.ex2archive.com/
    No mocking - downloads actual Exness data and processes it.

    SLO-MA-4: True end-to-end testing from online source.
    """
    from exness_data_preprocess.processor import ExnessDataProcessor

    processor = ExnessDataProcessor(base_dir=temp_dir)
    processor.temp_dir.mkdir(parents=True, exist_ok=True)

    # Download real data from Exness online source
    # Using August 2024 data (more likely to have both variants available)
    try:
        raw_spread_zip = processor.download_exness_zip(
            pair="EURUSD", variant="Raw_Spread", year=2024, month=8
        )
        if raw_spread_zip is None or not raw_spread_zip.exists():
            pytest.skip("Could not download Exness Raw_Spread data: download returned None")

        # Try to download Standard variant, but don't fail if not available
        standard_zip = processor.download_exness_zip(
            pair="EURUSD",
            variant="",  # Empty string for Standard variant
            year=2024,
            month=8,
        )
        # Check if download actually succeeded
        if standard_zip is not None and standard_zip.exists():
            processor.has_standard_data = True
        else:
            processor.has_standard_data = False
    except Exception as e:
        pytest.skip(f"Could not download Exness Raw_Spread data: {e}")

    return processor
