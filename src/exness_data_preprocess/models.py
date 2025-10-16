"""
Pydantic models for exness-data-preprocess API.

This module defines the data models used throughout the package, following the
industry-standard three-layer pattern:

Layer 1: Type definitions (Literal types for valid values)
Layer 2: Pydantic models (data structures with validation)
Layer 3: Methods (behavior, defined in processor.py)

All models support both attribute access (result.months_added) and dict access
(result['months_added']) for backward compatibility with v2.0.0.

Discovery Methods for AI Agents:
    >>> import exness_data_preprocess as edp
    >>> from exness_data_preprocess.models import UpdateResult
    >>> # Get JSON Schema
    >>> print(UpdateResult.model_json_schema())
    >>> # Get field info
    >>> print(UpdateResult.model_fields)
    >>> # Get valid values for types
    >>> from typing import get_args
    >>> print(get_args(edp.models.PairType))  # All valid pairs

Example:
    >>> from exness_data_preprocess.models import UpdateResult, PairType
    >>> # Valid pairs
    >>> pair: PairType = "EURUSD"  # ✓ Type checker knows this is valid
    >>> # UpdateResult usage
    >>> result = UpdateResult(
    ...     duckdb_path=Path("eurusd.duckdb"),
    ...     months_added=12,
    ...     raw_ticks_added=1000000,
    ...     standard_ticks_added=1000000,
    ...     ohlc_bars=50000,
    ...     duckdb_size_mb=150.5
    ... )
    >>> # Both access patterns work
    >>> print(result.months_added)       # ✓ Attribute access (new)
    >>> print(result['months_added'])    # ✓ Dict access (backward compat)
"""

from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, Field

# ============================================================================
# Layer 1: Type Definitions
# ============================================================================
# These Literal types define all valid values for enums.
# AI agents can discover valid values via:
#   from typing import get_args
#   print(get_args(PairType))  # ('EURUSD', 'GBPUSD', ...)

PairType = Literal[
    "EURUSD",
    "GBPUSD",
    "XAUUSD",
    "USDJPY",
    "AUDUSD",
    "USDCAD",
    "NZDUSD",
    "EURGBP",
    "EURJPY",
    "GBPJPY",
]
"""
Supported currency pairs from Exness tick data repository.

All pairs available at: https://ticks.ex2archive.com/ticks/

To get list of valid pairs programmatically:
    >>> from typing import get_args
    >>> from exness_data_preprocess.models import PairType
    >>> valid_pairs = get_args(PairType)
    >>> print(valid_pairs)  # ('EURUSD', 'GBPUSD', ...)
"""

TimeframeType = Literal["1m", "5m", "15m", "30m", "1h", "4h", "1d"]
"""
Supported OHLC timeframes.

- 1m: Base timeframe (stored in database)
- 5m, 15m, 30m, 1h, 4h, 1d: On-demand resampling (<15ms)

To get list of valid timeframes programmatically:
    >>> from typing import get_args
    >>> from exness_data_preprocess.models import TimeframeType
    >>> valid_timeframes = get_args(TimeframeType)
    >>> print(valid_timeframes)  # ('1m', '5m', '15m', ...)
"""

VariantType = Literal["raw_spread", "standard"]
"""
Exness data variants.

- raw_spread: Raw_Spread variant (~98% zero-spreads, execution prices)
- standard: Standard variant (0% zero-spreads, traditional quotes)

Data sources:
    - Raw_Spread: https://ticks.ex2archive.com/ticks/{PAIR}_Raw_Spread/{YEAR}/{MONTH}/
    - Standard: https://ticks.ex2archive.com/ticks/{PAIR}/{YEAR}/{MONTH}/

To get list of valid variants programmatically:
    >>> from typing import get_args
    >>> from exness_data_preprocess.models import VariantType
    >>> valid_variants = get_args(VariantType)
    >>> print(valid_variants)  # ('raw_spread', 'standard')
"""


# ============================================================================
# Layer 2: Pydantic Models
# ============================================================================


class UpdateResult(BaseModel):
    """
    Result from update_data() operation.

    Returned when downloading and updating an instrument's database with latest
    data from Exness repository.

    Attributes:
        duckdb_path: Absolute path to the DuckDB database file
        months_added: Number of months successfully downloaded (0 if up to date)
        raw_ticks_added: Number of Raw_Spread ticks inserted
        standard_ticks_added: Number of Standard ticks inserted
        ohlc_bars: Total number of 1-minute OHLC bars after update
        duckdb_size_mb: Database file size in megabytes

    Example:
        >>> processor = ExnessDataProcessor()
        >>> result = processor.update_data("EURUSD", start_date="2022-01-01")
        >>> print(f"Added {result.months_added} months")
        >>> print(f"Database: {result.duckdb_size_mb:.2f} MB")
        >>> # Backward compatible dict access also works
        >>> print(result['months_added'])
    """

    duckdb_path: Path = Field(
        description="Absolute path to the DuckDB database file (e.g., ~/eon/exness-data/eurusd.duckdb)"
    )
    months_added: int = Field(
        ge=0,
        description="Number of months successfully downloaded and added to database. Returns 0 if database is up to date.",
    )
    raw_ticks_added: int = Field(
        ge=0,
        description="Number of Raw_Spread ticks inserted into raw_spread_ticks table. May be less than expected if duplicates prevented by PRIMARY KEY.",
    )
    standard_ticks_added: int = Field(
        ge=0,
        description="Number of Standard ticks inserted into standard_ticks table. May be less than expected if duplicates prevented by PRIMARY KEY.",
    )
    ohlc_bars: int = Field(
        ge=0,
        description="Total number of 1-minute OHLC bars in ohlc_1m table after update (not just new bars, but total count).",
    )
    duckdb_size_mb: float = Field(
        ge=0,
        description="Total database file size in megabytes after update. Typical size: ~135 MB/year.",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "duckdb_path": "/Users/user/eon/exness-data/eurusd.duckdb",
                    "months_added": 12,
                    "raw_ticks_added": 18600000,
                    "standard_ticks_added": 19600000,
                    "ohlc_bars": 413000,
                    "duckdb_size_mb": 2080.5,
                }
            ]
        }
    }


class CoverageInfo(BaseModel):
    """
    Database coverage information for an instrument.

    Returned when querying data availability and statistics for an instrument.

    Attributes:
        database_exists: Whether the DuckDB file exists
        duckdb_path: Path to the database file (may not exist)
        duckdb_size_mb: Database file size in MB (0 if not exists)
        raw_spread_ticks: Total number of Raw_Spread ticks
        standard_ticks: Total number of Standard ticks
        ohlc_bars: Total number of 1-minute OHLC bars
        earliest_date: ISO 8601 timestamp of earliest tick (None if empty)
        latest_date: ISO 8601 timestamp of latest tick (None if empty)
        date_range_days: Number of calendar days between earliest and latest

    Example:
        >>> processor = ExnessDataProcessor()
        >>> coverage = processor.get_data_coverage("EURUSD")
        >>> if coverage.database_exists:
        ...     print(f"Coverage: {coverage.earliest_date} to {coverage.latest_date}")
        ...     print(f"Total: {coverage.raw_spread_ticks:,} ticks")
        >>> # Backward compatible dict access also works
        >>> print(coverage['database_exists'])
    """

    database_exists: bool = Field(description="Whether the DuckDB database file exists on disk")
    duckdb_path: str = Field(
        description="Absolute path to the database file (string representation, may not exist)"
    )
    duckdb_size_mb: float = Field(
        ge=0, description="Database file size in megabytes (0 if file doesn't exist)"
    )
    raw_spread_ticks: int = Field(
        ge=0,
        description="Total number of ticks in raw_spread_ticks table (0 if database doesn't exist or is empty)",
    )
    standard_ticks: int = Field(
        ge=0,
        description="Total number of ticks in standard_ticks table (0 if database doesn't exist or is empty)",
    )
    ohlc_bars: int = Field(
        ge=0,
        description="Total number of 1-minute bars in ohlc_1m table (0 if database doesn't exist or is empty)",
    )
    earliest_date: Optional[str] = Field(
        default=None,
        description="ISO 8601 timestamp of earliest tick in raw_spread_ticks (None if no data)",
    )
    latest_date: Optional[str] = Field(
        default=None,
        description="ISO 8601 timestamp of latest tick in raw_spread_ticks (None if no data)",
    )
    date_range_days: int = Field(
        ge=0,
        description="Number of calendar days between earliest_date and latest_date (0 if no data)",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "database_exists": True,
                    "duckdb_path": "/Users/user/eon/exness-data/eurusd.duckdb",
                    "duckdb_size_mb": 2080.5,
                    "raw_spread_ticks": 18600000,
                    "standard_ticks": 19600000,
                    "ohlc_bars": 413000,
                    "earliest_date": "2024-10-01 00:00:00+00:00",
                    "latest_date": "2025-10-31 23:59:59+00:00",
                    "date_range_days": 395,
                }
            ]
        }
    }


# ============================================================================
# Helper Functions
# ============================================================================


def supported_pairs() -> tuple[str, ...]:
    """
    Get list of all supported currency pairs.

    Returns:
        Tuple of supported pair strings

    Example:
        >>> from exness_data_preprocess.models import supported_pairs
        >>> pairs = supported_pairs()
        >>> print(pairs)  # ('EURUSD', 'GBPUSD', ...)
        >>> assert 'EURUSD' in pairs
    """
    from typing import get_args

    return get_args(PairType)


def supported_timeframes() -> tuple[str, ...]:
    """
    Get list of all supported OHLC timeframes.

    Returns:
        Tuple of supported timeframe strings

    Example:
        >>> from exness_data_preprocess.models import supported_timeframes
        >>> timeframes = supported_timeframes()
        >>> print(timeframes)  # ('1m', '5m', '15m', ...)
        >>> assert '1h' in timeframes
    """
    from typing import get_args

    return get_args(TimeframeType)


def supported_variants() -> tuple[str, ...]:
    """
    Get list of all supported data variants.

    Returns:
        Tuple of supported variant strings

    Example:
        >>> from exness_data_preprocess.models import supported_variants
        >>> variants = supported_variants()
        >>> print(variants)  # ('raw_spread', 'standard')
        >>> assert 'raw_spread' in variants
    """
    from typing import get_args

    return get_args(VariantType)
