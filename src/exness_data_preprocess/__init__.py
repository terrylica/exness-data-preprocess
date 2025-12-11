"""
Exness Data Preprocessing (v2.0.0)

Professional forex tick data preprocessing with ClickHouse backend.

ADR: /docs/adr/2025-12-11-duckdb-removal-clickhouse.md

BREAKING CHANGES (v2.0.0):
- Renamed: duckdb_path → database (str, ClickHouse database name)
- Renamed: duckdb_size_mb → storage_bytes (int, bytes not MB)
- Removed: database_exists field (ClickHouse is always available)
- Backend: ClickHouse is now the only supported backend (DuckDB removed)

Architecture (v2.0.0):
- ClickHouse backend: Single-table design with instrument column
- Dual-variant storage (Raw_Spread + Standard)
- Incremental updates with automatic gap detection
- 26-column OHLC schema with dual spreads, tick counts, timezone/session tracking,
  holiday tracking, and 10 global exchange sessions with trading hour detection
- Self-documenting database schema with embedded COMMENT statements
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
    >>> # Initialize processor (requires ClickHouse running)
    >>> processor = edp.ExnessDataProcessor()
    >>>
    >>> # Initial 3-year download
    >>> result = processor.update_data("EURUSD", start_date="2022-01-01")
    >>> print(f"Downloaded {result.months_added} months")  # Attribute access
    >>> print(f"Storage: {result.storage_bytes / 1024 / 1024:.2f} MB")
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

__version__ = "1.2.1"
__author__ = "Terry Li <terry@eonlabs.com>"
__license__ = "MIT"

# ClickHouse exports (v2.0.0 - sole backend)
from exness_data_preprocess.clickhouse_client import (
    ClickHouseConnectionError,
    ClickHouseQueryError,
)
from exness_data_preprocess.clickhouse_client import (
    get_client as get_clickhouse_client,
)
from exness_data_preprocess.clickhouse_gap_detector import ClickHouseGapDetector
from exness_data_preprocess.clickhouse_manager import ClickHouseManager
from exness_data_preprocess.clickhouse_ohlc_generator import ClickHouseOHLCGenerator
from exness_data_preprocess.clickhouse_query_engine import ClickHouseQueryEngine
from exness_data_preprocess.models import (
    CoverageInfo,
    CursorResult,
    DryRunResult,
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
    # Main class (ClickHouse backend)
    "ExnessDataProcessor",
    # Pydantic models
    "UpdateResult",
    "CoverageInfo",
    "CursorResult",
    "DryRunResult",
    # Type definitions
    "PairType",
    "TimeframeType",
    "VariantType",
    # Helper functions
    "supported_pairs",
    "supported_timeframes",
    "supported_variants",
    # ClickHouse modules
    "ClickHouseManager",
    "ClickHouseGapDetector",
    "ClickHouseQueryEngine",
    "ClickHouseOHLCGenerator",
    "ClickHouseConnectionError",
    "ClickHouseQueryError",
    "get_clickhouse_client",
    # Package metadata
    "__version__",
]
