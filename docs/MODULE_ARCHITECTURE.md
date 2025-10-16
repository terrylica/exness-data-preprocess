# Module Architecture

**Version**: v1.3.0 (Facade Pattern Implementation)
**Last Updated**: 2025-10-16
**Related**: [`README.md`](../README.md) - Architecture overview

---

## Overview

The exness-data-preprocess codebase uses a **Facade Pattern** with 7 specialized modules coordinated by a thin orchestrator (`processor.py`). Each module has a single responsibility and defines clear SLOs (Availability, Correctness, Observability, Maintainability).

**Design Principles**:
- **Facade Pattern**: processor.py delegates all operations to specialized modules
- **Separation of Concerns**: Each module has single, focused responsibility
- **SLO-Based Design**: All modules define Availability, Correctness, Observability, Maintainability contracts
- **Off-the-Shelf Libraries**: httpx, pandas, DuckDB, exchange_calendars (no custom implementations)
- **Zero Regressions**: All 48 tests pass after 7-module extraction

**Architecture Diagram**:
```
┌─────────────────────────────────────────────────┐
│           processor.py (Facade)                 │
│  Thin orchestrator coordinating workflow        │
└─────────────────────────────────────────────────┘
              ↓
    ┌─────────┴─────────┐
    │                   │
    ↓                   ↓
┌─────────────┐   ┌──────────────┐
│ downloader  │   │ tick_loader  │
│ .py         │   │ .py          │
└─────────────┘   └──────────────┘
    ↓                   ↓
┌─────────────────────────────────┐
│    database_manager.py          │
│  (DuckDB operations, schema)    │
└─────────────────────────────────┘
    ↓
┌──────────────┬─────────────┬──────────────┐
│ session_     │ gap_        │ ohlc_        │
│ detector.py  │ detector.py │ generator.py │
└──────────────┴─────────────┴──────────────┘
    ↓
┌─────────────────────────────────────────────────┐
│           query_engine.py                       │
│  Tick/OHLC queries, date filtering, resampling  │
└─────────────────────────────────────────────────┘
```

---

## Module 1: processor.py (Facade Orchestrator)

**File**: `src/exness_data_preprocess/processor.py`

**Role**: Thin orchestrator facade coordinating 7 specialized modules

**Pattern**: Facade Pattern - all public methods delegate to specialized modules

**Responsibilities**:
- Initialize 7 module dependencies
- Coordinate workflow between modules
- Provide unified public API
- No business logic (all delegated to modules)

**Key Methods**:
- `__init__()` - Initialize 7 module dependencies
- `download_exness_zip()` - Delegates to downloader module
- `_get_or_create_db()` - Delegates to database_manager module
- `_load_ticks_from_zip()` - Delegates to tick_loader module
- `_append_ticks_to_db()` - Delegates to database_manager module
- `_discover_missing_months()` - Delegates to gap_detector module
- `update_data()` - Main workflow orchestrator
- `_regenerate_ohlc()` - Delegates to ohlc_generator module
- `query_ticks()` - Delegates to query_engine module
- `query_ohlc()` - Delegates to query_engine module
- `get_data_coverage()` - Delegates to query_engine module

**SLOs**:
- **Availability**: Raises exceptions from delegated modules (no fallbacks)
- **Correctness**: Delegates validation to specialized modules
- **Observability**: Orchestration logging, module logs propagated
- **Maintainability**: Thin facade, easy to add new modules

**Module Statistics**: Run `make module-stats` to see current line count

---

## Module 2: downloader.py (HTTP Downloads)

**File**: `src/exness_data_preprocess/downloader.py`

**Role**: HTTP download operations for Exness ZIP files

**Responsibility**: Download Exness ZIP files from ticks.ex2archive.com

**Class**: `ExnessDownloader`

**Methods**:
- `download_zip(year: int, month: int, pair: str, variant: str) -> Path`
  - Downloads ZIP file for specified parameters
  - Returns path to downloaded ZIP file
  - Raises HTTPError on download failure

**SLOs**:
- **Availability**: Raise exceptions on HTTP errors (no fallback retries)
- **Correctness**: Validate URL patterns match Exness repository structure
- **Observability**: HTTP request logging via httpx library
- **Maintainability**: Thin wrapper around httpx library (off-the-shelf)

**Dependencies**:
- httpx - HTTP client library
- pathlib - File path handling

**URL Pattern**:
```
https://ticks.ex2archive.com/ticks/{VARIANT}/{YEAR}/{MONTH}/Exness_{VARIANT}_{YEAR}_{MONTH}.zip
```

**Example**:
```python
downloader = ExnessDownloader()
zip_path = downloader.download_zip(2024, 9, "EURUSD", "Raw_Spread")
# Returns: Path to Exness_EURUSD_Raw_Spread_2024_09.zip
```

**Error Handling**:
- HTTP 404: Raise error (month doesn't exist)
- HTTP 500: Raise error (server error)
- Network timeout: Raise error (no retries)

---

## Module 3: tick_loader.py (CSV Parsing)

**File**: `src/exness_data_preprocess/tick_loader.py`

**Role**: Load tick data from ZIP files into pandas DataFrames

**Responsibility**: Parse CSV tick data from Exness ZIP files with microsecond-precision timestamps

**Class**: `TickLoader`

**Methods**:
- `load_from_zip(zip_path: Path) -> pd.DataFrame` (static method)
  - Opens ZIP file, reads CSV
  - Parses timestamps to datetime64[ns]
  - Returns DataFrame with columns: Timestamp, Bid, Ask
  - Raises ValueError on parsing errors

**SLOs**:
- **Availability**: Raise exceptions on CSV parsing errors (no fallback)
- **Correctness**: Validate timestamp parsing to microsecond precision
- **Observability**: Parsing error logging with line numbers
- **Maintainability**: Pure pandas implementation (off-the-shelf)

**Dependencies**:
- pandas - DataFrame operations
- zipfile - ZIP archive handling

**CSV Format**:
```csv
Timestamp,Bid,Ask
2024-09-01 00:00:01.123456,1.10234,1.10236
2024-09-01 00:00:01.234567,1.10235,1.10237
```

**Example**:
```python
df = TickLoader.load_from_zip(Path("Exness_EURUSD_Raw_Spread_2024_09.zip"))
# Returns DataFrame with ~815K rows, 3 columns
```

**Validation**:
- Timestamps must be monotonically increasing
- Bid and Ask must be positive floats
- No NULL values allowed

---

## Module 4: database_manager.py (Database Operations)

**File**: `src/exness_data_preprocess/database_manager.py`

**Role**: Database initialization, schema creation, tick insertion with duplicate prevention

**Responsibility**: Manage DuckDB database lifecycle and ensure schema integrity

**Class**: `DatabaseManager`

**Methods**:
- `get_or_create_db(pair: str) -> Path`
  - Creates database if doesn't exist
  - Initializes schema with PRIMARY KEY constraints
  - Adds COMMENT ON statements for self-documentation
  - Returns path to database file

- `append_ticks(duckdb_path: Path, df: pd.DataFrame, table_name: str) -> int`
  - Appends tick data to specified table
  - PRIMARY KEY prevents duplicates (silent ignore)
  - Returns number of rows inserted
  - Raises DuckDBError on schema mismatches

**SLOs**:
- **Availability**: Raise exceptions on database errors (no fallback)
- **Correctness**: Enforce schema integrity with PRIMARY KEY constraints
- **Observability**: DuckDB logging enabled, transaction logging
- **Maintainability**: Pure DuckDB library (off-the-shelf)

**Dependencies**:
- duckdb - Database library
- pandas - DataFrame integration

**Schema**:
```sql
-- raw_spread_ticks table
CREATE TABLE IF NOT EXISTS raw_spread_ticks (
    Timestamp TIMESTAMP PRIMARY KEY,
    Bid DOUBLE NOT NULL,
    Ask DOUBLE NOT NULL
);

-- standard_ticks table
CREATE TABLE IF NOT EXISTS standard_ticks (
    Timestamp TIMESTAMP PRIMARY KEY,
    Bid DOUBLE NOT NULL,
    Ask DOUBLE NOT NULL
);

-- ohlc_1m table (30 columns, Phase7 schema v1.5.0)
-- See docs/DATABASE_SCHEMA.md for complete schema

-- metadata table
CREATE TABLE IF NOT EXISTS metadata (
    key VARCHAR PRIMARY KEY,
    value VARCHAR,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Self-Documentation**:
- All tables have COMMENT ON TABLE statements
- All columns have COMMENT ON COLUMN statements
- Queryable via `duckdb_tables()` and `duckdb_columns()`

**Duplicate Handling**:
- PRIMARY KEY constraint automatically prevents duplicates
- No error raised on duplicate insert (silent ignore per DuckDB default)
- Enables safe incremental updates

---

## Module 5: session_detector.py (Holiday and Session Detection)

**File**: `src/exness_data_preprocess/session_detector.py`

**Role**: Detect holidays and trading sessions for 10 global exchanges

**Responsibility**: Use exchange_calendars library to detect US/UK/major holidays and global exchange trading sessions

**Class**: `SessionDetector`

**Methods**:
- `detect_sessions_and_holidays(dates_df: pd.DataFrame) -> pd.DataFrame`
  - Input: DataFrame with date column
  - Output: DataFrame with 13 additional columns:
    - `is_us_holiday` (BOOLEAN)
    - `is_uk_holiday` (BOOLEAN)
    - `is_major_holiday` (BOOLEAN)
    - `is_nyse_session` (BOOLEAN) - New York Stock Exchange
    - `is_lse_session` (BOOLEAN) - London Stock Exchange
    - `is_xswx_session` (BOOLEAN) - Swiss Exchange
    - `is_xfra_session` (BOOLEAN) - Frankfurt Stock Exchange
    - `is_xtse_session` (BOOLEAN) - Toronto Stock Exchange
    - `is_xnze_session` (BOOLEAN) - New Zealand Exchange
    - `is_xtks_session` (BOOLEAN) - Tokyo Stock Exchange
    - `is_xasx_session` (BOOLEAN) - Australian Securities Exchange
    - `is_xhkg_session` (BOOLEAN) - Hong Kong Exchange
    - `is_xses_session` (BOOLEAN) - Singapore Exchange

**SLOs**:
- **Availability**: Raise exceptions on exchange_calendars errors (no fallback)
- **Correctness**: Use official exchange calendars with DST handling
- **Observability**: Calendar lookup logging
- **Maintainability**: Thin wrapper around exchange_calendars library (off-the-shelf)

**Dependencies**:
- exchange_calendars - Official exchange trading calendars
- pandas_market_calendars - Market session detection

**Exchange Coverage**:
- **10 global exchanges** covering 24-hour forex trading
- **Automatic DST handling** via exchange_calendars
- **Holiday detection** for US (NYSE calendar), UK (LSE calendar), and major overlaps

**Use Case**: Phase7 OHLC schema (v1.5.0) includes session flags for regime detection

**Example**:
```python
detector = SessionDetector()
dates_df = pd.DataFrame({'date': pd.date_range('2024-09-01', '2024-09-30')})
result = detector.detect_sessions_and_holidays(dates_df)
# Returns DataFrame with 13 additional boolean columns
```

---

## Module 6: gap_detector.py (Incremental Update Logic)

**File**: `src/exness_data_preprocess/gap_detector.py`

**Role**: Discover missing months for incremental database updates

**Responsibility**: Compare database coverage vs. Exness repository to identify gaps

**Class**: `GapDetector`

**Methods**:
- `discover_missing_months(pair: str, start_date: datetime) -> List[Tuple[int, int]]`
  - Queries database metadata for earliest/latest dates
  - Queries Exness repository for available months
  - Returns list of (year, month) tuples for missing data
  - Returns empty list if database is up-to-date

**SLOs**:
- **Availability**: Raise exceptions on database/HTTP errors (no fallback)
- **Correctness**: Accurate gap detection using metadata table
- **Observability**: Gap discovery logging (e.g., "Found 3 missing months")
- **Maintainability**: DuckDB metadata + HTTP directory listing (off-the-shelf)

**Dependencies**:
- duckdb - Metadata queries
- httpx - Repository directory listing
- pandas - Date range calculations

**Gap Detection Logic**:
1. Query metadata table for `earliest_date` and `latest_date`
2. Calculate expected month range: `start_date` to `current_month`
3. Identify months missing from database
4. Return list of missing (year, month) tuples

**Example**:
```python
gap_detector = GapDetector()
missing = gap_detector.discover_missing_months("EURUSD", datetime(2024, 1, 1))
# Returns: [(2024, 1), (2024, 2), (2024, 3)] if Jan-Mar missing
# Returns: [] if database is up-to-date
```

**Use Case**: Enables incremental `update_data()` to download only missing months

---

## Module 7: ohlc_generator.py (OHLC Generation)

**File**: `src/exness_data_preprocess/ohlc_generator.py`

**Role**: Generate Phase7 30-column OHLC from dual-variant tick data

**Responsibility**: Aggregate Raw_Spread and Standard ticks into 1-minute OHLC bars using LEFT JOIN methodology

**Class**: `OHLCGenerator`

**Methods**:
- `regenerate_ohlc(duckdb_path: Path) -> int`
  - Drops existing `ohlc_1m` table
  - Generates Phase7 30-column OHLC via SQL LEFT JOIN
  - Detects sessions and holidays using `session_detector`
  - Returns number of OHLC bars generated

**SLOs**:
- **Availability**: Raise exceptions on SQL errors (no fallback)
- **Correctness**: Phase7 schema v1.5.0 with dual-variant spreads and normalized metrics
- **Observability**: OHLC generation logging (bars created, date range)
- **Maintainability**: DuckDB aggregation + exchange_calendars (off-the-shelf)

**Dependencies**:
- duckdb - OHLC aggregation SQL
- session_detector - Holiday and session detection
- schema.py - OHLCSchema class for column definitions

**Phase7 Schema (v1.5.0)**:
- **30 columns** total (see `docs/DATABASE_SCHEMA.md` for complete schema)
- **BID-only OHLC**: Uses Raw_Spread Bid prices (execution prices)
- **Dual spreads**: `raw_spread_avg` and `standard_spread_avg`
- **Dual tick counts**: `tick_count_raw_spread` and `tick_count_standard`
- **Normalized metrics**: `range_per_spread`, `range_per_tick`, `body_per_spread`, `body_per_tick`
- **Timezone/session tracking**: `ny_hour`, `london_hour`, `ny_session`, `london_session`
- **Holiday tracking**: `is_us_holiday`, `is_uk_holiday`, `is_major_holiday`
- **10 Global Exchange Sessions**: is_nyse_session, is_lse_session, is_xswx_session, is_xfra_session, is_xtse_session, is_xnze_session, is_xtks_session, is_xasx_session, is_xhkg_session, is_xses_session

**LEFT JOIN Methodology**:
```sql
SELECT
    DATE_TRUNC('minute', r.Timestamp) AS minute,
    MIN(r.Bid) AS open,
    MAX(r.Bid) AS high,
    MIN(r.Bid) AS low,
    LAST(r.Bid ORDER BY r.Timestamp) AS close,
    COUNT(r.Timestamp) AS tick_count_raw_spread,
    AVG(r.Ask - r.Bid) AS raw_spread_avg,
    COUNT(s.Timestamp) AS tick_count_standard,
    AVG(s.Ask - s.Bid) AS standard_spread_avg,
    -- ... 21 more columns
FROM raw_spread_ticks r
LEFT JOIN standard_ticks s
    ON DATE_TRUNC('minute', r.Timestamp) = DATE_TRUNC('minute', s.Timestamp)
GROUP BY DATE_TRUNC('minute', r.Timestamp)
ORDER BY minute;
```

**Exchange Registry Pattern** (v1.5.0):
- Centralized `EXCHANGES` dict in `session_detector.py`
- Dynamic session column generation from registry
- Easy to add new exchanges (modify dict, schema auto-updates)

**Example**:
```python
generator = OHLCGenerator()
bars_created = generator.regenerate_ohlc(Path("eurusd.duckdb"))
# Returns: 413000 (for 13 months of 1-minute bars)
```

---

## Module 8: query_engine.py (Query Operations)

**File**: `src/exness_data_preprocess/query_engine.py`

**Role**: Query tick and OHLC data with date filtering, SQL filters, and on-demand resampling

**Responsibility**: Provide unified query interface for tick and OHLC data with performance <15ms

**Class**: `QueryEngine`

**Methods**:
- `query_ticks(duckdb_path: Path, table_name: str, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None, sql_filter: Optional[str] = None) -> pd.DataFrame`
  - Queries raw_spread_ticks or standard_ticks tables
  - Optional date range filtering
  - Optional SQL WHERE clause filter
  - Returns DataFrame with filtered ticks

- `query_ohlc(duckdb_path: Path, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None, timeframe: str = "1m", sql_filter: Optional[str] = None) -> pd.DataFrame`
  - Queries ohlc_1m table
  - Optional date range filtering
  - Optional on-demand resampling (1m/5m/15m/1h/4h/1d)
  - Optional SQL WHERE clause filter
  - Returns DataFrame with OHLC bars

- `get_data_coverage(duckdb_path: Path) -> dict`
  - Queries metadata table
  - Returns dict with: earliest_date, latest_date, total_ticks_raw_spread, total_ticks_standard, total_ohlc_bars

**SLOs**:
- **Availability**: Raise exceptions on SQL errors (no fallback)
- **Correctness**: Accurate date filtering and aggregation
- **Observability**: Query logging (query time, rows returned)
- **Maintainability**: Pure DuckDB SQL (off-the-shelf)

**Dependencies**:
- duckdb - SQL query execution
- pandas - DataFrame results

**Performance**:
- **Sub-15ms** for all queries (date range filtering, resampling)
- Indexed on Timestamp PRIMARY KEY
- No full table scans

**On-Demand Resampling**:
```python
# 1-minute bars (direct from ohlc_1m)
df = query_engine.query_ohlc(db_path, timeframe="1m")

# 5-minute bars (aggregated from ohlc_1m)
df = query_engine.query_ohlc(db_path, timeframe="5m")

# 1-hour bars (aggregated from ohlc_1m)
df = query_engine.query_ohlc(db_path, timeframe="1h")
```

**SQL Filter Example**:
```python
# Get only OHLC bars during US trading hours
df = query_engine.query_ohlc(
    db_path,
    sql_filter="ny_session = TRUE AND is_us_holiday = FALSE"
)
```

---

## Module 9: api.py (Backward Compatibility Layer)

**File**: `src/exness_data_preprocess/api.py`

**Role**: v1.0.0 CLI compatibility wrappers

**Responsibility**: Map v1.0.0 monthly-file API to v2.0.0 unified single-file API

**Functions**:
- `process_month(pair, year, month)` → Delegates to `processor.update_data()`
- `process_date_range(pair, start_date, end_date)` → Delegates to `processor.update_data()`
- `query_ohlc(pair, start_date, end_date)` → Delegates to `processor.query_ohlc()`
- `analyze_ticks(pair, month)` → Delegates to `processor.query_ticks()`
- `get_storage_stats(pair)` → Delegates to `processor.get_data_coverage()`

**SLOs**:
- **Availability**: Raise exceptions from processor (no additional error handling)
- **Correctness**: Delegate to processor methods (no transformation logic)
- **Observability**: Processor logging propagated
- **Maintainability**: Thin wrappers (will be deprecated when CLI is rewritten)

**Status**: Backward compatibility for CLI (to be deprecated in future release)

---

## Module 10: cli.py (Command-Line Interface)

**File**: `src/exness_data_preprocess/cli.py`

**Role**: Command-line interface for package

**Responsibility**: Provide `exness-preprocess` command with subcommands

**Entry Point**: `exness-preprocess` command (installed via setuptools)

**Subcommands**:
- `download` - Download and update data
- `query` - Query tick or OHLC data
- `coverage` - Show data coverage

**SLOs**:
- **Availability**: Print errors to stderr, exit with non-zero code
- **Correctness**: Argument validation via argparse
- **Observability**: Progress bars, status messages
- **Maintainability**: Uses api.py functions (thin CLI layer)

**Status**: Uses deprecated api.py (will be rewritten for v2.0.0)

---

## Data Flow

```
Exness Repository (monthly ZIPs)
  ↓
gap_detector.py (discover missing months)
  ↓
downloader.py (download Raw_Spread + Standard)
  ↓
tick_loader.py (parse CSV from ZIP)
  ↓
database_manager.py (append to DuckDB, PRIMARY KEY prevents duplicates)
  ↓
ohlc_generator.py (Phase7 30-column OHLC with LEFT JOIN)
  ↓
session_detector.py (holidays + 10 exchange sessions)
  ↓
query_engine.py (tick/OHLC queries, date filters, resampling)
```

---

## Module Statistics

**Introspection Commands** (always current):
```bash
make module-stats       # Show current line counts
make module-complexity  # Show cyclomatic complexity (requires radon)
make module-deps        # Show dependency tree (requires pipdeptree)
```

See [`Makefile`](../Makefile) for implementation.

---

## Testing

**Test Suite**: 48 tests (100% passing)
- `test_models.py` - Pydantic model validation (13 tests)
- `test_types.py` - Type safety and helpers (15 tests)
- `test_processor_pydantic.py` - Integration tests (6 tests)
- `test_functional_regression.py` - v2.0.0 regression tests (10 tests)

**Coverage**:
- models.py: 100%
- __init__.py: 100%
- processor.py: 45% (orchestration code, hard to unit test)

**Run Tests**:
```bash
make test      # Run all tests
make test-cov  # Run with coverage report
```

---

## Design Patterns

### Facade Pattern (v1.3.0)

**Definition**: processor.py is a thin facade coordinating 7 specialized modules

**Benefits**:
- **Separation of concerns**: Each module has single responsibility
- **Testability**: Modules can be unit tested independently
- **Maintainability**: Easy to replace or extend individual modules
- **Zero regressions**: 48 tests pass after refactoring

**Metrics**:
- processor.py orchestrator: ~410 lines
- Extracted modules: ~1,140 lines
- Reduction: 53% line reduction via extraction

### SLO-Based Design

**Definition**: All modules define 4 SLOs:

1. **Availability**: How does the module handle errors?
   - Standard: Raise exceptions on errors (no fallback retries)
   - Enables fail-fast behavior

2. **Correctness**: What guarantees does the module provide?
   - Examples: URL pattern validation, schema integrity, timestamp precision
   - Documented as invariants

3. **Observability**: How does the module support debugging?
   - Standard: Logging via Python logging library
   - Propagates to orchestrator

4. **Maintainability**: How complex is the module implementation?
   - Preference: Off-the-shelf libraries (httpx, pandas, DuckDB)
   - Avoid custom implementations

**Benefits**:
- Clear contracts between modules
- Easy to verify module behavior
- Guides implementation decisions

### Off-the-Shelf Libraries

**Principle**: Prefer established libraries over custom implementations

**Libraries Used**:
- **httpx**: HTTP downloads (downloader.py)
- **pandas**: DataFrame operations (tick_loader.py, query_engine.py)
- **DuckDB**: Database operations (database_manager.py, query_engine.py)
- **exchange_calendars**: Exchange session detection (session_detector.py)
- **pandas_market_calendars**: Market session detection (session_detector.py)

**Benefits**:
- Battle-tested implementations
- Community support
- Reduced maintenance burden

---

## Future Enhancements

### Planned

1. **CLI Rewrite** - Rewrite cli.py to use processor methods directly (deprecate api.py)
2. **Streaming Queries** - Add streaming query methods for large date ranges
3. **Batch Operations** - Add batch download/query operations for multiple instruments
4. **Module Metrics** - Add module-level metrics (cache hit rates, query times)

### Under Consideration

1. **Plugin System** - Allow custom modules to extend processor
2. **Caching Layer** - Add Redis/Memcached for frequently accessed OHLC bars
3. **Parallel Downloads** - Parallel month downloads for faster updates

---

## Related Documentation

- **[README.md](../README.md)** - User-facing API reference
- **[docs/README.md](README.md)** - Documentation hub
- **[docs/DATABASE_SCHEMA.md](DATABASE_SCHEMA.md)** - Complete database schema
- **[docs/UNIFIED_DUCKDB_PLAN_v2.md](UNIFIED_DUCKDB_PLAN_v2.md)** - v2.0.0 architecture specification
- **[Makefile](../Makefile)** - Module introspection commands

---

**Version**: v1.3.0
**Last Updated**: 2025-10-16
**Status**: Facade Pattern Implementation Complete
