# Pydantic Refactoring Plan - Deep Dive Analysis

**Version**: 2.1.0 (Minor - Backward Compatible)
**Status**: Pre-Implementation Analysis
**Date**: 2025-01-12
**Objective**: Migrate to Pydantic-based API documentation pattern with maximum impact and minimal regressions

---

## Executive Summary

**Goal**: Refactor exness-data-preprocess v2.0.0 to use Pydantic v2 models + rich docstrings as single source of truth for API documentation, validation, and AI agent discovery.

**Impact**: High - Enables AI agents to discover API structure, adds runtime validation, generates JSON schemas automatically, eliminates documentation fragmentation.

**Regression Risk**: Low - Pydantic models are dict-compatible, so existing code continues to work. Breaking changes limited to api.py deprecation.

**Timeline**: 3-4 hours of implementation + 2 hours testing

---

## Current State Analysis

### API Surface (v2.0.0)

**Main Class**: `ExnessDataProcessor`

**Public Methods**:
1. `__init__(base_dir: Path = None)` - No return
2. `download_exness_zip(year, month, pair, variant)` → `Optional[Path]`
3. `update_data(pair, start_date, force_redownload, delete_zip)` → `Dict[str, Any]` ⚠️
4. `query_ticks(pair, variant, start_date, end_date, filter_sql)` → `pd.DataFrame`
5. `query_ohlc(pair, timeframe, start_date, end_date)` → `pd.DataFrame`
6. `add_schema_comments(pair)` → `bool`
7. `add_schema_comments_all()` → `Dict[str, bool]`
8. `get_data_coverage(pair)` → `Dict[str, Any]` ⚠️

**Legacy API (api.py)**: ❌ BROKEN - References non-existent methods
- `process_month()` - calls `processor.process_month()` which doesn't exist!
- `process_date_range()` - calls `processor.process_month()` which doesn't exist!
- `query_ohlc()` - signature doesn't match processor.query_ohlc()
- `analyze_ticks()` - calls `processor.analyze_ticks()` which doesn't exist!
- `get_storage_stats()` - calls `processor.get_storage_stats()` which doesn't exist!

**Exports (__init__.py)**: Exports broken api.py functions

### Issues Identified

#### Critical Issues
1. **api.py is completely broken** - All functions call non-existent methods
2. **__init__.py docstring outdated** - Shows v1.0.0 API (process_month)
3. **No type safety** - Dict[str, Any] return types hide structure
4. **No validation** - Can return arbitrary dict keys/values

#### High-Priority Issues
5. **AI agents can't discover API** - Untyped dicts, no JSON Schema
6. **No enum types** - pair/timeframe/variant are strings, not Literal
7. **Missing validation helpers** - No supported_pairs() method

#### Medium-Priority Issues
8. **Docstrings lack structure** - No consistent Args/Returns/Examples
9. **No embedded examples** - Can't show AI agents usage patterns
10. **query_ticks returns DataFrame** - Good, but should document schema

---

## Impact Analysis

### Changes Required

#### Breaking Changes (None - Maintain Backward Compatibility)
- ❌ None - All changes are additive or compatible

#### Non-Breaking Changes (High Impact)
1. **Add Pydantic models** for return types
2. **Add Literal types** for enums
3. **Update method signatures** with typed parameters
4. **Deprecate api.py** with warnings
5. **Update __init__.py** docstring
6. **Add validation helpers**
7. **Enhance docstrings** with structured format

### Backward Compatibility Strategy

**Pydantic models are dict-compatible**:
```python
# Old code (v2.0.0)
result = processor.update_data("EURUSD", "2022-01-01")
print(result['months_added'])  # ✅ Still works

# New code (v2.1.0)
result = processor.update_data("EURUSD", "2022-01-01")
print(result.months_added)  # ✅ Also works (attribute access)
print(result['months_added'])  # ✅ Still works (dict access)
```

**Key insight**: Pydantic BaseModel implements `__getitem__`, so existing code using dict access continues to work!

---

## Detailed Refactoring Plan

### Phase 1: Foundation (1 hour)

#### 1.1 Create `models.py` (New File)

**Location**: `/Users/terryli/eon/exness-data-preprocess/src/exness_data_preprocess/models.py`

**Contents**:
```python
"""
Pydantic models for exness-data-preprocess v2.1.0.

Single source of truth for:
- Data contracts (what data looks like)
- Validation rules (constraints on values)
- JSON Schema (for AI agents and APIs)
- Type hints (for IDEs and type checkers)
"""

from typing import Literal, Optional
from pathlib import Path
from pydantic import BaseModel, Field

# ============================================================================
# TYPE DEFINITIONS - Valid values defined once
# ============================================================================

PairType = Literal["EURUSD", "GBPUSD", "XAUUSD", "USDJPY", "AUDUSD"]
TimeframeType = Literal["1m", "5m", "15m", "1h", "4h", "1d"]
VariantType = Literal["raw_spread", "standard"]

# ============================================================================
# RESULT MODELS - Machine-readable return structures
# ============================================================================

class UpdateResult(BaseModel):
    """
    Result from update_data() operation.

    This structure is returned after downloading and updating forex data.
    All fields are guaranteed to be present and validated.
    """

    duckdb_path: Path = Field(
        description="Absolute path to the DuckDB database file (e.g., ~/eon/exness-data/eurusd.duckdb)"
    )
    months_added: int = Field(
        ge=0,
        description="Number of new months downloaded and added to database (0 if already up to date)"
    )
    raw_ticks_added: int = Field(
        ge=0,
        description="Number of Raw_Spread variant ticks added (execution prices, ~98% zero-spreads)"
    )
    standard_ticks_added: int = Field(
        ge=0,
        description="Number of Standard variant ticks added (market prices, 0% zero-spreads)"
    )
    ohlc_bars: int = Field(
        ge=0,
        description="Total 1-minute OHLC bars in database (Phase7 9-column schema)"
    )
    duckdb_size_mb: float = Field(
        ge=0,
        description="Current database file size in megabytes"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [{
                "duckdb_path": "/home/user/eon/exness-data/eurusd.duckdb",
                "months_added": 13,
                "raw_ticks_added": 18600000,
                "standard_ticks_added": 19600000,
                "ohlc_bars": 413000,
                "duckdb_size_mb": 2080.0
            }]
        }
    }


class CoverageInfo(BaseModel):
    """
    Database coverage statistics and metadata.

    Returned by get_data_coverage() to show what data is available
    for an instrument.
    """

    database_exists: bool = Field(
        description="Whether the database file exists on disk"
    )
    duckdb_path: str = Field(
        description="Absolute path to database file"
    )
    duckdb_size_mb: float = Field(
        ge=0,
        description="Database file size in megabytes"
    )
    raw_spread_ticks: int = Field(
        ge=0,
        description="Total Raw_Spread ticks in database"
    )
    standard_ticks: int = Field(
        ge=0,
        description="Total Standard ticks in database"
    )
    ohlc_bars: int = Field(
        ge=0,
        description="Total 1-minute OHLC bars in database"
    )
    earliest_date: Optional[str] = Field(
        default=None,
        description="Earliest tick timestamp in database (ISO 8601 format)"
    )
    latest_date: Optional[str] = Field(
        default=None,
        description="Latest tick timestamp in database (ISO 8601 format)"
    )
    date_range_days: int = Field(
        ge=0,
        description="Number of days between earliest and latest ticks"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [{
                "database_exists": True,
                "duckdb_path": "/home/user/eon/exness-data/eurusd.duckdb",
                "duckdb_size_mb": 2080.0,
                "raw_spread_ticks": 18600000,
                "standard_ticks": 19600000,
                "ohlc_bars": 413000,
                "earliest_date": "2024-10-01 00:00:00+00:00",
                "latest_date": "2025-10-12 23:59:59+00:00",
                "date_range_days": 377
            }]
        }
    }
```

**Benefits**:
- ✅ Single source of truth for all return types
- ✅ Validation rules embedded (ge=0 for counts)
- ✅ Field descriptions for AI agents
- ✅ Examples embedded in schema
- ✅ JSON Schema auto-generated

#### 1.2 Update `processor.py` Imports

**Add at top**:
```python
from exness_data_preprocess.models import (
    UpdateResult,
    CoverageInfo,
    PairType,
    TimeframeType,
    VariantType,
)
```

#### 1.3 Add Validation Helpers to `ExnessDataProcessor`

**Add static methods**:
```python
@staticmethod
def supported_pairs() -> list[PairType]:
    """
    Return list of supported currency pairs.

    Returns:
        List of supported currency pair symbols

    Example:
        >>> pairs = ExnessDataProcessor.supported_pairs()
        >>> print(pairs)
        ['EURUSD', 'GBPUSD', 'XAUUSD', 'USDJPY', 'AUDUSD']
    """
    return ["EURUSD", "GBPUSD", "XAUUSD", "USDJPY", "AUDUSD"]

@staticmethod
def supported_timeframes() -> list[TimeframeType]:
    """
    Return list of supported OHLC timeframes.

    Returns:
        List of supported timeframe strings

    Example:
        >>> timeframes = ExnessDataProcessor.supported_timeframes()
        >>> print(timeframes)
        ['1m', '5m', '15m', '1h', '4h', '1d']
    """
    return ["1m", "5m", "15m", "1h", "4h", "1d"]

@staticmethod
def supported_variants() -> list[VariantType]:
    """
    Return list of supported data variants.

    Returns:
        List of supported variant names

    Example:
        >>> variants = ExnessDataProcessor.supported_variants()
        >>> print(variants)
        ['raw_spread', 'standard']
    """
    return ["raw_spread", "standard"]
```

---

### Phase 2: Update Method Signatures (1.5 hours)

#### 2.1 Update `update_data()` Method

**Current signature**:
```python
def update_data(
    self,
    pair: str = "EURUSD",
    start_date: str = "2022-01-01",
    force_redownload: bool = False,
    delete_zip: bool = True,
) -> Dict[str, Any]:
```

**New signature**:
```python
def update_data(
    self,
    pair: PairType = "EURUSD",
    start_date: str = "2022-01-01",
    force_redownload: bool = False,
    delete_zip: bool = True,
) -> UpdateResult:
    """
    Download and update forex data incrementally.

    This method automatically detects which months are missing from the database
    and downloads only the necessary data. If the database is up to date, it
    returns immediately with months_added=0.

    The method performs these steps:
    1. Discover missing months between start_date and current month
    2. Download missing months from ticks.ex2archive.com (both variants)
    3. Insert ticks into DuckDB with PRIMARY KEY duplicate prevention
    4. Regenerate Phase7 9-column OHLC with dual spreads
    5. Update metadata table with coverage statistics

    Args:
        pair: Currency pair (EURUSD, GBPUSD, XAUUSD, USDJPY, AUDUSD)
        start_date: Start date in YYYY-MM-DD format (e.g., "2022-01-01")
        force_redownload: If True, re-download existing months (default: False)
        delete_zip: If True, delete ZIP files after extraction (default: True)

    Returns:
        UpdateResult with paths, counts, and statistics. See UpdateResult model
        for complete field descriptions and validation rules.

    Raises:
        ValueError: If start_date format is invalid
        URLError: If download from Exness repository fails
        DatabaseError: If DuckDB operations fail

    Example - Initial 3-year download:
        >>> processor = ExnessDataProcessor()
        >>> result = processor.update_data("EURUSD", start_date="2022-01-01")
        >>> print(f"Downloaded {result.months_added} months")
        >>> print(f"Database size: {result.duckdb_size_mb:.2f} MB")

    Example - Incremental update (downloads only new data):
        >>> result = processor.update_data("EURUSD", start_date="2022-01-01")
        >>> print(f"New months: {result.months_added}")  # 0 if up to date

    Example - Force re-download of all data:
        >>> result = processor.update_data(
        ...     "EURUSD",
        ...     start_date="2022-01-01",
        ...     force_redownload=True
        ... )

    Note:
        - Requires internet connection to download from ticks.ex2archive.com
        - Downloads both Raw_Spread and Standard variants (Phase7 requirement)
        - Uses PRIMARY KEY constraints to prevent duplicate data
        - Typical download speed: ~2-5 MB/s per month
        - Typical database size: ~160 MB/year per instrument

    See Also:
        - query_ohlc() - Query OHLC bars after updating
        - query_ticks() - Query raw tick data after updating
        - get_data_coverage() - Check what's already in database
    """
    # ... existing implementation ...

    # At end, change return statement:
    return UpdateResult(
        duckdb_path=duckdb_path,
        months_added=months_success,
        raw_ticks_added=raw_ticks_total,
        standard_ticks_added=standard_ticks_total,
        ohlc_bars=ohlc_bars,
        duckdb_size_mb=duckdb_size_mb,
    )
```

**Changes**:
- ✅ `pair: str` → `pair: PairType` (IDE autocomplete shows valid values)
- ✅ `-> Dict[str, Any]` → `-> UpdateResult` (structured return)
- ✅ Rich docstring with Args/Returns/Raises/Examples/See Also/Note
- ✅ Return Pydantic model instead of dict

**Backward compatibility**: ✅ Perfect - Pydantic models support dict access

#### 2.2 Update `get_data_coverage()` Method

**Current signature**:
```python
def get_data_coverage(self, pair: str = "EURUSD") -> Dict[str, Any]:
```

**New signature**:
```python
def get_data_coverage(self, pair: PairType = "EURUSD") -> CoverageInfo:
    """
    Get data coverage information for an instrument.

    Args:
        pair: Currency pair (EURUSD, GBPUSD, XAUUSD, USDJPY, AUDUSD)

    Returns:
        CoverageInfo with database statistics. See CoverageInfo model for
        complete field descriptions and validation rules.

    Example:
        >>> processor = ExnessDataProcessor()
        >>> coverage = processor.get_data_coverage("EURUSD")
        >>> print(f"Coverage: {coverage.earliest_date} to {coverage.latest_date}")
        >>> print(f"Total: {coverage.raw_spread_ticks:,} ticks")
    """
    # ... existing implementation ...

    # At end, change return statement:
    return CoverageInfo(
        database_exists=True,
        duckdb_path=str(duckdb_path),
        duckdb_size_mb=duckdb_path.stat().st_size / 1024 / 1024,
        raw_spread_ticks=raw_count,
        standard_ticks=std_count,
        ohlc_bars=ohlc_count,
        earliest_date=str(earliest) if earliest else None,
        latest_date=str(latest) if latest else None,
        date_range_days=date_range_days,
    )
```

#### 2.3 Update `query_ticks()` Method

**Current signature**:
```python
def query_ticks(
    self,
    pair: str = "EURUSD",
    variant: str = "raw_spread",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    filter_sql: Optional[str] = None,
) -> pd.DataFrame:
```

**New signature**:
```python
def query_ticks(
    self,
    pair: PairType = "EURUSD",
    variant: VariantType = "raw_spread",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    filter_sql: Optional[str] = None,
) -> pd.DataFrame:
    """
    Query tick data with optional date range filtering.

    Retrieves raw tick data from the database for the specified variant.
    Supports date range filtering and custom SQL WHERE clauses for
    advanced queries.

    Args:
        pair: Currency pair (EURUSD, GBPUSD, XAUUSD, USDJPY, AUDUSD)
        variant: Data variant (raw_spread or standard)
        start_date: Optional start date in YYYY-MM-DD format (inclusive)
        end_date: Optional end date in YYYY-MM-DD format (inclusive)
        filter_sql: Optional SQL WHERE clause (e.g., "Bid > 1.11 AND Ask < 1.12")

    Returns:
        DataFrame with columns: Timestamp, Bid, Ask
        Empty DataFrame if no ticks match the filters

    Raises:
        FileNotFoundError: If database doesn't exist (call update_data first)
        ValueError: If date format is invalid

    Example - Query all Raw_Spread ticks for September 2024:
        >>> df = processor.query_ticks("EURUSD", "raw_spread",
        ...                             "2024-09-01", "2024-09-30")
        >>> print(f"Ticks: {len(df):,}")

    Example - Query with custom SQL filter:
        >>> df = processor.query_ticks("EURUSD", "raw_spread",
        ...                             filter_sql="Bid > 1.11")
        >>> print(f"High-price ticks: {len(df):,}")

    Example - Query zero-spread ticks only:
        >>> df = processor.query_ticks("EURUSD", "raw_spread",
        ...                             filter_sql="Bid = Ask")
        >>> print(f"Zero-spreads: {len(df):,}")

    Performance:
        - <15ms for 1 month (~880K ticks)
        - Date range filtering is optimized
        - SQL filters execute in-database

    See Also:
        - query_ohlc() - Query aggregated OHLC bars
        - update_data() - Download tick data first
    """
    # ... existing implementation unchanged ...
```

#### 2.4 Update `query_ohlc()` Method

**Current signature**:
```python
def query_ohlc(
    self,
    pair: str = "EURUSD",
    timeframe: str = "1m",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> pd.DataFrame:
```

**New signature**:
```python
def query_ohlc(
    self,
    pair: PairType = "EURUSD",
    timeframe: TimeframeType = "1m",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> pd.DataFrame:
    """
    Query OHLC bars with optional date range filtering and resampling.

    Retrieves 1-minute bars from the database and optionally resamples to higher
    timeframes. All resampling is performed in-database using DuckDB's window
    functions for optimal performance (<15ms for most queries).

    The returned DataFrame contains Phase7 9-column schema:
    - Timestamp: Bar timestamp (UTC)
    - Open, High, Low, Close: BID prices from Raw_Spread variant
    - raw_spread_avg: Average spread from Raw_Spread variant
    - standard_spread_avg: Average spread from Standard variant
    - tick_count_raw_spread: Tick count from Raw_Spread variant
    - tick_count_standard: Tick count from Standard variant

    Args:
        pair: Currency pair (EURUSD, GBPUSD, XAUUSD, USDJPY, AUDUSD)
        timeframe: Bar timeframe (1m, 5m, 15m, 1h, 4h, 1d)
        start_date: Optional start date in YYYY-MM-DD format (inclusive)
        end_date: Optional end date in YYYY-MM-DD format (inclusive)

    Returns:
        DataFrame with Phase7 9-column OHLC schema. Empty if no data in range.

    Raises:
        FileNotFoundError: If database doesn't exist (call update_data first)
        ValueError: If date format is invalid or timeframe unsupported

    Example - Query 1-minute bars for January 2024:
        >>> df = processor.query_ohlc("EURUSD", "1m", "2024-01-01", "2024-01-31")
        >>> print(f"Bars: {len(df):,}")
        >>> print(f"Columns: {list(df.columns)}")

    Example - Query 1-hour bars for Q1 2024 (resampled on-demand):
        >>> df = processor.query_ohlc("EURUSD", "1h", "2024-01-01", "2024-03-31")
        >>> print(f"Avg spread: {df['raw_spread_avg'].mean() * 10000:.2f} pips")

    Example - Query all data (no date filtering):
        >>> df = processor.query_ohlc("EURUSD", "1d")
        >>> print(f"Date range: {df['Timestamp'].min()} to {df['Timestamp'].max()}")

    Performance:
        - 1-minute bars: <10ms for 1 month (30K rows)
        - 1-hour bars: <15ms for 1 year (6K rows)
        - 1-day bars: <20ms for 10 years (2.5K rows)

    See Also:
        - query_ticks() - Query raw tick data instead of OHLC
        - update_data() - Download data before querying
        - supported_timeframes() - Get list of valid timeframes
    """
    # ... existing implementation unchanged ...
```

---

### Phase 3: Deprecate api.py (30 minutes)

#### 3.1 Fix or Remove api.py

**Option A: Remove entirely** (Recommended)
- api.py is completely broken
- All functions call non-existent methods
- No users can be relying on it

**Option B: Fix and deprecate**
- Would need to rewrite all functions
- More work for no benefit
- Delays v2.1.0 release

**Recommendation**: Remove api.py, add deprecation notice in CHANGELOG.md

#### 3.2 Update __init__.py

**Current**:
```python
from exness_data_preprocess.api import (
    analyze_ticks,
    get_storage_stats,
    process_date_range,
    process_month,
    query_ohlc,
)
from exness_data_preprocess.processor import ExnessDataProcessor

__all__ = [
    "ExnessDataProcessor",
    "process_month",
    "process_date_range",
    "query_ohlc",
    "analyze_ticks",
    "get_storage_stats",
    "__version__",
]
```

**New**:
```python
"""
exness-data-preprocess v2.1.0

Professional forex tick data preprocessing with unified DuckDB storage.

Quick Start:
    >>> import exness_data_preprocess as edp
    >>>
    >>> # Initialize processor
    >>> processor = edp.ExnessDataProcessor()
    >>>
    >>> # Download 3 years of data (automatic gap detection)
    >>> result = processor.update_data("EURUSD", start_date="2022-01-01")
    >>> print(f"Months added: {result.months_added}")
    >>>
    >>> # Query 1-minute OHLC for January 2024
    >>> df_ohlc = processor.query_ohlc("EURUSD", "1m", "2024-01-01", "2024-01-31")
    >>>
    >>> # Query raw ticks for September 2024
    >>> df_ticks = processor.query_ticks("EURUSD", "raw_spread", "2024-09-01", "2024-09-30")
    >>>
    >>> # Check data coverage
    >>> coverage = processor.get_data_coverage("EURUSD")
    >>> print(f"Ticks: {coverage.raw_spread_ticks:,}")

Supported: EURUSD, GBPUSD, XAUUSD, USDJPY, AUDUSD
Timeframes: 1m, 5m, 15m, 1h, 4h, 1d
Variants: raw_spread, standard
"""

__version__ = "2.1.0"
__author__ = "Terry Li <terry@eonlabs.com>"
__license__ = "MIT"

from exness_data_preprocess.processor import ExnessDataProcessor
from exness_data_preprocess.models import (
    UpdateResult,
    CoverageInfo,
    PairType,
    TimeframeType,
    VariantType,
)

__all__ = [
    # Main API
    "ExnessDataProcessor",
    # Pydantic Models
    "UpdateResult",
    "CoverageInfo",
    # Type Hints
    "PairType",
    "TimeframeType",
    "VariantType",
    # Package metadata
    "__version__",
]
```

---

### Phase 4: Testing Strategy (2 hours)

#### 4.1 Backward Compatibility Tests

**Create**: `tests/test_backward_compatibility.py`

```python
"""Test that v2.1.0 is backward compatible with v2.0.0 usage patterns."""

def test_dict_access_still_works():
    """Pydantic models should support dict-style access."""
    from exness_data_preprocess.models import UpdateResult

    result = UpdateResult(
        duckdb_path="/tmp/test.duckdb",
        months_added=1,
        raw_ticks_added=100,
        standard_ticks_added=100,
        ohlc_bars=10,
        duckdb_size_mb=1.0,
    )

    # Old style (dict access) should still work
    assert result['months_added'] == 1
    assert result['duckdb_size_mb'] == 1.0

    # New style (attribute access) also works
    assert result.months_added == 1
    assert result.duckdb_size_mb == 1.0


def test_update_data_return_type():
    """update_data() should return dict-compatible object."""
    # ... test implementation ...


def test_coverage_return_type():
    """get_data_coverage() should return dict-compatible object."""
    # ... test implementation ...
```

#### 4.2 Validation Tests

**Create**: `tests/test_validation.py`

```python
"""Test Pydantic validation works correctly."""

def test_update_result_validation():
    """UpdateResult should validate field constraints."""
    from exness_data_preprocess.models import UpdateResult
    from pydantic import ValidationError
    import pytest

    # Negative months_added should fail
    with pytest.raises(ValidationError):
        UpdateResult(
            duckdb_path="/tmp/test.duckdb",
            months_added=-1,  # ❌ Invalid
            raw_ticks_added=100,
            standard_ticks_added=100,
            ohlc_bars=10,
            duckdb_size_mb=1.0,
        )


def test_pair_type_validation():
    """PairType should only accept valid pairs."""
    from exness_data_preprocess import ExnessDataProcessor

    processor = ExnessDataProcessor()

    # Valid pair should work
    result = processor.update_data("EURUSD", "2022-01-01")

    # Invalid pair should fail type checking (mypy)
    # Runtime won't catch this unless we add runtime validation
```

#### 4.3 AI Agent Discovery Tests

**Create**: `tests/test_ai_discovery.py`

```python
"""Test that AI agents can discover API structure."""

def test_json_schema_generation():
    """Models should generate JSON Schema for AI agents."""
    from exness_data_preprocess.models import UpdateResult

    schema = UpdateResult.model_json_schema()

    assert 'properties' in schema
    assert 'months_added' in schema['properties']
    assert schema['properties']['months_added']['type'] == 'integer'
    assert schema['properties']['months_added']['minimum'] == 0


def test_literal_type_discovery():
    """AI agents should discover valid enum values."""
    from typing import get_args
    from exness_data_preprocess.models import PairType

    pairs = get_args(PairType)
    assert "EURUSD" in pairs
    assert "GBPUSD" in pairs


def test_help_function():
    """help() should show rich docstrings."""
    from exness_data_preprocess import ExnessDataProcessor
    import inspect

    doc = inspect.getdoc(ExnessDataProcessor.update_data)
    assert "Download and update forex data" in doc
    assert "Example" in doc
```

---

## Risk Assessment

### Low Risk Changes ✅
- Adding Pydantic models (new file, no existing code affected)
- Adding validation helpers (new methods, purely additive)
- Updating docstrings (doesn't affect runtime behavior)
- Updating __init__.py docstring (cosmetic change)

### Medium Risk Changes ⚠️
- Changing return types `Dict[str, Any]` → Pydantic models
  - **Mitigation**: Pydantic models are dict-compatible
  - **Test**: Verify dict access still works
- Changing parameter types `str` → `Literal`
  - **Mitigation**: Literal accepts same string values
  - **Test**: Verify existing calls still work

### High Risk Changes ❌
- Removing api.py
  - **Mitigation**: api.py is already broken, can't have users
  - **Test**: N/A - no functional code to break

### Regressions to Avoid

1. **Dict access breaking** - Ensure Pydantic models support `result['key']`
2. **Parameter validation too strict** - Don't add runtime validation, only types
3. **Import paths changing** - Keep `ExnessDataProcessor` importable from root
4. **Examples breaking** - Update all examples to use new API

---

## Migration Timeline

### Hour 1: Foundation
- [ ] Create models.py with Pydantic models
- [ ] Add validation helpers to processor.py
- [ ] Update imports in processor.py

### Hour 2: Update Signatures
- [ ] Update update_data() signature and docstring
- [ ] Update get_data_coverage() signature and docstring
- [ ] Update return statements to use Pydantic models

### Hour 3: Update Remaining Methods
- [ ] Update query_ticks() signature and docstring
- [ ] Update query_ohlc() signature and docstring
- [ ] Remove api.py
- [ ] Update __init__.py

### Hour 4: Testing
- [ ] Write backward compatibility tests
- [ ] Write validation tests
- [ ] Write AI discovery tests
- [ ] Run existing test suite
- [ ] Update examples/

### Hour 5: Documentation
- [ ] Update README.md Quick Start
- [ ] Update CHANGELOG.md
- [ ] Update CLAUDE.md in project
- [ ] Update examples/basic_usage.py
- [ ] Update examples/batch_processing.py

---

## Success Criteria

### Functional Requirements
- ✅ All existing code continues to work (dict access)
- ✅ Type hints show valid values in IDE
- ✅ Runtime validation catches invalid data
- ✅ JSON Schema auto-generated
- ✅ help() shows rich documentation

### Performance Requirements
- ✅ No performance degradation (Pydantic v2 is fast)
- ✅ Same query performance (<15ms)

### Documentation Requirements
- ✅ AI agents can discover API via introspection
- ✅ Examples in docstrings
- ✅ Validation rules in Field descriptions

---

## Post-Implementation Validation

### Checklist
1. [ ] Run full test suite (existing + new tests)
2. [ ] Verify examples/ still work
3. [ ] Test in real REPL with real database
4. [ ] Run mypy type checking
5. [ ] Generate JSON Schema and verify structure
6. [ ] Test with AI agent (Claude Code, Copilot)
7. [ ] Update PyPI package description

### Rollback Plan
If critical issues found:
1. Revert to v2.0.0 tag
2. Keep models.py for future
3. Release v2.0.1 with bug fixes only

---

## Conclusion

This refactoring plan provides:
- ✅ **High Impact**: Enables AI discovery, adds validation, generates schemas
- ✅ **Low Regression Risk**: Backward compatible via Pydantic dict access
- ✅ **Clear Timeline**: 5 hours total (3 implementation + 2 testing)
- ✅ **Measurable Success**: Concrete functional/performance/documentation criteria

**Recommendation**: Proceed with implementation following this phased approach.

**Next Step**: Review this plan, then begin Phase 1 implementation.
