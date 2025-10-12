"""
Exness Data Preprocessing

Professional forex tick data preprocessing with optimal compression and DuckDB OHLC generation.

Features:
- Optimal compression: Parquet with Zstd-22 (9% smaller than ZIP, lossless)
- DuckDB OHLC generation with embedded metadata
- Direct queryability (no decode step needed)
- On-demand tick analysis workflow
- Production-grade atomic operations

Quick Start:
    >>> import exness_data_preprocess as edp
    >>>
    >>> # Download and preprocess Exness data
    >>> processor = edp.ExnessDataProcessor()
    >>> result = processor.process_month(year=2024, month=8)
    >>>
    >>> # Query OHLC data
    >>> df_ohlc = edp.query_ohlc(year=2024, month=8, timeframe='1m')
    >>>
    >>> # On-demand tick analysis
    >>> df_ticks = edp.analyze_ticks(year=2024, month=8)
"""

__version__ = "0.1.0"
__author__ = "Terry Li <terry@eonlabs.com>"
__license__ = "MIT"

from exness_data_preprocess.processor import ExnessDataProcessor
from exness_data_preprocess.api import (
    process_month,
    process_date_range,
    query_ohlc,
    analyze_ticks,
    get_storage_stats,
)

__all__ = [
    # Main class
    "ExnessDataProcessor",
    # Simple API functions
    "process_month",
    "process_date_range",
    "query_ohlc",
    "analyze_ticks",
    "get_storage_stats",
    # Package metadata
    "__version__",
]
