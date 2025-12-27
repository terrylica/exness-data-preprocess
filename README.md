# Exness Data Preprocess v2.0.0

[![PyPI version](https://img.shields.io/pypi/v/exness-data-preprocess.svg)](https://pypi.org/project/exness-data-preprocess/)
[![Python versions](https://img.shields.io/pypi/pyversions/exness-data-preprocess.svg)](https://pypi.org/project/exness-data-preprocess/)
[![License](https://img.shields.io/pypi/l/exness-data-preprocess.svg)](https://github.com/terrylica/exness-data-preprocess/blob/main/LICENSE)
[![CI](https://github.com/terrylica/exness-data-preprocess/workflows/CI/badge.svg)](https://github.com/terrylica/exness-data-preprocess/actions)
[![Downloads](https://img.shields.io/pypi/dm/exness-data-preprocess.svg)](https://pypi.org/project/exness-data-preprocess/)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

Professional forex tick data preprocessing with ClickHouse backend. Provides efficient storage with lossless precision, incremental updates, dual-variant storage (Raw_Spread + Standard), and 26-column OHLC schema with 10 global exchange sessions.

## Features

- **ClickHouse Backend**: High-performance columnar storage with ReplacingMergeTree deduplication
- **Incremental Updates**: Automatic gap detection and download only missing months
- **Dual-Variant Storage**: Raw_Spread (primary) + Standard (reference) in same database
- **26-Column OHLC Schema**: BID-based bars with dual spreads, tick counts, timezone tracking, and 10 global exchange sessions
- **High Performance**: Vectorized session detection, SQL gap detection with complete coverage
- **Fast Queries**: Sub-15ms query performance with date range filtering
- **On-Demand Resampling**: Any timeframe (5m, 1h, 1d) resampled efficiently
- **Simple API**: Clean Python API for all operations

## Requirements

- **Python**: 3.11+
- **ClickHouse**: Running on localhost:8123 (local) or cloud instance

## Installation

```bash
# From PyPI (when published)
pip install exness-data-preprocess

# From source
git clone https://github.com/Eon-Labs/exness-data-preprocess.git
cd exness-data-preprocess
pip install -e .

# Using uv (recommended)
uv pip install exness-data-preprocess
```

## Quick Start

### Python API

```python
import exness_data_preprocess as edp

# Initialize processor (requires ClickHouse on localhost:8123)
processor = edp.ExnessDataProcessor()

# Download 3 years of EURUSD data (automatic gap detection)
result = processor.update_data(
    pair="EURUSD",
    start_date="2022-01-01",
    delete_zip=True,
)

print(f"Months added:  {result.months_added}")
print(f"Raw ticks:     {result.raw_ticks_added:,}")
print(f"Standard ticks: {result.standard_ticks_added:,}")
print(f"OHLC bars:     {result.ohlc_bars:,}")
print(f"Storage:       {result.storage_bytes:,} bytes")

# Query 1-minute OHLC bars for January 2024
df_1m = processor.query_ohlc(
    pair="EURUSD",
    timeframe="1m",
    start_date="2024-01-01",
    end_date="2024-01-31",
)
print(df_1m.head())

# Query raw tick data for September 2024
df_ticks = processor.query_ticks(
    pair="EURUSD",
    variant="raw_spread",
    start_date="2024-09-01",
    end_date="2024-09-30",
)
print(f"Ticks: {len(df_ticks):,}")

# Clean up
processor.close()
```

## Architecture v2.0.0

### Data Flow

```
Exness Public Repository (monthly ZIPs, both variants)
           ↓
    Automatic Gap Detection
           ↓
Download Only Missing Months (Raw_Spread + Standard)
           ↓
ClickHouse Storage (ReplacingMergeTree deduplication)
           ↓
26-Column OHLC Generation (dual spreads, tick counts, 10 global exchange sessions)
           ↓
Query Interface (date ranges, SQL filters, on-demand resampling)
```

### Storage Format

**ClickHouse Database**: `exness` (single database for all instruments)

**Schema**:

- `raw_spread_ticks` table: instrument, timestamp, bid, ask (ReplacingMergeTree)
- `standard_ticks` table: instrument, timestamp, bid, ask (ReplacingMergeTree)
- `ohlc_1m` table: 26-column schema with instrument column (ReplacingMergeTree)

**26-Column OHLC Schema**:

- **Core OHLC**: instrument, timestamp, open, high, low, close (BID-based)
- **Spreads**: raw_spread_avg, standard_spread_avg
- **Tick Counts**: tick_count_raw_spread, tick_count_standard
- **Timezone**: ny_hour, london_hour, ny_session, london_session
- **Holidays**: is_us_holiday, is_uk_holiday, is_major_holiday
- **Exchange Sessions**: 10 global exchanges (NYSE, LSE, XSWX, XFRA, XTSE, XNZE, XTKS, XASX, XHKG, XSES)

### ClickHouse Configuration

**Local Mode** (default):

```bash
# Start ClickHouse server
clickhouse-server

# Default connection: localhost:8123
```

**Cloud Mode** (via environment variables):

```bash
export CLICKHOUSE_MODE=cloud
export CLICKHOUSE_HOST=your-instance.clickhouse.cloud
export CLICKHOUSE_PORT=8443
export CLICKHOUSE_USER=default
export CLICKHOUSE_PASSWORD=your-password
```

**Why ClickHouse?**

- **Columnar Storage**: Optimized for analytical queries on time-series data
- **ReplacingMergeTree**: Automatic deduplication at merge time
- **Fast Queries**: Sub-15ms performance for date range queries
- **Scalability**: Handles billions of ticks efficiently
- **Cloud Ready**: Same API for local and cloud deployments

## Usage Examples

### Example 1: Initial Download and Incremental Updates

```python
import exness_data_preprocess as edp

processor = edp.ExnessDataProcessor()

# Initial download (3-year history)
result = processor.update_data(
    pair="EURUSD",
    start_date="2022-01-01",
    delete_zip=True,
)

# Run again - only downloads new months since last update
result = processor.update_data(
    pair="EURUSD",
    start_date="2022-01-01",
)
print(f"Months added: {result.months_added} (0 if up to date)")

processor.close()
```

### Example 2: Check Data Coverage

```python
coverage = processor.get_data_coverage("EURUSD")

print(f"Database:        {coverage.database}")
print(f"Raw_Spread ticks: {coverage.raw_spread_ticks:,}")
print(f"Standard ticks:  {coverage.standard_ticks:,}")
print(f"OHLC bars:       {coverage.ohlc_bars:,}")
print(f"Date range:      {coverage.earliest_date} to {coverage.latest_date}")
print(f"Days covered:    {coverage.date_range_days}")
print(f"Storage:         {coverage.storage_bytes:,} bytes")
```

### Example 3: Query OHLC with Date Ranges

```python
# Query 1-minute bars for January 2024
df_1m = processor.query_ohlc(
    pair="EURUSD",
    timeframe="1m",
    start_date="2024-01-01",
    end_date="2024-01-31",
)

# Query 1-hour bars for Q1 2024 (resampled on-demand)
df_1h = processor.query_ohlc(
    pair="EURUSD",
    timeframe="1h",
    start_date="2024-01-01",
    end_date="2024-03-31",
)

# Query daily bars for entire 2024
df_1d = processor.query_ohlc(
    pair="EURUSD",
    timeframe="1d",
    start_date="2024-01-01",
    end_date="2024-12-31",
)

print(f"1m bars: {len(df_1m):,}")
print(f"1h bars: {len(df_1h):,}")
print(f"1d bars: {len(df_1d):,}")
```

### Example 4: Query Ticks with Date Ranges

```python
# Query Raw_Spread ticks for September 2024
df_raw = processor.query_ticks(
    pair="EURUSD",
    variant="raw_spread",
    start_date="2024-09-01",
    end_date="2024-09-30",
)

print(f"Raw_Spread ticks: {len(df_raw):,}")
print(f"Columns: {list(df_raw.columns)}")

# Calculate spread statistics
df_raw['Spread'] = df_raw['Ask'] - df_raw['Bid']
print(f"Mean spread: {df_raw['Spread'].mean() * 10000:.4f} pips")
print(f"Zero-spreads: {((df_raw['Spread'] == 0).sum() / len(df_raw) * 100):.2f}%")
```

### Example 5: Query with SQL Filters

```python
# Query only zero-spread ticks
df_zero = processor.query_ticks(
    pair="EURUSD",
    variant="raw_spread",
    start_date="2024-09-01",
    end_date="2024-09-01",
    filter_sql="Bid = Ask",
)
print(f"Zero-spread ticks: {len(df_zero):,}")

# Query high-price ticks
df_high = processor.query_ticks(
    pair="EURUSD",
    variant="raw_spread",
    start_date="2024-09-01",
    end_date="2024-09-30",
    filter_sql="Bid > 1.11",
)
print(f"High-price ticks: {len(df_high):,}")
```

### Example 6: Process Multiple Instruments

```python
processor = edp.ExnessDataProcessor()

# Process multiple pairs
pairs = ["EURUSD", "GBPUSD", "XAUUSD"]

for pair in pairs:
    print(f"Processing {pair}...")
    result = processor.update_data(
        pair=pair,
        start_date="2023-01-01",
        delete_zip=True,
    )
    print(f"  Months added: {result.months_added}")
    print(f"  Storage: {result.storage_bytes:,} bytes")

processor.close()
```

### Example 7: Parallel Processing

```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def process_instrument(pair, start_date):
    processor = edp.ExnessDataProcessor()
    result = processor.update_data(pair=pair, start_date=start_date, delete_zip=True)
    processor.close()
    return result

instruments = [
    ("EURUSD", "2023-01-01"),
    ("GBPUSD", "2023-01-01"),
    ("XAUUSD", "2023-01-01"),
    ("USDJPY", "2023-01-01"),
]

with ThreadPoolExecutor(max_workers=4) as executor:
    futures = {
        executor.submit(process_instrument, pair, start_date): pair
        for pair, start_date in instruments
    }

    for future in as_completed(futures):
        pair = futures[future]
        result = future.result()
        print(f"{pair}: {result.months_added} months added")
```

## Development

### Setup

```bash
# Clone repository
git clone https://github.com/Eon-Labs/exness-data-preprocess.git
cd exness-data-preprocess

# Install with development dependencies (using uv)
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

# Run specific test
uv run pytest tests/test_processor.py -v
```

### Code Quality

```bash
# Format code
uv run ruff format .

# Lint
uv run ruff check --fix .

# Type checking
uv run mypy src/
```

### Building

```bash
# Build package
uv build

# Test installation locally
uv tool install --editable .
```

## Data Source

Data is sourced from Exness's public tick data repository:

- **URL**: <https://ticks.ex2archive.com/>
- **Format**: Monthly ZIP files with CSV tick data
- **Variants**: Raw_Spread (zero-spreads) + Standard (market spreads)
- **Content**: Timestamp, Bid, Ask prices for major forex pairs
- **Quality**: Institutional ECN/STP data with microsecond precision

## Technical Specifications

### Database Size (3-Year History, EURUSD)

| Metric           | Value                    |
| ---------------- | ------------------------ |
| Raw_Spread ticks | ~18.6M                   |
| Standard ticks   | ~19.6M                   |
| OHLC bars (1m)   | ~413K                    |
| Database size    | ~2.08 GB                 |
| Date range       | 2022-01-01 to 2025-01-10 |

### Query Performance

| Operation                  | Time  |
| -------------------------- | ----- |
| Query 880K ticks (1 month) | <15ms |
| Query 1m OHLC (1 month)    | <10ms |
| Resample to 1h (1 month)   | <15ms |
| Resample to 1d (1 year)    | <20ms |

### Architecture Benefits

| Feature                 | Benefit                                            |
| ----------------------- | -------------------------------------------------- |
| ClickHouse backend      | Columnar storage optimized for time-series         |
| ReplacingMergeTree      | Automatic deduplication at merge time              |
| Automatic gap detection | Download only missing months                       |
| Dual-variant storage    | Raw_Spread + Standard in same database             |
| 26-column OHLC schema   | Dual spreads + dual tick counts + sessions         |
| Date range queries      | Efficient filtering without loading entire dataset |
| On-demand resampling    | Any timeframe in <15ms                             |
| SQL filter support      | Direct SQL WHERE clauses on ticks                  |
| Cloud ready             | Same API for local and cloud ClickHouse            |

### Performance Optimizations (v0.5.0)

**Incremental OHLC Generation** - 7.3x speedup for updates:

- Full regeneration: 8.05s (303K bars, 7 months)
- Incremental update: 1.10s (43K new bars, 1 month)
- Implementation: Optional date-range parameters for partial regeneration
- Validation: [`docs/validation/SPIKE_TEST_RESULTS_PHASE1_2025-10-18.md`](/docs/validation/SPIKE_TEST_RESULTS_PHASE1_2025-10-18.md)

**Vectorized Session Detection** - 2.2x speedup for trading hour detection:

- Current approach: 5.99s (302K bars, 10 exchanges)
- Vectorized approach: 2.69s (302K bars, 10 exchanges)
- Combined Phase 1+2: ~16x total speedup (8.05s → 0.50s)
- Implementation: Pre-compute trading minutes, vectorized `.isin()` lookup
- SSoT: [`docs/phases/PHASE2_SESSION_VECTORIZATION_PLAN.yaml`](/docs/phases/PHASE2_SESSION_VECTORIZATION_PLAN.yaml)
- Validation: [`docs/validation/SPIKE_TEST_RESULTS_PHASE2_2025-10-18.md`](/docs/validation/SPIKE_TEST_RESULTS_PHASE2_2025-10-18.md)

**SQL Gap Detection** - Complete coverage with 46% code reduction:

- Bug fix: Python approach missed internal gaps (41 detected vs 42 actual)
- SQL EXCEPT operator detects ALL gaps (before + within + after existing data)
- Code reduced from 62 lines to 34 lines (46% reduction)
- SSoT: [`docs/phases/PHASE3_SQL_GAP_DETECTION_PLAN.yaml`](/docs/phases/PHASE3_SQL_GAP_DETECTION_PLAN.yaml)

**Release Notes**: See [`CHANGELOG.md`](/CHANGELOG.md) for complete v0.5.0 details

## API Reference

### ExnessDataProcessor

```python
processor = edp.ExnessDataProcessor()  # Requires ClickHouse on localhost:8123
```

**Methods**:

- `update_data(pair, start_date, force_redownload=False, delete_zip=True)` - Update database with latest data, returns `UpdateResult`
- `query_ohlc(pair, timeframe, start_date=None, end_date=None)` - Query OHLC bars, returns DataFrame
- `query_ticks(pair, variant, start_date=None, end_date=None, filter_sql=None)` - Query tick data, returns DataFrame
- `get_data_coverage(pair)` - Get coverage information, returns `CoverageInfo`
- `close()` - Close ClickHouse connection

**Parameters**:

- `pair` (str): Currency pair (e.g., "EURUSD", "GBPUSD", "XAUUSD")
- `timeframe` (str): OHLC timeframe ("1m", "5m", "15m", "1h", "4h", "1d")
- `variant` (str): Tick variant ("raw_spread" or "standard")
- `start_date` (str): Start date in "YYYY-MM-DD" format
- `end_date` (str): End date in "YYYY-MM-DD" format
- `filter_sql` (str): SQL WHERE clause (e.g., "bid > 1.11 AND ask < 1.12")

### Return Models (Pydantic)

**UpdateResult**:

- `database` (str): ClickHouse database name
- `months_added` (int): Number of months downloaded
- `raw_ticks_added` (int): Number of raw spread ticks added
- `standard_ticks_added` (int): Number of standard ticks added
- `ohlc_bars` (int): Number of OHLC bars generated
- `storage_bytes` (int): Total storage in bytes

**CoverageInfo**:

- `database` (str): ClickHouse database name
- `raw_spread_ticks` (int): Total raw spread tick count
- `standard_ticks` (int): Total standard tick count
- `ohlc_bars` (int): Total OHLC bar count
- `earliest_date` (str | None): Earliest data timestamp
- `latest_date` (str | None): Latest data timestamp
- `date_range_days` (int): Days of data coverage
- `storage_bytes` (int): Total storage in bytes

## Migration from v1.x

**v1.x (Legacy DuckDB)**:

- Single DuckDB file per instrument: `eurusd.duckdb`
- Fields: `duckdb_path`, `duckdb_size_mb`, `database_exists`
- Constructor: `ExnessDataProcessor(base_dir=...)`

**v2.0.0 (ClickHouse-only)**:

- ClickHouse database: `exness` (all instruments)
- Fields: `database`, `storage_bytes` (renamed)
- Constructor: `ExnessDataProcessor()` (no base_dir)
- **Requires**: ClickHouse running on localhost:8123

**BREAKING CHANGES**:

- `duckdb_path` → `database` (str, ClickHouse database name)
- `duckdb_size_mb` → `storage_bytes` (int, bytes not MB)
- `database_exists` → removed (ClickHouse always exists if connection works)
- `base_dir` parameter → removed (ClickHouse manages storage)

**Migration Steps**:

1. Install and start ClickHouse: `brew install clickhouse && clickhouse-server`
2. Update code to use new field names (`database`, `storage_bytes`)
3. Remove `base_dir` parameter from `ExnessDataProcessor()`
4. Run `processor.update_data(pair, start_date)` to populate ClickHouse
5. Delete old DuckDB files if no longer needed

## License

MIT License - see LICENSE file for details.

## Authors

- Terry Li <terry@eonlabs.com>
- Eon Labs

## Contributing

Contributions are welcome! Please see CONTRIBUTING.md for guidelines.

## Acknowledgments

- Exness for providing high-quality public tick data
- ClickHouse for high-performance columnar storage with sub-15ms query performance

## Additional Documentation

**[📚 Complete Documentation Hub](/docs/README.md)** - Organized guide from beginner to advanced (72+ documents)

- **Basic Usage Examples**: See `examples/basic_usage.py`
- **Batch Processing**: See `examples/batch_processing.py`
- **Architecture Details**: See `docs/UNIFIED_DUCKDB_PLAN_v2.md`
- **Unit Tests**: See `tests/` directory
