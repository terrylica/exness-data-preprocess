"""
Pytest configuration and fixtures for exness-data-preprocess tests.
"""

import pytest
from pathlib import Path
import tempfile
import shutil
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from datetime import datetime, timezone


@pytest.fixture
def temp_dir():
    """Create temporary directory for testing."""
    temp_path = Path(tempfile.mkdtemp())
    yield temp_path
    # Cleanup
    if temp_path.exists():
        shutil.rmtree(temp_path)


@pytest.fixture
def sample_tick_data():
    """Create sample tick data for testing."""
    # Create 1000 ticks spanning one hour
    # Create timestamps as naive (without timezone) like real Exness CSV data
    timestamps = pd.date_range(
        start='2024-08-01 00:00:00',
        periods=1000,
        freq='3.6s',  # ~1000 ticks per hour
        tz=None  # Naive timestamps like in CSV
    )

    # Simulate realistic EURUSD tick data
    base_bid = 1.08500
    bid_changes = (pd.Series(range(1000)) % 100 - 50) * 0.00001  # Small variations
    bids = base_bid + bid_changes

    # Spread typically 1-2 pips for EURUSD
    spreads = 0.00015 + (pd.Series(range(1000)) % 10) * 0.00001
    asks = bids + spreads

    df = pd.DataFrame({
        'Timestamp': timestamps,
        'Bid': bids,
        'Ask': asks
    })

    return df


@pytest.fixture
def sample_parquet_file(temp_dir, sample_tick_data):
    """Create sample Parquet file for testing."""
    parquet_path = temp_dir / 'test_ticks.parquet'

    # Convert to UTC timezone-aware (like processor does)
    df = sample_tick_data.copy()
    df['Timestamp'] = pd.to_datetime(df['Timestamp'], utc=True)

    table = pa.Table.from_pandas(df)
    pq.write_table(table, parquet_path, compression='zstd', compression_level=22)
    return parquet_path


@pytest.fixture
def mock_exness_zip(temp_dir, sample_tick_data):
    """Create mock Exness ZIP file for testing."""
    import zipfile

    # Create CSV content
    csv_path = temp_dir / 'Exness_EURUSD_Raw_Spread_2024_08.csv'
    sample_tick_data.to_csv(csv_path, index=False)

    # Create ZIP
    zip_path = temp_dir / 'Exness_EURUSD_Raw_Spread_2024_08.zip'
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.write(csv_path, csv_path.name)

    # Cleanup CSV
    csv_path.unlink()

    return zip_path


@pytest.fixture
def processor_with_temp_dir(temp_dir):
    """Create ExnessDataProcessor with temporary directory."""
    from exness_data_preprocess.processor import ExnessDataProcessor
    return ExnessDataProcessor(base_dir=temp_dir)
