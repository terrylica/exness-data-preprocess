"""
Pydantic models for exness-data-preprocess API.

ADR: 2025-12-11-duckdb-removal-clickhouse

BREAKING CHANGES (v2.0.0):
- Renamed: duckdb_path → database (str, ClickHouse database name)
- Renamed: duckdb_size_mb → storage_bytes (int, bytes not MB)
- Removed: database_exists field (ClickHouse is always available)
- Backend: ClickHouse is now the only supported backend

This module defines the data models used throughout the package, following the
industry-standard three-layer pattern:

Layer 1: Type definitions (Literal types for valid values)
Layer 2: Pydantic models (data structures with validation)
Layer 3: Methods (behavior, defined in processor.py)

All models support both attribute access (result.months_added) and dict access
(result['months_added']) for backward compatibility.

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
    ...     database="exness",
    ...     months_added=12,
    ...     raw_ticks_added=1000000,
    ...     standard_ticks_added=1000000,
    ...     ohlc_bars=50000,
    ...     storage_bytes=2181038080
    ... )
    >>> # Both access patterns work
    >>> print(result.months_added)       # ✓ Attribute access (new)
    >>> print(result['months_added'])    # ✓ Dict access (backward compat)
"""

from typing import Literal, Optional

from pydantic import BaseModel, Field, computed_field

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

    Returned when downloading and updating an instrument's data in ClickHouse.

    Attributes:
        database: ClickHouse database name (e.g., 'exness')
        months_added: Number of months successfully downloaded (0 if up to date)
        raw_ticks_added: Number of Raw_Spread ticks inserted
        standard_ticks_added: Number of Standard ticks inserted
        ohlc_bars: Total number of 1-minute OHLC bars after update
        storage_bytes: Total storage in bytes (from system.tables)

    Example:
        >>> processor = ExnessDataProcessor()
        >>> result = processor.update_data("EURUSD", start_date="2022-01-01")
        >>> print(f"Added {result.months_added} months")
        >>> print(f"Storage: {result.storage_bytes / 1024 / 1024:.2f} MB")
        >>> # Backward compatible dict access also works
        >>> print(result['months_added'])
    """

    database: str = Field(description="ClickHouse database name (e.g., 'exness')")
    months_added: int = Field(
        ge=0,
        description="Number of months successfully downloaded and added to database. Returns 0 if database is up to date.",
    )
    raw_ticks_added: int = Field(
        ge=0,
        description="Number of Raw_Spread ticks inserted into ticks table. May be less than expected if duplicates deduplicated by ReplacingMergeTree.",
    )
    standard_ticks_added: int = Field(
        ge=0,
        description="Number of Standard ticks inserted into ticks table. May be less than expected if duplicates deduplicated by ReplacingMergeTree.",
    )
    ohlc_bars: int = Field(
        ge=0,
        description="Total number of 1-minute OHLC bars in ohlc_1m table after update (not just new bars, but total count).",
    )
    storage_bytes: int = Field(
        default=0,
        ge=0,
        description="Total storage in bytes from system.tables (sum of data_compressed_bytes).",
    )

    @computed_field  # type: ignore[misc]
    @property
    def avg_ticks_per_month(self) -> float:
        """
        Average ticks added per month.

        Returns:
            Average number of ticks (Raw_Spread + Standard) per month downloaded.
            Returns 0.0 if no months were added.

        Example:
            >>> result = UpdateResult(...)
            >>> print(f"Avg ticks/month: {result.avg_ticks_per_month:,.0f}")
        """
        if self.months_added == 0:
            return 0.0
        total_ticks = self.raw_ticks_added + self.standard_ticks_added
        return total_ticks / self.months_added

    @computed_field  # type: ignore[misc]
    @property
    def storage_efficiency_mb_per_million_ticks(self) -> float:
        """
        Storage efficiency: MB per million ticks.

        Returns:
            Database size per million total ticks (Raw_Spread + Standard).
            Returns 0.0 if no ticks exist.

        Example:
            >>> result = UpdateResult(...)
            >>> print(f"Efficiency: {result.storage_efficiency_mb_per_million_ticks:.2f} MB/M ticks")
        """
        total_ticks = self.raw_ticks_added + self.standard_ticks_added
        if total_ticks == 0:
            return 0.0
        storage_mb = self.storage_bytes / (1024 * 1024)
        return (storage_mb / total_ticks) * 1_000_000

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "database": "exness",
                    "months_added": 12,
                    "raw_ticks_added": 18600000,
                    "standard_ticks_added": 19600000,
                    "ohlc_bars": 413000,
                    "storage_bytes": 2181038080,
                }
            ]
        }
    }


class CoverageInfo(BaseModel):
    """
    Database coverage information for an instrument.

    Returned when querying data availability and statistics for an instrument
    from ClickHouse.

    Attributes:
        database: ClickHouse database name (e.g., 'exness')
        storage_bytes: Total storage in bytes (from system.tables)
        raw_spread_ticks: Total number of Raw_Spread ticks
        standard_ticks: Total number of Standard ticks
        ohlc_bars: Total number of 1-minute OHLC bars
        earliest_date: ISO 8601 timestamp of earliest tick (None if empty)
        latest_date: ISO 8601 timestamp of latest tick (None if empty)
        date_range_days: Number of calendar days between earliest and latest

    Example:
        >>> processor = ExnessDataProcessor()
        >>> coverage = processor.get_data_coverage("EURUSD")
        >>> print(f"Coverage: {coverage.earliest_date} to {coverage.latest_date}")
        >>> print(f"Total: {coverage.raw_spread_ticks:,} ticks")
        >>> # Backward compatible dict access also works
        >>> print(coverage['database'])
    """

    database: str = Field(description="ClickHouse database name (e.g., 'exness')")
    storage_bytes: int = Field(
        default=0,
        ge=0,
        description="Total storage in bytes from system.tables (0 if no data)",
    )
    raw_spread_ticks: int = Field(
        ge=0,
        description="Total number of raw_spread ticks in ticks table (0 if empty)",
    )
    standard_ticks: int = Field(
        ge=0,
        description="Total number of standard ticks in ticks table (0 if empty)",
    )
    ohlc_bars: int = Field(
        ge=0,
        description="Total number of 1-minute bars in ohlc_1m table (0 if empty)",
    )
    earliest_date: Optional[str] = Field(
        default=None,
        pattern=r"^\d{4}-\d{2}-\d{2}",
        description="ISO 8601 timestamp of earliest tick (None if no data). Format: YYYY-MM-DD HH:MM:SS+TZ",
    )
    latest_date: Optional[str] = Field(
        default=None,
        pattern=r"^\d{4}-\d{2}-\d{2}",
        description="ISO 8601 timestamp of latest tick (None if no data). Format: YYYY-MM-DD HH:MM:SS+TZ",
    )
    date_range_days: int = Field(
        ge=0,
        description="Number of calendar days between earliest_date and latest_date (0 if no data)",
    )

    @computed_field  # type: ignore[misc]
    @property
    def total_ticks(self) -> int:
        """
        Total number of ticks across both variants.

        Returns:
            Sum of raw_spread_ticks + standard_ticks

        Example:
            >>> coverage = CoverageInfo(...)
            >>> print(f"Total ticks: {coverage.total_ticks:,}")
        """
        return self.raw_spread_ticks + self.standard_ticks

    @computed_field  # type: ignore[misc]
    @property
    def coverage_percentage(self) -> float:
        """
        Percentage of expected trading days with data.

        Estimates coverage by comparing date_range_days to expected trading days
        (approximately 252 trading days per year = 69% of calendar days).

        Returns:
            Percentage of expected trading days covered (0-100+).
            Returns 0.0 if no data.

        Note:
            Values >100% indicate full coverage including weekends/holidays.
            Values <100% indicate gaps in trading day coverage.

        Example:
            >>> coverage = CoverageInfo(...)
            >>> print(f"Coverage: {coverage.coverage_percentage:.1f}%")
        """
        if self.date_range_days == 0:
            return 0.0

        # Approximate expected trading days: 252 per year = 0.69 ratio
        expected_trading_days = self.date_range_days * 0.69
        actual_coverage = self.date_range_days  # We have data for these days

        return (actual_coverage / expected_trading_days) * 100 if expected_trading_days > 0 else 0.0

    @computed_field  # type: ignore[misc]
    @property
    def storage_efficiency_mb_per_million_ticks(self) -> float:
        """
        Storage efficiency: MB per million ticks.

        Returns:
            Database size per million total ticks.
            Returns 0.0 if no ticks exist.

        Example:
            >>> coverage = CoverageInfo(...)
            >>> print(f"Efficiency: {coverage.storage_efficiency_mb_per_million_ticks:.2f} MB/M ticks")
        """
        total = self.total_ticks
        if total == 0:
            return 0.0
        storage_mb = self.storage_bytes / (1024 * 1024)
        return (storage_mb / total) * 1_000_000

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "database": "exness",
                    "storage_bytes": 2181038080,
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


class CursorResult(BaseModel):
    """
    Result from cursor-based pagination query.

    ADR: /docs/adr/2025-12-10-clickhouse-e2e-validation-pipeline.md

    Used for memory-efficient pagination through large tick datasets.
    The cursor is an ISO 8601 timestamp marking the last row returned.

    Attributes:
        data: DataFrame containing the current page of results
        next_cursor: ISO 8601 timestamp for the next page (None if no more data)
        has_more: Whether more data is available after this page
        page_size: Number of rows requested per page

    Example:
        >>> engine = ClickHouseQueryEngine()
        >>> result = engine.query_ticks_paginated("EURUSD", page_size=10000)
        >>> while result.has_more:
        ...     process(result.data)
        ...     result = engine.query_ticks_paginated("EURUSD", cursor=result.next_cursor)
    """

    data: object = Field(
        description="DataFrame containing the current page of results (pd.DataFrame)"
    )
    next_cursor: Optional[str] = Field(
        default=None, description="ISO 8601 timestamp to pass for next page (None if no more data)"
    )
    has_more: bool = Field(description="Whether more data is available after this page")
    page_size: int = Field(ge=1, description="Number of rows requested per page")

    model_config = {
        "arbitrary_types_allowed": True,  # Allow pd.DataFrame
        "json_schema_extra": {
            "examples": [
                {
                    "data": "<DataFrame with 10000 rows>",
                    "next_cursor": "2024-08-01 12:30:45.123456+00:00",
                    "has_more": True,
                    "page_size": 10000,
                }
            ]
        },
    }


class DryRunResult(BaseModel):
    """
    Result from dry-run mode (preview without executing).

    Returned when calling update_data() with dry_run=True to estimate
    download operations without modifying the file system.

    Attributes:
        would_download_months: Number of months that would be downloaded
        estimated_raw_ticks: Estimated Raw_Spread ticks (~9.5M per month)
        estimated_standard_ticks: Estimated Standard ticks (~9.5M per month)
        estimated_size_mb: Estimated database size increase (~11 MB per month)
        gap_months: List of YYYY-MM month strings that would be downloaded

    Example:
        >>> processor = ExnessDataProcessor()
        >>> result = processor.update_data("EURUSD", start_date="2024-01-01", dry_run=True)
        >>> print(f"Would download {result.would_download_months} months")
        >>> print(f"Estimated size: {result.estimated_size_mb:.1f} MB")
        >>> print(f"Months: {', '.join(result.gap_months)}")
    """

    would_download_months: int = Field(
        ge=0, description="Number of months that would be downloaded (0 if up to date)"
    )
    estimated_raw_ticks: int = Field(
        ge=0,
        description="Estimated Raw_Spread ticks based on historical average (~9.5M per month for EURUSD)",
    )
    estimated_standard_ticks: int = Field(
        ge=0,
        description="Estimated Standard ticks based on historical average (~9.5M per month for EURUSD)",
    )
    estimated_size_mb: float = Field(
        ge=0,
        description="Estimated database size increase in megabytes (~11 MB per month for EURUSD)",
    )
    gap_months: list[str] = Field(
        default_factory=list,
        description="List of YYYY-MM month strings that would be downloaded, in chronological order",
    )

    @computed_field  # type: ignore[misc]
    @property
    def estimated_total_ticks(self) -> int:
        """
        Total estimated ticks (Raw_Spread + Standard).

        Returns:
            Sum of estimated_raw_ticks + estimated_standard_ticks

        Example:
            >>> result = DryRunResult(...)
            >>> print(f"Total: {result.estimated_total_ticks:,} ticks")
        """
        return self.estimated_raw_ticks + self.estimated_standard_ticks

    @computed_field  # type: ignore[misc]
    @property
    def avg_ticks_per_month(self) -> float:
        """
        Average estimated ticks per month.

        Returns:
            Average number of ticks per month (0.0 if no months)

        Example:
            >>> result = DryRunResult(...)
            >>> print(f"Avg: {result.avg_ticks_per_month:,.0f} ticks/month")
        """
        if self.would_download_months == 0:
            return 0.0
        return self.estimated_total_ticks / self.would_download_months

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "would_download_months": 3,
                    "estimated_raw_ticks": 28500000,
                    "estimated_standard_ticks": 28500000,
                    "estimated_size_mb": 33.0,
                    "gap_months": ["2024-01", "2024-02", "2024-03"],
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
