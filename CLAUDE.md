# exness-data-preprocess - Project Memory

**Architecture**: Professional forex tick data preprocessing with unified single-file DuckDB storage

**Full Documentation**: [`README.md`](README.md) - Installation, usage, API reference

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
- **[examples/add_schema_comments.py](examples/add_schema_comments.py)** - Retrofit self-documentation

### Development
- **[CONTRIBUTING.md](CONTRIBUTING.md)** - Contribution guidelines
- **[tests/README.md](tests/README.md)** - Test suite documentation

---

## Essential Architecture Decisions

### Unified Single-File DuckDB Storage v2.0.0 (✅ Implemented & Validated 2025-10-12)

**Decision**: Store all years of data in single DuckDB file per instrument (eurusd.duckdb, not monthly files)

**Implementation**: v2.0.0 refactoring completed
- ✅ **Single file per instrument**: eurusd.duckdb contains all years
- ✅ **Dual-variant storage**: Raw_Spread + Standard in same database
- ✅ **PRIMARY KEY constraints**: Prevents duplicates during incremental updates
- ✅ **Automatic gap detection**: Downloads only missing months
- ✅ **Phase7 9-column OHLC**: Dual spreads + dual tick counts
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

### Phase7 9-Column OHLC Schema (✅ Implemented)

**Decision**: Dual-variant BID-only OHLC with 9 columns capturing both Raw_Spread and Standard characteristics

**Schema**: `Timestamp | Open | High | Low | Close | raw_spread_avg | standard_spread_avg | tick_count_raw_spread | tick_count_standard`

**Key Features**:
- ✅ **BID-only OHLC**: Uses Raw_Spread Bid prices (execution prices)
- ✅ **Dual spreads**: Tracks both Raw_Spread (zero-spreads) and Standard (market spreads)
- ✅ **Dual tick counts**: Records tick counts from both variants
- ✅ **LEFT JOIN methodology**: Raw_Spread primary, Standard reference

**Implementation**: [`src/exness_data_preprocess/processor.py`](src/exness_data_preprocess/processor.py) (lines 453-485)

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

**Retrofit Methods**:
- `add_schema_comments(pair)` - Add comments to single database
- `add_schema_comments_all()` - Batch-update all databases

**Implementation**: [`src/exness_data_preprocess/processor.py`](src/exness_data_preprocess/processor.py) (lines 138-215, 698-797)

**Usage Example**: [`examples/add_schema_comments.py`](examples/add_schema_comments.py)

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

## Development Setup

**Quick Start**:
```bash
git clone https://github.com/Eon-Labs/exness-data-preprocess.git
cd exness-data-preprocess
uv sync --dev
```

**Complete Setup Guide**: [`README.md`](README.md) - Installation, testing, code quality, building

**Contributing**: [`CONTRIBUTING.md`](CONTRIBUTING.md) - Contribution guidelines and workflow

---

## Current Implementation Status

### v2.0.0 Architecture (✅ Completed 2025-10-12)

- ✅ **Unified single-file DuckDB** - One file per instrument (eurusd.duckdb)
- ✅ **Dual-variant storage** - Raw_Spread + Standard in same database
- ✅ **PRIMARY KEY constraints** - Prevents duplicates during incremental updates
- ✅ **Automatic gap detection** - Downloads only missing months
- ✅ **Phase7 9-column OHLC** - Dual spreads + dual tick counts
- ✅ **Date range queries** - Sub-15ms query performance
- ✅ **On-demand resampling** - Any timeframe in <15ms
- ✅ **SQL filter support** - Direct SQL WHERE clauses on ticks
- ✅ **API refactoring** - Clean unified API
- ✅ **Examples updated** - basic_usage.py, batch_processing.py
- ✅ **Documentation updated** - README.md, CLAUDE.md, docs/README.md

### Usage Examples

**Basic Operations**: [`examples/basic_usage.py`](examples/basic_usage.py) - Download, query, coverage

**Batch Processing**: [`examples/batch_processing.py`](examples/batch_processing.py) - Multi-instrument, parallel processing

**Schema Comments**: [`examples/add_schema_comments.py`](examples/add_schema_comments.py) - Retrofit self-documentation to existing databases

**Complete API Reference**: [`README.md`](README.md) - All methods, parameters, and usage patterns

### Pending Tasks

- ⏳ **CLI enhancements** - Add variant selection, OHLC resampling commands
- ⏳ **Test suite** - Update test_processor.py, test_api.py, test_cli.py for v2.0.0
- ⏳ **API expansion** - Add streaming query methods, batch operations

---

## File Locations

**Project Root**: `/Users/terryli/eon/exness-data-preprocess/ `

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
├── ohlc_1m            # Phase7 9-column schema
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

**Version**: 2.0.0
**Last Updated**: 2025-10-12
**Architecture**: Unified Single-File DuckDB Storage with Incremental Updates
