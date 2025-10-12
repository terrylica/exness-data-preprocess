"""
Simple API for Exness data preprocessing.

This module provides function-based wrappers around ExnessDataProcessor
for common use cases.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from exness_data_preprocess.processor import ExnessDataProcessor

# Global processor instance (lazy initialization)
_processor = None


def _get_processor(base_dir: Optional[Path] = None) -> ExnessDataProcessor:
    """Get or create global processor instance."""
    global _processor
    if _processor is None or base_dir is not None:
        _processor = ExnessDataProcessor(base_dir=base_dir)
    return _processor


def process_month(
    year: int,
    month: int,
    pair: str = "EURUSD",
    delete_zip: bool = True,
    base_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Process one month of Exness forex tick data.

    This is the primary API for downloading and preprocessing Exness data.
    Downloads monthly ZIP, converts to Parquet (Zstd-22), generates DuckDB OHLC.

    Args:
        year: Year (e.g., 2024)
        month: Month (1-12)
        pair: Currency pair (default: EURUSD)
        delete_zip: Whether to delete ZIP after processing (default: True)
        base_dir: Base directory for data storage (default: ~/eon/exness-data-preprocess/data)

    Returns:
        Dictionary with processing results:
            - parquet_path: Path to Parquet file
            - duckdb_path: Path to DuckDB file
            - tick_count: Number of ticks
            - ohlc_bar_count: Number of 1-minute bars
            - parquet_size_mb: Parquet file size in MB
            - duckdb_size_mb: DuckDB file size in MB
            - compression_ratio: Parquet size / ZIP size

    Example:
        >>> import exness_data_preprocess as edp
        >>> result = edp.process_month(2024, 8)
        >>> print(f"Processed {result['tick_count']:,} ticks")
        >>> print(f"Storage: {result['parquet_size_mb']:.2f} MB")
    """
    processor = _get_processor(base_dir)
    return processor.process_month(year, month, pair, delete_zip)


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
    Process multiple months of Exness data.

    Downloads and processes all months in the specified range.

    Args:
        start_year: Start year
        start_month: Start month (1-12)
        end_year: End year
        end_month: End month (1-12)
        pair: Currency pair (default: EURUSD)
        delete_zip: Whether to delete ZIPs after processing
        base_dir: Base directory for data storage

    Returns:
        List of result dictionaries (one per month)

    Example:
        >>> import exness_data_preprocess as edp
        >>> results = edp.process_date_range(2024, 1, 2024, 12)
        >>> total_ticks = sum(r['tick_count'] for r in results)
        >>> print(f"Processed {total_ticks:,} ticks across {len(results)} months")
    """
    processor = _get_processor(base_dir)
    results = []

    # Generate month sequence
    current_year = start_year
    current_month = start_month

    while (current_year < end_year) or (current_year == end_year and current_month <= end_month):
        try:
            result = processor.process_month(current_year, current_month, pair, delete_zip)
            results.append(result)
        except Exception as e:
            print(f"✗ Failed to process {current_year}-{current_month:02d}: {e}")

        # Move to next month
        if current_month == 12:
            current_month = 1
            current_year += 1
        else:
            current_month += 1

    return results


def query_ohlc(
    year: int,
    month: int,
    pair: str = "EURUSD",
    timeframe: str = "1m",
    base_dir: Optional[Path] = None,
) -> pd.DataFrame:
    """
    Query OHLC data from DuckDB.

    Loads pre-computed OHLC data from DuckDB storage. Supports resampling
    to higher timeframes on the fly.

    Args:
        year: Year
        month: Month (1-12)
        pair: Currency pair (default: EURUSD)
        timeframe: Timeframe (1m, 5m, 15m, 30m, 1h, 4h, 1d)
        base_dir: Base directory for data storage

    Returns:
        DataFrame with OHLC data (Timestamp, Open, High, Low, Close, spread_avg, tick_count)

    Example:
        >>> import exness_data_preprocess as edp
        >>> # Query 1-hour OHLC bars
        >>> df = edp.query_ohlc(2024, 8, timeframe='1h')
        >>> print(df.head())
        >>> print(f"Average spread: {df['spread_avg'].mean():.5f}")
    """
    processor = _get_processor(base_dir)
    return processor.query_ohlc(year, month, pair, timeframe)


def analyze_ticks(
    year: int,
    month: int,
    pair: str = "EURUSD",
    base_dir: Optional[Path] = None,
) -> pd.DataFrame:
    """
    Load tick data for analysis.

    Provides on-demand access to raw tick data from Parquet storage.
    Useful for microstructure analysis, spread statistics, etc.

    Args:
        year: Year
        month: Month (1-12)
        pair: Currency pair (default: EURUSD)
        base_dir: Base directory for data storage

    Returns:
        DataFrame with tick data (Timestamp, Bid, Ask)

    Example:
        >>> import exness_data_preprocess as edp
        >>> df_ticks = edp.analyze_ticks(2024, 8)
        >>> # Calculate spread statistics
        >>> spreads = df_ticks['Ask'] - df_ticks['Bid']
        >>> print(f"Mean spread: {spreads.mean():.5f}")
        >>> print(f"Median spread: {spreads.median():.5f}")
        >>> print(f"95th percentile: {spreads.quantile(0.95):.5f}")
    """
    processor = _get_processor(base_dir)
    return processor.analyze_ticks(year, month, pair)


def get_storage_stats(base_dir: Optional[Path] = None) -> Dict[str, Any]:
    """
    Get storage statistics for all processed data.

    Returns counts and total sizes for Parquet and DuckDB files.

    Args:
        base_dir: Base directory for data storage

    Returns:
        Dictionary with storage stats:
            - parquet_count: Number of Parquet files
            - parquet_total_mb: Total Parquet storage (MB)
            - duckdb_count: Number of DuckDB files
            - duckdb_total_mb: Total DuckDB storage (MB)
            - total_mb: Total storage (MB)

    Example:
        >>> import exness_data_preprocess as edp
        >>> stats = edp.get_storage_stats()
        >>> print(f"Total storage: {stats['total_mb']:.2f} MB")
        >>> print(f"Parquet files: {stats['parquet_count']}")
        >>> print(f"DuckDB files: {stats['duckdb_count']}")
    """
    processor = _get_processor(base_dir)
    return processor.get_storage_stats()
