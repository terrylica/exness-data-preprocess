# Exness Data Preprocess v2.0.0

[![PyPI version](https://img.shields.io/pypi/v/exness-data-preprocess.svg)](https://pypi.org/project/exness-data-preprocess/)
[![Python versions](https://img.shields.io/pypi/pyversions/exness-data-preprocess.svg)](https://pypi.org/project/exness-data-preprocess/)
[![License](https://img.shields.io/pypi/l/exness-data-preprocess.svg)](https://github.com/terrylica/exness-data-preprocess/blob/main/LICENSE)
[![CI](https://github.com/terrylica/exness-data-preprocess/workflows/CI/badge.svg)](https://github.com/terrylica/exness-data-preprocess/actions)
[![Downloads](https://img.shields.io/pypi/dm/exness-data-preprocess.svg)](https://pypi.org/project/exness-data-preprocess/)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

Professional forex tick data preprocessing with unified single-file DuckDB storage. Provides incremental updates, dual-variant storage (Raw_Spread + Standard), and Phase7 30-column OHLC schema (v1.6.0) with 10 global exchange sessions (trading hour detection) and sub-15ms query performance.

## Features

- **Unified Single-File Architecture**: One DuckDB file per instrument (eurusd.duckdb)
- **Incremental Updates**: Automatic gap detection and download only missing months
- **Dual-Variant Storage**: Raw_Spread (primary) + Standard (reference) in same database
- **Phase7 OHLC Schema**: 30-column bars (v1.6.0) with dual spreads, tick counts, normalized metrics, and 10 global exchange sessions with trading hour detection
- **Fast Queries**: Date range queries with sub-15ms performance
- **On-Demand Resampling**: Any timeframe (5m, 1h, 1d) resampled in <15ms
- **PRIMARY KEY Constraints**: Prevents duplicate data during incremental updates
- **Simple API**: Clean Python API for all operations

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

# Initialize processor
processor = edp.ExnessDataProcessor(base_dir="~/eon/exness-data")

# Download 3 years of EURUSD data (automatic gap detection)
result = processor.update_data(
    pair="EURUSD",
    start_date="2022-01-01",
    delete_zip=True,
)

print(f"Months added:  {result['months_added']}")
print(f"Raw ticks:     {result['raw_ticks_added']:,}")
print(f"Standard ticks: {result['standard_ticks_added']:,}")
print(f"OHLC bars:     {result['ohlc_bars']:,}")
print(f"Database size: {result['duckdb_size_mb']:.2f} MB")

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
DuckDB Single-File Storage (PRIMARY KEY prevents duplicates)
           ↓
Phase7 30-Column OHLC Generation (v1.6.0 - dual spreads, tick counts, normalized metrics, 10 global exchange sessions with trading hour detection)
           ↓
Query Interface (date ranges, SQL filters, on-demand resampling)
```

### Storage Format

**Single File Per Instrument**: `~/eon/exness-data/eurusd.duckdb`

**Schema**:

- `raw_spread_ticks` table: Timestamp (PK), Bid, Ask
- `standard_ticks` table: Timestamp (PK), Bid, Ask
- `ohlc_1m` table: Phase7 30-column schema (v1.6.0)
- `metadata` table: Coverage tracking

**Phase7 30-Column OHLC (v1.6.0)**:

- **Column Definitions**: See [`schema.py`](src/exness_data_preprocess/schema.py) - Single source of truth
- **Comprehensive Reference**: See [`DATABASE_SCHEMA.md`](docs/DATABASE_SCHEMA.md) - Query examples and usage patterns
- **Key Features**: BID-only OHLC with dual spreads (Raw_Spread + Standard), normalized spread metrics, and 10 global exchange sessions with trading hour detection (XNYS, XLON, XSWX, XFRA, XTSE, XNZE, XTKS, XASX, XHKG, XSES)

### Directory Structure

**Default Location**: `~/eon/exness-data/` (outside project workspace)

```
~/eon/exness-data/
├── eurusd.duckdb      # Single file for all EURUSD data
├── gbpusd.duckdb      # Single file for all GBPUSD data
├── xauusd.duckdb      # Single file for all XAUUSD data
└── temp/
    └── (temporary ZIP files)
```

**Why Single-File Per Instrument?**

- **Unified Storage**: All years in one database
- **Incremental Updates**: Automatic gap detection and download only missing months
- **No Duplicates**: PRIMARY KEY constraints prevent duplicate data
- **Fast Queries**: Date range queries with sub-15ms performance
- **Scalability**: Multi-year data in ~2 GB per instrument (3 years)

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
print(f"Months added: {result['months_added']} (0 if up to date)")
```

### Example 2: Check Data Coverage

```python
coverage = processor.get_data_coverage("EURUSD")

print(f"Database exists: {coverage['database_exists']}")
print(f"Raw_Spread ticks: {coverage['raw_spread_ticks']:,}")
print(f"Standard ticks:  {coverage['standard_ticks']:,}")
print(f"OHLC bars:       {coverage['ohlc_bars']:,}")
print(f"Date range:      {coverage['earliest_date']} to {coverage['latest_date']}")
print(f"Days covered:    {coverage['date_range_days']}")
print(f"Database size:   {coverage['duckdb_size_mb']:.2f} MB")
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
    print(f"  Months added: {result['months_added']}")
    print(f"  Database size: {result['duckdb_size_mb']:.2f} MB")
```

### Example 7: Parallel Processing

```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def process_instrument(pair, start_date):
    processor = edp.ExnessDataProcessor()
    return processor.update_data(pair=pair, start_date=start_date, delete_zip=True)

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
        print(f"{pair}: {result['months_added']} months added")
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

- **URL**: https://ticks.ex2archive.com/
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

| Feature                    | Benefit                                            |
| -------------------------- | -------------------------------------------------- |
| Single file per instrument | Unified storage, no file fragmentation             |
| PRIMARY KEY constraints    | Prevents duplicates during incremental updates     |
| Automatic gap detection    | Download only missing months                       |
| Dual-variant storage       | Raw_Spread + Standard in same database             |
| Phase7 OHLC schema         | Dual spreads + dual tick counts                    |
| Date range queries         | Efficient filtering without loading entire dataset |
| On-demand resampling       | Any timeframe in <15ms                             |
| SQL filter support         | Direct SQL WHERE clauses on ticks                  |

## API Reference

### ExnessDataProcessor

```python
processor = edp.ExnessDataProcessor(base_dir="~/eon/exness-data")
```

**Methods**:

- `update_data(pair, start_date, force_redownload=False, delete_zip=True)` - Update database with latest data
- `query_ohlc(pair, timeframe, start_date=None, end_date=None)` - Query OHLC bars
- `query_ticks(pair, variant, start_date=None, end_date=None, filter_sql=None)` - Query tick data
- `get_data_coverage(pair)` - Get coverage information

**Parameters**:

- `pair` (str): Currency pair (e.g., "EURUSD", "GBPUSD", "XAUUSD")
- `timeframe` (str): OHLC timeframe ("1m", "5m", "15m", "1h", "4h", "1d")
- `variant` (str): Tick variant ("raw_spread" or "standard")
- `start_date` (str): Start date in "YYYY-MM-DD" format
- `end_date` (str): End date in "YYYY-MM-DD" format
- `filter_sql` (str): SQL WHERE clause (e.g., "Bid > 1.11 AND Ask < 1.12")

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

## License

MIT License - see LICENSE file for details.

## Authors

- Terry Li <terry@eonlabs.com>
- Eon Labs

## Contributing

Contributions are welcome! Please see CONTRIBUTING.md for guidelines.

## Acknowledgments

- Exness for providing high-quality public tick data
- DuckDB for embedded OLAP capabilities with sub-15ms query performance

## Additional Documentation

**[📚 Complete Documentation Hub](DOCUMENTATION.md)** - Organized guide from beginner to advanced (72+ documents)

- **Basic Usage Examples**: See `examples/basic_usage.py`
- **Batch Processing**: See `examples/batch_processing.py`
- **Architecture Details**: See `docs/UNIFIED_DUCKDB_PLAN_v2.md`
- **Unit Tests**: See `tests/` directory
