# exness-data-preprocess v2.0.0

Forex tick data preprocessing with ClickHouse backend. Downloads, stores, and queries tick data from Exness public repository.

## Data Inventory (Validated 2025-12-28)

| Instrument | raw_spread_ticks | standard_ticks | ohlc_1m   | Date Range              |
| ---------- | ---------------- | -------------- | --------- | ----------------------- |
| EURUSD     | 56,687,313       | 62,203,144     | 1,466,724 | 2022-01-02 → 2025-12-26 |
| XAUUSD     | 166,820,410      | 167,871,871    | 1,401,953 | 2022-01-02 → 2025-12-26 |

**Total**: 453.6M ticks, 2.87M OHLC bars in 5.99 GiB

## Requirements

- Python 3.11+
- ClickHouse running on `localhost:8123`

## Verify ClickHouse

```bash
# Check ClickHouse is running
clickhouse client --query "SELECT version()"

# Check exness database exists
clickhouse client --query "SELECT count() FROM exness.raw_spread_ticks"
```

## Installation

```bash
# Using uv
uv pip install exness-data-preprocess

# From source
git clone https://github.com/Eon-Labs/exness-data-preprocess.git
cd exness-data-preprocess
uv sync
```

## Python API

```python
import exness_data_preprocess as edp

# Context manager (recommended)
with edp.ExnessDataProcessor() as processor:
    # Query ticks
    df = processor.query_ticks('EURUSD', 'raw_spread', '2024-01-01', '2024-01-31')

    # Query OHLC
    df = processor.query_ohlc('EURUSD', '1m', '2024-01-01', '2024-01-31')

    # Get coverage info
    cov = processor.get_data_coverage('EURUSD')

    # Download new data (incremental)
    result = processor.update_data('EURUSD', start_date='2022-01-01')
```

### API Methods

| Method                                              | Parameters                                     | Returns      |
| --------------------------------------------------- | ---------------------------------------------- | ------------ |
| `query_ticks(pair, variant, start_date, end_date)`  | variant: `raw_spread` or `standard`            | DataFrame    |
| `query_ohlc(pair, timeframe, start_date, end_date)` | timeframe: `1m`, `5m`, `15m`, `1h`, `4h`, `1d` | DataFrame    |
| `get_data_coverage(pair)`                           |                                                | CoverageInfo |
| `update_data(pair, start_date, delete_zip=True)`    |                                                | UpdateResult |

### Return Models

```python
# UpdateResult
result.months_added        # int: months downloaded
result.raw_ticks_added     # int: raw spread ticks added
result.standard_ticks_added # int: standard ticks added
result.ohlc_bars           # int: OHLC bars generated
result.storage_bytes       # int: storage used

# CoverageInfo
cov.raw_spread_ticks       # int: total raw spread ticks
cov.standard_ticks         # int: total standard ticks
cov.ohlc_bars              # int: total OHLC bars
cov.earliest_date          # str: earliest timestamp
cov.latest_date            # str: latest timestamp
cov.storage_bytes          # int: storage used
```

## Direct SQL Access

```bash
# Count ticks
clickhouse client --query "SELECT count() FROM exness.raw_spread_ticks WHERE instrument='EURUSD'"

# Query tick data
clickhouse client --query "
SELECT timestamp, bid, ask
FROM exness.raw_spread_ticks
WHERE instrument='EURUSD'
  AND timestamp >= '2024-01-01'
  AND timestamp < '2024-01-02'
LIMIT 10"

# Query OHLC
clickhouse client --query "
SELECT timestamp, open, high, low, close
FROM exness.ohlc_1m
WHERE instrument='EURUSD'
  AND timestamp >= '2024-01-01'
LIMIT 10"

# Resample to 1h
clickhouse client --query "
SELECT
    toStartOfHour(timestamp) AS ts,
    argMin(open, timestamp) AS open,
    max(high) AS high,
    min(low) AS low,
    argMax(close, timestamp) AS close
FROM exness.ohlc_1m
WHERE instrument='EURUSD' AND timestamp >= '2024-01-01'
GROUP BY ts
ORDER BY ts"
```

## Schema

### Tick Tables

`exness.raw_spread_ticks`, `exness.standard_ticks`:

| Column     | Type                   | Codec               |
| ---------- | ---------------------- | ------------------- |
| instrument | LowCardinality(String) | -                   |
| timestamp  | DateTime64(6, 'UTC')   | DoubleDelta, LZ4    |
| bid        | Float64                | Gorilla(8), ZSTD(1) |
| ask        | Float64                | Gorilla(8), ZSTD(1) |

### OHLC Table

`exness.ohlc_1m` (27 columns):

| Category    | Columns                                                                                                                                                                 |
| ----------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Core        | instrument, timestamp, open, high, low, close                                                                                                                           |
| Spreads     | raw_spread_avg, standard_spread_avg                                                                                                                                     |
| Tick counts | tick_count_raw_spread, tick_count_standard                                                                                                                              |
| Timezone    | ny_hour, london_hour, ny_session, london_session                                                                                                                        |
| Holidays    | is_us_holiday, is_uk_holiday, is_major_holiday                                                                                                                          |
| Sessions    | is_nyse_session, is_lse_session, is_xswx_session, is_xfra_session, is_xtse_session, is_xnze_session, is_xtks_session, is_xasx_session, is_xhkg_session, is_xses_session |

Engine: `ReplacingMergeTree` (automatic deduplication)

Partition: `toYYYYMM(timestamp)`

Order: `(instrument, timestamp)`

## Data Source

- URL: <https://ticks.ex2archive.com/>
- Format: Monthly ZIP files with CSV tick data
- Variants: Raw_Spread (zero spreads) + Standard (market spreads)
- Precision: Microsecond timestamps

## Development

```bash
# Setup
uv sync --dev

# Test
uv run pytest

# Lint
uv run ruff check --fix .

# Type check
uv run mypy src/
```

## Documentation

- [ClickHouse User Guide](/docs/CLICKHOUSE_USER_GUIDE.md) - Detailed ClickHouse usage
- [Database Schema](/docs/DATABASE_SCHEMA.md) - 27-column OHLC specification
- [Module Architecture](/docs/MODULE_ARCHITECTURE.md) - 13 modules with SLOs
- [ADR: ClickHouse Migration](/docs/adr/2025-12-11-duckdb-removal-clickhouse.md) - Architecture decision

## License

MIT
