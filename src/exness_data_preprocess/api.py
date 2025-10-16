"""
Backward compatibility API for v1.0.0 CLI commands.

This module provides wrapper functions that map v1.0.0 monthly-file API
to v2.0.0 unified single-file architecture.

**SLOs**:
- **Availability**: Raise on errors, no fallbacks
- **Correctness**: Delegate to ExnessDataProcessor, preserve v1.0.0 semantics
- **Observability**: Pass through processor logging
- **Maintainability**: Thin wrappers, no business logic

**Architecture**: Facade pattern wrapping ExnessDataProcessor

**Status**: Compatibility layer for CLI (to be deprecated when CLI is rewritten for v2.0.0)
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from exness_data_preprocess.processor import ExnessDataProcessor


def process_month(
    year: int,
    month: int,
    pair: str = "EURUSD",
    delete_zip: bool = True,
    base_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Process single month of data (v1.0.0 API compatibility).

    Maps to v2.0.0 update_data() with single-month range.

    **SLOs**:
    - Availability: Raise on download/processing errors
    - Correctness: Delegate to processor.update_data()
    - Observability: Relies on processor logging
    - Maintainability: Thin wrapper, no business logic

    Args:
        year: Year to process
        month: Month to process (1-12)
        pair: Currency pair (default: EURUSD)
        delete_zip: Delete ZIP files after processing
        base_dir: Base directory for data storage

    Returns:
        Dict with v1.0.0-compatible keys:
        - tick_count: Total ticks added (raw + standard)
        - parquet_size_mb: 0 (v2.0.0 has no parquet files)
        - duckdb_size_mb: Database size in MB

    Raises:
        Any exception from processor.update_data()
    """
    processor = ExnessDataProcessor(base_dir=base_dir)

    # Construct start_date for single month
    start_date = f"{year}-{month:02d}-01"

    # Call v2.0.0 API
    result = processor.update_data(
        pair=pair,
        start_date=start_date,
        delete_zip=delete_zip,
    )

    # Map to v1.0.0 response format
    return {
        "tick_count": result["raw_ticks_added"] + result["standard_ticks_added"],
        "parquet_size_mb": 0.0,  # v2.0.0 has no parquet files
        "duckdb_size_mb": result["duckdb_size_mb"],
    }


def process_date_range(
    start_year: int,
    start_month: int,
    end_year: int,
    end_month: int,
    pair: str = "EURUSD",
    delete_zip: bool = True,
    base_dir: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """
    Process date range (v1.0.0 API compatibility).

    Maps to v2.0.0 update_data() with single call (incremental update handles range).

    **SLOs**:
    - Availability: Raise on download/processing errors
    - Correctness: Delegate to processor.update_data()
    - Observability: Relies on processor logging
    - Maintainability: Thin wrapper, no business logic

    Args:
        start_year: Start year
        start_month: Start month (1-12)
        end_year: End year
        end_month: End month (1-12)
        pair: Currency pair (default: EURUSD)
        delete_zip: Delete ZIP files after processing
        base_dir: Base directory for data storage

    Returns:
        List of dicts (one entry for compatibility, v2.0.0 does single update):
        - tick_count: Total ticks added
        - parquet_size_mb: 0 (v2.0.0 has no parquet files)
        - duckdb_size_mb: Database size in MB

    Raises:
        Any exception from processor.update_data()
    """
    processor = ExnessDataProcessor(base_dir=base_dir)

    # Construct start_date from range
    start_date = f"{start_year}-{start_month:02d}-01"

    # Call v2.0.0 API (single call handles entire range)
    result = processor.update_data(
        pair=pair,
        start_date=start_date,
        delete_zip=delete_zip,
    )

    # Return as list for v1.0.0 compatibility (even though v2.0.0 does single operation)
    return [
        {
            "tick_count": result["raw_ticks_added"] + result["standard_ticks_added"],
            "parquet_size_mb": 0.0,  # v2.0.0 has no parquet files
            "duckdb_size_mb": result["duckdb_size_mb"],
        }
    ]


def query_ohlc(
    year: int,
    month: int,
    pair: str = "EURUSD",
    timeframe: str = "1m",
    base_dir: Optional[Path] = None,
) -> pd.DataFrame:
    """
    Query OHLC data for single month (v1.0.0 API compatibility).

    Maps to v2.0.0 query_ohlc() with month-based date range.

    **SLOs**:
    - Availability: Raise on query errors
    - Correctness: Delegate to processor.query_ohlc()
    - Observability: Relies on processor logging
    - Maintainability: Thin wrapper, no business logic

    Args:
        year: Year to query
        month: Month to query (1-12)
        pair: Currency pair (default: EURUSD)
        timeframe: Timeframe (1m, 5m, 15m, 30m, 1h, 4h, 1d)
        base_dir: Base directory for data storage

    Returns:
        DataFrame with OHLC data (30-column v1.5.0 schema)

    Raises:
        Any exception from processor.query_ohlc()
    """
    processor = ExnessDataProcessor(base_dir=base_dir)

    # Construct date range for single month
    start_date = f"{year}-{month:02d}-01"

    # Calculate end_date (last day of month)
    import calendar

    last_day = calendar.monthrange(year, month)[1]
    end_date = f"{year}-{month:02d}-{last_day}"

    # Call v2.0.0 API
    return processor.query_ohlc(
        pair=pair,
        timeframe=timeframe,
        start_date=start_date,
        end_date=end_date,
    )


def analyze_ticks(
    year: int,
    month: int,
    pair: str = "EURUSD",
    base_dir: Optional[Path] = None,
) -> pd.DataFrame:
    """
    Analyze tick data for single month (v1.0.0 API compatibility).

    Maps to v2.0.0 query_ticks() with month-based date range.

    **SLOs**:
    - Availability: Raise on query errors
    - Correctness: Delegate to processor.query_ticks()
    - Observability: Relies on processor logging
    - Maintainability: Thin wrapper, no business logic

    Args:
        year: Year to analyze
        month: Month to analyze (1-12)
        pair: Currency pair (default: EURUSD)
        base_dir: Base directory for data storage

    Returns:
        DataFrame with raw_spread tick data (Timestamp, Bid, Ask)

    Raises:
        Any exception from processor.query_ticks()
    """
    processor = ExnessDataProcessor(base_dir=base_dir)

    # Construct date range for single month
    start_date = f"{year}-{month:02d}-01"

    # Calculate end_date (last day of month)
    import calendar

    last_day = calendar.monthrange(year, month)[1]
    end_date = f"{year}-{month:02d}-{last_day}"

    # Call v2.0.0 API (always use raw_spread for analysis)
    return processor.query_ticks(
        pair=pair,
        variant="raw_spread",
        start_date=start_date,
        end_date=end_date,
    )


def get_storage_stats(base_dir: Optional[Path] = None) -> Dict[str, Any]:
    """
    Get storage statistics (v1.0.0 API compatibility).

    Maps to v2.0.0 unified DuckDB architecture (no parquet files).

    **SLOs**:
    - Availability: Raise on filesystem errors
    - Correctness: Accurately report v2.0.0 storage
    - Observability: Direct filesystem inspection
    - Maintainability: Simple file counting, no business logic

    Args:
        base_dir: Base directory for data storage

    Returns:
        Dict with storage statistics:
        - parquet_count: 0 (v2.0.0 has no parquet files)
        - parquet_total_mb: 0.0
        - duckdb_count: Number of .duckdb files
        - duckdb_total_mb: Total size of .duckdb files in MB
        - total_mb: Total storage in MB

    Raises:
        OSError: If base_dir is inaccessible
    """
    if base_dir is None:
        base_dir = Path.home() / "eon" / "exness-data"
    else:
        base_dir = Path(base_dir)

    # Check if base_dir exists
    if not base_dir.exists():
        raise FileNotFoundError(f"Base directory does not exist: {base_dir}")

    # Count DuckDB files (v2.0.0 architecture)
    duckdb_files = list(base_dir.glob("*.duckdb"))
    duckdb_count = len(duckdb_files)
    duckdb_total_mb = sum(f.stat().st_size for f in duckdb_files) / (1024 * 1024)

    # v2.0.0 has no parquet files
    parquet_count = 0
    parquet_total_mb = 0.0

    return {
        "parquet_count": parquet_count,
        "parquet_total_mb": parquet_total_mb,
        "duckdb_count": duckdb_count,
        "duckdb_total_mb": duckdb_total_mb,
        "total_mb": parquet_total_mb + duckdb_total_mb,
    }
