# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**Architecture**: Professional forex tick data preprocessing with unified single-file DuckDB storage

**Full Documentation**: [`README.md`](README.md) - Installation, usage, API reference

---

## Development Commands

### Setup
```bash
# Install with development dependencies
uv sync --dev

# Or with pip
pip install -e ".[dev]"
```

### Testing
```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=exness_data_preprocess --cov-report=html

# Run specific test file
uv run pytest tests/test_processor.py -v

# Run specific test
uv run pytest tests/test_processor.py::test_compression_ratio -v
```

### Code Quality
```bash
# Format code
uv run ruff format .

# Check formatting without changes
uv run ruff format --check .

# Lint and auto-fix
uv run ruff check --fix .

# Lint without changes
uv run ruff check .

# Type checking
uv run mypy src/
```

### Building and Publishing
```bash
# Build package
uv build

# Test installation locally
uv tool install --editable .

# Publish to PyPI (requires PYPI_TOKEN in environment)
doppler run --project claude-config --config dev -- uv publish --token "$PYPI_TOKEN"
```

---

## Codebase Architecture

### Module Structure (v1.3.0 - Facade Pattern)

**Architecture**: Thin facade orchestrator with 7 focused modules

**Core Facade**:

1. **`processor.py`** (`/Users/terryli/eon/exness-data-preprocess/src/exness_data_preprocess/processor.py`) - Thin orchestrator facade
   - **Responsibility**: Coordinate workflow, delegate to specialized modules
   - **Pattern**: Facade pattern - all public methods delegate to modules
   - **Lines 76-110**: `__init__()` - Initialize 7 module dependencies
   - **Lines 111-132**: `download_exness_zip()` - Delegates to downloader module
   - **Lines 134-145**: `_get_or_create_db()` - Delegates to database_manager module
   - **Lines 147-150**: `_load_ticks_from_zip()` - Delegates to tick_loader module
   - **Lines 152-162**: `_append_ticks_to_db()` - Delegates to database_manager module
   - **Lines 164-176**: `_discover_missing_months()` - Delegates to gap_detector module
   - **Lines 178-315**: `update_data()` - Main workflow orchestrator
   - **Lines 317-326**: `_regenerate_ohlc()` - Delegates to ohlc_generator module
   - **Lines 328-357**: `query_ticks()` - Delegates to query_engine module
   - **Lines 359-386**: `query_ohlc()` - Delegates to query_engine module
   - **Lines 388-412**: `get_data_coverage()` - Delegates to query_engine module

**Specialized Modules**:

2. **`downloader.py`** (`/Users/terryli/eon/exness-data-preprocess/src/exness_data_preprocess/downloader.py`) - HTTP download operations
   - **Responsibility**: Download Exness ZIP files from ticks.ex2archive.com
   - **SLOs**: Availability (raise on failure), Correctness (URL patterns), Observability (logging), Maintainability (httpx library)
   - **Class**: `ExnessDownloader`
   - **Methods**: `download_zip(year, month, pair, variant)`

3. **`tick_loader.py`** (`/Users/terryli/eon/exness-data-preprocess/src/exness_data_preprocess/tick_loader.py`) - CSV parsing
   - **Responsibility**: Load tick data from ZIP files into pandas DataFrames
   - **SLOs**: Availability (raise on failure), Correctness (timestamp parsing), Observability (logging), Maintainability (pandas library)
   - **Class**: `TickLoader`
   - **Methods**: `load_from_zip(zip_path)` (static method)

4. **`database_manager.py`** (`/Users/terryli/eon/exness-data-preprocess/src/exness_data_preprocess/database_manager.py`) - Database operations
   - **Responsibility**: Database initialization, schema creation, tick insertion with PRIMARY KEY duplicate prevention
   - **SLOs**: Availability (raise on failure), Correctness (schema integrity), Observability (DuckDB logging), Maintainability (DuckDB library)
   - **Class**: `DatabaseManager`
   - **Methods**: `get_or_create_db(pair)`, `append_ticks(duckdb_path, df, table_name)`

5. **`session_detector.py`** (`/Users/terryli/eon/exness-data-preprocess/src/exness_data_preprocess/session_detector.py`) - Holiday and session detection
   - **Responsibility**: Detect holidays (US, UK, major) and trading sessions for 10 global exchanges using exchange_calendars
   - **SLOs**: Availability (raise on failure), Correctness (official calendars), Observability (logging), Maintainability (exchange_calendars library)
   - **Class**: `SessionDetector`
   - **Methods**: `detect_sessions_and_holidays(dates_df)`

6. **`gap_detector.py`** (`/Users/terryli/eon/exness-data-preprocess/src/exness_data_preprocess/gap_detector.py`) - Incremental update logic
   - **Responsibility**: Discover missing months for incremental database updates
   - **SLOs**: Availability (raise on failure), Correctness (gap detection), Observability (logging), Maintainability (DuckDB library)
   - **Class**: `GapDetector`
   - **Methods**: `discover_missing_months(pair, start_date)`

7. **`ohlc_generator.py`** (`/Users/terryli/eon/exness-data-preprocess/src/exness_data_preprocess/ohlc_generator.py`) - OHLC generation
   - **Responsibility**: Generate Phase7 30-column OHLC from dual-variant tick data with LEFT JOIN, normalized metrics, and exchange session detection
   - **SLOs**: Availability (raise on failure), Correctness (Phase7 schema), Observability (logging), Maintainability (DuckDB + exchange_calendars)
   - **Class**: `OHLCGenerator`
   - **Methods**: `regenerate_ohlc(duckdb_path)`

8. **`query_engine.py`** (`/Users/terryli/eon/exness-data-preprocess/src/exness_data_preprocess/query_engine.py`) - Query operations
   - **Responsibility**: Query tick and OHLC data with date filtering, SQL filters, and on-demand resampling (1m/5m/15m/1h/4h/1d)
   - **SLOs**: Availability (raise on failure), Correctness (SQL queries), Observability (DuckDB logging), Maintainability (DuckDB library)
   - **Class**: `QueryEngine`
   - **Methods**: `query_ticks()`, `query_ohlc()`, `get_data_coverage()`

**Compatibility Layer**:

9. **`api.py`** (`/Users/terryli/eon/exness-data-preprocess/src/exness_data_preprocess/api.py`) - v1.0.0 CLI compatibility wrappers
   - **Responsibility**: Map v1.0.0 monthly-file API to v2.0.0 unified single-file API
   - **SLOs**: Availability (raise on errors), Correctness (delegate to processor), Observability (processor logging), Maintainability (thin wrappers)
   - **Functions**: `process_month()`, `process_date_range()`, `query_ohlc()`, `analyze_ticks()`, `get_storage_stats()`
   - **Status**: Backward compatibility for CLI (will be deprecated when CLI is rewritten for v2.0.0)

10. **`cli.py`** (`/Users/terryli/eon/exness-data-preprocess/src/exness_data_preprocess/cli.py`) - Command-line interface
    - Entry point: `exness-preprocess` command
    - Commands for download, query, coverage operations

**Module Statistics**:

To get current line counts and metrics on-demand:
```bash
make module-stats       # Show current line counts
make module-complexity  # Show cyclomatic complexity (requires radon)
make module-deps        # Show dependency tree (requires pipdeptree)
```

See [`Makefile`](Makefile) for implementation details.

### Key Design Patterns

**Facade Pattern** (v1.3.0):
- **processor.py** is a thin orchestrator coordinating 7 specialized modules
- All public methods delegate to modules (no business logic in processor)
- **Separation of concerns**: Each module has single responsibility
- **SLO-based design**: All modules define SLOs (Availability, Correctness, Observability, Maintainability)
- **Zero regressions**: All 48 tests pass after 7-module extraction (53% line reduction)
- **Off-the-shelf libraries**: httpx, pandas, DuckDB, exchange_calendars (no custom implementations)

**Unified Single-File Architecture** (v2.0.0):
- ONE DuckDB file per instrument (e.g., `eurusd.duckdb`) containing all historical data
- NO monthly file separation (major change from v1.0.0)
- Incremental updates with automatic gap detection
- PRIMARY KEY constraints prevent duplicates during updates

**Phase7 30-Column OHLC Schema** (v1.5.0):
- BID-only OHLC from Raw_Spread variant
- Dual spreads: `raw_spread_avg` and `standard_spread_avg`
- Dual tick counts: `tick_count_raw_spread` and `tick_count_standard`
- Normalized metrics: `range_per_spread`, `range_per_tick`, `body_per_spread`, `body_per_tick`
- Timezone/session tracking: `ny_hour`, `london_hour`, `ny_session`, `london_session` (v1.3.0+)
- Holiday tracking: `is_us_holiday`, `is_uk_holiday`, `is_major_holiday` (v1.4.0+)
- Global exchange sessions: 10 binary flags (`is_nyse_session`, `is_lse_session`, `is_xswx_session`, `is_xfra_session`, `is_xtse_session`, `is_xnze_session`, `is_xtks_session`, `is_xasx_session`, `is_xhkg_session`, `is_xses_session`) covering 24-hour forex trading (v1.5.0)
- Generated via LEFT JOIN between Raw_Spread and Standard variants

**Self-Documentation**:
- All tables and columns have embedded `COMMENT ON` statements
- Queryable via `duckdb_tables()` and `duckdb_columns()` system functions
- Enables BI tools and IDEs to display inline help

**Data Flow** (Module-Based Architecture v1.3.0):
```
Exness Repository (monthly ZIPs)
  → gap_detector.py (discover missing months)
  → downloader.py (download Raw_Spread + Standard)
  → tick_loader.py (parse CSV from ZIP)
  → database_manager.py (append to DuckDB, PRIMARY KEY prevents duplicates)
  → ohlc_generator.py (Phase7 30-column OHLC with LEFT JOIN)
  → session_detector.py (holidays + 10 exchange sessions)
  → query_engine.py (tick/OHLC queries, date filters, resampling)
```

### Database Schema (per instrument)

Each `.duckdb` file contains:

1. **`raw_spread_ticks`** table:
   - Columns: `Timestamp` (PK), `Bid`, `Ask`
   - Exness Raw_Spread variant (~98% zero-spreads, execution prices)
   - Primary data source for OHLC construction

2. **`standard_ticks`** table:
   - Columns: `Timestamp` (PK), `Bid`, `Ask`
   - Exness Standard variant (0% zero-spreads, always Bid < Ask)
   - Reference data for spread comparison

3. **`ohlc_1m`** table:
   - **Schema**: Phase7 30-column (v1.5.0) - See [`schema.py`](src/exness_data_preprocess/schema.py)
   - **Details**: BID-only OHLC with dual-variant spreads, tick counts, normalized metrics, and 10 global exchange sessions
   - **Reference**: [`DATABASE_SCHEMA.md`](docs/DATABASE_SCHEMA.md)

4. **`metadata`** table:
   - Columns: `key` (PK), `value`, `updated_at`
   - Tracks coverage (earliest_date, latest_date, etc.)

---

## Quick Links

### Documentation
- **[README.md](README.md)** - Full API reference, installation, usage examples
- **[docs/README.md](docs/README.md)** - Documentation hub with research findings
- **[docs/DATABASE_SCHEMA.md](docs/DATABASE_SCHEMA.md)** - Complete database schema with self-documentation
- **[docs/UNIFIED_DUCKDB_PLAN_v2.md](docs/UNIFIED_DUCKDB_PLAN_v2.md)** - v2.0.0 architecture specification
- **[docs/EXNESS_DATA_SOURCES.md](docs/EXNESS_DATA_SOURCES.md)** - Data source variants and URLs

### Code Examples
- **[examples/basic_usage.py](examples/basic_usage.py)** - Download, query, coverage operations
- **[examples/batch_processing.py](examples/batch_processing.py)** - Multi-instrument parallel processing

### Development
- **[CONTRIBUTING.md](CONTRIBUTING.md)** - Contribution guidelines
- **[tests/README.md](tests/README.md)** - Test suite documentation (v2.0.0 tests needed)

---

## Essential Architecture Decisions

### Unified Single-File DuckDB Storage v2.0.0 (✅ Implemented & Validated 2025-10-12)

**Decision**: Store all years of data in single DuckDB file per instrument (eurusd.duckdb, not monthly files)

**Implementation**: v2.0.0 refactoring completed
- ✅ **Single file per instrument**: eurusd.duckdb contains all years
- ✅ **Dual-variant storage**: Raw_Spread + Standard in same database
- ✅ **PRIMARY KEY constraints**: Prevents duplicates during incremental updates
- ✅ **Automatic gap detection**: Downloads only missing months
- ✅ **Phase7 30-column OHLC (v1.5.0)**: Dual spreads + dual tick counts + 10 global exchange sessions
- ✅ **Date range queries**: Sub-15ms query performance
- ✅ **On-demand resampling**: Any timeframe (5m, 1h, 1d) in <15ms

**Validation Results** (13 months, Oct 2024 - Oct 2025):
- ✅ **Raw_Spread ticks**: 18.6M ticks
- ✅ **Standard ticks**: 19.6M ticks
- ✅ **OHLC bars**: 413K bars (1-minute)
- ✅ **Database size**: 2.08 GB
- ✅ **Query performance**: <15ms for all operations
- ✅ **Incremental updates**: Working correctly (0 months added when up to date)

**Architecture Benefits**:
- **No file fragmentation**: All years in one database
- **No duplicates**: PRIMARY KEY constraints prevent duplicate data
- **Fast queries**: Date range filtering without loading entire dataset
- **Scalability**: 2.08 GB for 13 months (3 years ~4.8 GB)

**Comprehensive Plan**: [`docs/UNIFIED_DUCKDB_PLAN_v2.md`](docs/UNIFIED_DUCKDB_PLAN_v2.md) - Complete v2.0.0 specification

**Legacy Plan**: [`docs/archive/UNIFIED_DUCKDB_PLAN_v1.0.0_LEGACY.md`](docs/archive/UNIFIED_DUCKDB_PLAN_v1.0.0_LEGACY.md) - Monthly-file architecture (archived)

**Test Artifacts**:
- `/tmp/exness-duckdb-test/refactored/eurusd.duckdb` - 2.08 GB unified database
- `/tmp/exness-duckdb-test/test_refactored_processor.py` - Validation test
- `/tmp/exness-duckdb-test/test_queries_only.py` - Query validation test

### Phase7 30-Column OHLC Schema v1.5.0 (✅ Implemented)

**Decision**: Dual-variant BID-only OHLC with 30 columns capturing Raw_Spread and Standard characteristics, normalized metrics, and 10 global exchange sessions

**Schema**: Phase7 30-column (v1.5.0)
- **Definition**: See [`schema.py`](src/exness_data_preprocess/schema.py)
- **Documentation**: See [`DATABASE_SCHEMA.md`](docs/DATABASE_SCHEMA.md)
- **Architecture**: Exchange Registry Pattern for dynamic session column generation

**Key Features**:
- ✅ **BID-only OHLC**: Uses Raw_Spread Bid prices (execution prices)
- ✅ **Dual spreads**: Tracks both Raw_Spread (zero-spreads) and Standard (market spreads)
- ✅ **Dual tick counts**: Records tick counts from both variants
- ✅ **Normalized metrics** (v1.2.0): range_per_spread, range_per_tick, body_per_spread, body_per_tick
- ✅ **Timezone/session tracking** (v1.3.0): ny_hour, london_hour, ny_session, london_session with automatic DST handling
- ✅ **Holiday tracking** (v1.4.0): is_us_holiday, is_uk_holiday, is_major_holiday via exchange_calendars
- ✅ **10 Global Exchange Sessions** (v1.5.0): is_nyse_session, is_lse_session, is_xswx_session, is_xfra_session, is_xtse_session, is_xnze_session, is_xtks_session, is_xasx_session, is_xhkg_session, is_xses_session covering 24-hour forex trading
- ✅ **LEFT JOIN methodology**: Raw_Spread primary, Standard reference

**Implementation**:
- **OHLC Generation**: [`src/exness_data_preprocess/ohlc_generator.py`](src/exness_data_preprocess/ohlc_generator.py)
- **Session Detection**: [`src/exness_data_preprocess/session_detector.py`](src/exness_data_preprocess/session_detector.py)
- **Orchestration**: [`src/exness_data_preprocess/processor.py`](src/exness_data_preprocess/processor.py) (lines 317-326, delegation)

**Specification**: [`docs/research/eurusd-zero-spread-deviations/data/plan/phase7_bid_ohlc_construction_v1.1.0.md`](docs/research/eurusd-zero-spread-deviations/data/plan/phase7_bid_ohlc_construction_v1.1.0.md)

**Complete Schema Details**: [`docs/DATABASE_SCHEMA.md`](docs/DATABASE_SCHEMA.md)

### DuckDB Self-Documentation (✅ Implemented)

**Decision**: Use DuckDB's `COMMENT ON` statements to store metadata inside the database

**Implementation**: All tables and columns have embedded documentation
- ✅ **Table comments**: Purpose, data source URLs, characteristics
- ✅ **Column comments**: Type, constraints, nullability explanations
- ✅ **Machine-readable**: Query via `duckdb_tables()`, `duckdb_columns()`
- ✅ **Version-controlled**: Comments stored in database schema

**Benefits**:
- **Self-documenting**: Anyone connecting to database can query metadata
- **Single source of truth**: Documentation lives with the data
- **Tool integration**: BI tools and IDEs can display inline help
- **No external docs needed**: Schema is fully self-explanatory

**Query Examples**:
```sql
-- Get all table comments
SELECT table_name, comment FROM duckdb_tables();

-- Get all column comments with types
SELECT table_name, column_name, data_type, comment FROM duckdb_columns();
```

**Implementation**: [`src/exness_data_preprocess/database_manager.py`](src/exness_data_preprocess/database_manager.py) (schema comments added automatically via get_or_create_db method)

**Complete Schema Reference**: [`docs/DATABASE_SCHEMA.md`](docs/DATABASE_SCHEMA.md) - Human-readable documentation with introspection queries

---

## Exness Data Sources

**Source**: https://ticks.ex2archive.com/ - Public tick data repository with 4 variants per instrument

**Phase7 Uses**:
- **Primary**: Raw_Spread variant (97.81% zero-spreads, execution prices)
- **Reference**: Standard variant (0% zero-spreads, traditional quotes)

**Key Characteristics**:
- Monthly ZIP files with microsecond-precision CSV tick data
- Institutional ECN/STP quality
- Fixed URL pattern: `https://ticks.ex2archive.com/ticks/{VARIANT}/{YEAR}/{MONTH}/`

**Complete Guide**: [`docs/EXNESS_DATA_SOURCES.md`](docs/EXNESS_DATA_SOURCES.md) - All 4 variants, URL patterns, download examples

---

## Research Areas

### Zero-Spread Deviation Analysis

**Research Period**: Sep 2024 baseline + 16-month validation (Jan-Aug 2024+2025)

**Key Findings**:
- ✅ **Mean Reversion**: 87.3% ± 1.9% stable across 16 months
- ⚠️ **Volatility Prediction**: Regime shift between 2024 (R²=0.371) and 2025 (R²=0.209)
- ✅ **Phase7 Methodology**: Dual-variant BID-only OHLC construction validated

**Documentation**: [`docs/research/eurusd-zero-spread-deviations/README.md`](docs/research/eurusd-zero-spread-deviations/README.md)

**Methodology**: [`docs/research/eurusd-zero-spread-deviations/01-methodology.md`](docs/research/eurusd-zero-spread-deviations/01-methodology.md)

### Compression Benchmarks

**Decision**: DuckDB native storage (no Parquet files in v2.0.0)

**Legacy Benchmarks** (v1.0.0): Parquet Zstd-22 over Brotli-11 (too slow) and Delta Encoding (lossy)

**Documentation**: [`docs/research/compression-benchmarks/README.md`](docs/research/compression-benchmarks/README.md)

---

## Current Implementation Status

### v2.0.0 Architecture (✅ Completed 2025-10-12)

- ✅ **Unified single-file DuckDB** - One file per instrument (eurusd.duckdb)
- ✅ **Dual-variant storage** - Raw_Spread + Standard in same database
- ✅ **PRIMARY KEY constraints** - Prevents duplicates during incremental updates
- ✅ **Automatic gap detection** - Downloads only missing months
- ✅ **Phase7 30-column OHLC (v1.5.0)** - Dual spreads + dual tick counts + 10 global exchange sessions
- ✅ **Date range queries** - Sub-15ms query performance
- ✅ **On-demand resampling** - Any timeframe in <15ms
- ✅ **SQL filter support** - Direct SQL WHERE clauses on ticks
- ✅ **API refactoring** - Clean unified API
- ✅ **Examples updated** - basic_usage.py, batch_processing.py
- ✅ **Documentation updated** - README.md, CLAUDE.md, docs/README.md

### Usage Examples

**Basic Operations**: [`examples/basic_usage.py`](examples/basic_usage.py) - Download, query, coverage

**Batch Processing**: [`examples/batch_processing.py`](examples/batch_processing.py) - Multi-instrument, parallel processing

**Complete API Reference**: [`README.md`](README.md) - All methods, parameters, and usage patterns

### Pending Tasks

- ⏳ **CLI enhancements** - Add variant selection, OHLC resampling commands
- ⏳ **Test suite** - Update test_processor.py, test_api.py, test_cli.py for v2.0.0
- ⏳ **API expansion** - Add streaming query methods, batch operations

---

## File Locations

**Project Root**: `/Users/terryli/eon/exness-data-preprocess/`

**Data Storage** (default): `~/eon/exness-data/`
```
~/eon/exness-data/
├── eurusd.duckdb      # Single file for all EURUSD data
├── gbpusd.duckdb      # Single file for all GBPUSD data
├── xauusd.duckdb      # Single file for all XAUUSD data
└── temp/
    └── (temporary ZIP files)
```

**Database Schema** (per instrument):
```
eurusd.duckdb:
├── raw_spread_ticks   # Timestamp (PK), Bid, Ask
├── standard_ticks     # Timestamp (PK), Bid, Ask
├── ohlc_1m            # Phase7 30-column schema (v1.5.0)
└── metadata           # Coverage tracking
```

**Test Artifacts**: `/tmp/exness-duckdb-test/`
- `refactored/eurusd.duckdb` - 2.08 GB unified database (13 months)
- `test_refactored_processor.py` - Validation test
- `test_queries_only.py` - Query validation test

---

## Migration from v1.0.0

**v1.0.0 (Legacy)**:
- Monthly DuckDB files: `eurusd_ohlc_2024_08.duckdb`
- Parquet tick storage: `eurusd_ticks_2024_08.parquet`
- Functions: `process_month()`, `process_date_range()`, `analyze_ticks()`

**v2.0.0 (Current)**:
- Single DuckDB file: `eurusd.duckdb`
- No Parquet files (everything in DuckDB)
- Unified API: `processor.update_data()`, `processor.query_ohlc()`, `processor.query_ticks()`

**Migration Steps**:
1. Run `processor.update_data(pair, start_date)` to create new unified database
2. Delete old monthly files: `rm eurusd_ohlc_2024_*.duckdb eurusd_ticks_2024_*.parquet`
3. Update code to use new API methods

---

## References

- **Exness Data**: https://ticks.ex2archive.com/
- **Official Exness**: https://www.exness.com/tick-history/ (Cloudflare protected)
- **DuckDB**: https://duckdb.org/
- **Apache Parquet**: https://parquet.apache.org/
- **Zstd Compression**: https://facebook.github.io/zstd/

---

**Version**: 2.0.0 (Architecture) + 1.3.0 (Implementation)
**Last Updated**: 2025-10-15
**Architecture**: Unified Single-File DuckDB Storage with Incremental Updates
**Implementation**: Facade Pattern with 7 Specialized Modules (Phase 1-4 Complete)
