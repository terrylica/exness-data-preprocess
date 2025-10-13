"""
Exness Data Preprocessing (v2.1.0)

Professional forex tick data preprocessing with unified single-file DuckDB storage.

Architecture (v2.0.0+):
- One DuckDB file per instrument (eurusd.duckdb, not monthly files)
- Dual-variant storage (Raw_Spread + Standard) for Phase7 compliance
- Incremental updates with automatic gap detection
- Phase7 9-column OHLC schema with dual spreads and tick counts
- Self-documenting database schema with embedded COMMENT ON statements
- Pydantic models for validated API responses

Features:
- Automatic incremental updates (only downloads missing months)
- Date range queries with SQL filters
- On-demand OHLC resampling (5m, 1h, 1d, etc.) in <15ms
- Type-safe API with Pydantic validation
- AI agent-friendly introspection (JSON Schema, Literal types)

Quick Start:
    >>> import exness_data_preprocess as edp
    >>>
    >>> # Initialize processor
    >>> processor = edp.ExnessDataProcessor()
    >>>
    >>> # Initial 3-year download
    >>> result = processor.update_data("EURUSD", start_date="2022-01-01")
    >>> print(f"Downloaded {result.months_added} months")  # Attribute access
    >>> print(f"Database: {result['duckdb_size_mb']:.2f} MB")  # Dict access (backward compat)
    >>>
    >>> # Incremental update (only new months)
    >>> result = processor.update_data("EURUSD")
    >>>
    >>> # Query OHLC data
    >>> df = processor.query_ohlc("EURUSD", timeframe="1h", start_date="2024-01-01")
    >>>
    >>> # Query tick data
    >>> df_ticks = processor.query_ticks("EURUSD", variant="raw_spread", start_date="2024-09-01")
    >>>
    >>> # Get coverage information
    >>> coverage = processor.get_data_coverage("EURUSD")
    >>> print(f"Coverage: {coverage.earliest_date} to {coverage.latest_date}")

AI Agent Discovery:
    >>> # Get JSON Schema for UpdateResult
    >>> from exness_data_preprocess.models import UpdateResult
    >>> print(UpdateResult.model_json_schema())
    >>>
    >>> # Get valid pairs/timeframes/variants
    >>> from typing import get_args
    >>> from exness_data_preprocess.models import PairType, TimeframeType
    >>> print(get_args(PairType))  # ('EURUSD', 'GBPUSD', ...)
    >>> print(get_args(TimeframeType))  # ('1m', '5m', '15m', ...)
"""

__version__ = "0.1.0"
__author__ = "Terry Li <terry@eonlabs.com>"
__license__ = "MIT"

from exness_data_preprocess.models import (
    CoverageInfo,
    PairType,
    TimeframeType,
    UpdateResult,
    VariantType,
    supported_pairs,
    supported_timeframes,
    supported_variants,
)
from exness_data_preprocess.processor import ExnessDataProcessor

__all__ = [
    # Main class
    "ExnessDataProcessor",
    # Pydantic models
    "UpdateResult",
    "CoverageInfo",
    # Type definitions
    "PairType",
    "TimeframeType",
    "VariantType",
    # Helper functions
    "supported_pairs",
    "supported_timeframes",
    "supported_variants",
    # Package metadata
    "__version__",
]
