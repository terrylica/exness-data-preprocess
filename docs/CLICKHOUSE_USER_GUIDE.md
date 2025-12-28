# ClickHouse User Guide - exness-data-preprocess v2.0.0

**Package**: `exness-data-preprocess` - Professional forex tick data preprocessing with ClickHouse backend

**Backend**: ClickHouse (columnar storage with ReplacingMergeTree deduplication)

**Database**: `exness` (single database for all instruments)

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [ClickHouse Connection](#clickhouse-connection)
3. [ExnessDataProcessor API](#exnessdataprocessor-api)
4. [Querying Tick Data](#querying-tick-data)
5. [Querying OHLC Data](#querying-ohlc-data)
6. [Data Coverage](#data-coverage)
7. [Updating Data](#updating-data)
8. [26-Column OHLC Schema](#26-column-ohlc-schema)
9. [Direct ClickHouse SQL Patterns](#direct-clickhouse-sql-patterns)
10. [mise Tasks for ClickHouse](#mise-tasks-for-clickhouse)
11. [Environment Configuration](#environment-configuration)
12. [Pagination Patterns](#pagination-patterns)
13. [Troubleshooting](#troubleshooting)

---

## Quick Start

```python
import exness_data_preprocess as edp

# Initialize processor (requires ClickHouse on localhost:8123)
processor = edp.ExnessDataProcessor()

# Download 3 years of EURUSD data
result = processor.update_data(
    pair="EURUSD",
    start_date="2022-01-01",
    delete_zip=True,
)

print(f"Months added:     {result.months_added}")
print(f"Raw_Spread ticks: {result.raw_ticks_added:,}")
print(f"Standard ticks:   {result.standard_ticks_added:,}")
print(f"OHLC bars:        {result.ohlc_bars:,}")

# Query OHLC data
df_ohlc = processor.query_ohlc(
    pair="EURUSD",
    timeframe="1h",
    start_date="2024-01-01",
    end_date="2024-01-31",
)

# Clean up
processor.close()
```

---

## ClickHouse Connection

### Local Mode (Default)

```bash
# Start ClickHouse server
mise run clickhouse:start

# Verify connection
mise run clickhouse:status
```

Default connection: `localhost:8123` (HTTP interface)

### Cloud Mode

Set environment variables for ClickHouse Cloud:

```bash
export CLICKHOUSE_MODE=cloud
export CLICKHOUSE_HOST=your-instance.clickhouse.cloud
export CLICKHOUSE_PORT=8443
export CLICKHOUSE_USER=default
export CLICKHOUSE_PASSWORD=your-password
```

### Direct Client Access

```python
from exness_data_preprocess import get_clickhouse_client

# Create client (uses environment variables)
client = get_clickhouse_client()

# Execute query
result = client.query("SELECT version()")
print(f"ClickHouse version: {result.first_row[0]}")

# Close when done
client.close()
```

---

## ExnessDataProcessor API

### Initialization

```python
import exness_data_preprocess as edp

# Context manager (recommended - auto-closes connection)
with edp.ExnessDataProcessor() as processor:
    df = processor.query_ticks("EURUSD", start_date="2024-01-01")
    # Connection automatically closed

# Manual management
processor = edp.ExnessDataProcessor()
# ... use processor ...
processor.close()
```

### Available Methods

| Method                  | Description                         | Returns           |
| ----------------------- | ----------------------------------- | ----------------- |
| `update_data()`         | Download and insert missing months  | `UpdateResult`    |
| `query_ticks()`         | Query tick data with date range     | `pd.DataFrame`    |
| `query_ohlc()`          | Query OHLC with optional resampling | `pd.DataFrame`    |
| `get_data_coverage()`   | Get coverage statistics             | `CoverageInfo`    |
| `get_available_dates()` | Get earliest/latest dates           | `tuple[str, str]` |
| `close()`               | Close ClickHouse connection         | `None`            |

### Supported Values

```python
from exness_data_preprocess import supported_pairs, supported_timeframes, supported_variants

# Currency pairs
print(supported_pairs())
# ('EURUSD', 'GBPUSD', 'XAUUSD', 'USDJPY', 'AUDUSD', 'USDCAD', 'NZDUSD', 'EURGBP', 'EURJPY', 'GBPJPY')

# Timeframes (1m stored, others resampled on-demand)
print(supported_timeframes())
# ('1m', '5m', '15m', '30m', '1h', '4h', '1d')

# Data variants
print(supported_variants())
# ('raw_spread', 'standard')
```

---

## Querying Tick Data

### Basic Tick Query

```python
# Query Raw_Spread ticks for January 2024
df = processor.query_ticks(
    pair="EURUSD",
    variant="raw_spread",
    start_date="2024-01-01",
    end_date="2024-01-31",
)

print(f"Ticks: {len(df):,}")
print(f"Columns: {list(df.columns)}")
# ['timestamp', 'bid', 'ask']
```

### Query Standard Ticks

```python
# Query Standard ticks (0% zero-spreads, traditional quotes)
df_std = processor.query_ticks(
    pair="EURUSD",
    variant="standard",
    start_date="2024-09-01",
    end_date="2024-09-30",
)

# Calculate spread statistics
df_std['spread'] = df_std['ask'] - df_std['bid']
print(f"Mean spread: {df_std['spread'].mean() * 10000:.4f} pips")
```

### Query with Limit

```python
# Get first 1000 ticks only
df = processor.query_ticks(
    pair="EURUSD",
    variant="raw_spread",
    limit=1000,
)
```

---

## Querying OHLC Data

### Basic OHLC Query (1m - stored)

```python
# Query pre-computed 1-minute bars
df_1m = processor.query_ohlc(
    pair="EURUSD",
    timeframe="1m",
    start_date="2024-01-01",
    end_date="2024-01-31",
)
print(f"1m bars: {len(df_1m):,}")
```

### On-Demand Resampling

Timeframes other than 1m are resampled on-the-fly (<15ms):

```python
# Resample to 1-hour bars
df_1h = processor.query_ohlc(
    pair="EURUSD",
    timeframe="1h",
    start_date="2024-01-01",
    end_date="2024-03-31",
)

# Resample to daily bars
df_1d = processor.query_ohlc(
    pair="EURUSD",
    timeframe="1d",
    start_date="2024-01-01",
    end_date="2024-12-31",
)

print(f"1h bars: {len(df_1h):,}")
print(f"1d bars: {len(df_1d):,}")
```

### Available Timeframes

| Timeframe | Description    | Storage                   |
| --------- | -------------- | ------------------------- |
| `1m`      | 1-minute bars  | Stored in `ohlc_1m` table |
| `5m`      | 5-minute bars  | Resampled on-demand       |
| `15m`     | 15-minute bars | Resampled on-demand       |
| `30m`     | 30-minute bars | Resampled on-demand       |
| `1h`      | 1-hour bars    | Resampled on-demand       |
| `4h`      | 4-hour bars    | Resampled on-demand       |
| `1d`      | Daily bars     | Resampled on-demand       |

---

## Data Coverage

### Get Coverage Statistics

```python
coverage = processor.get_data_coverage("EURUSD")

print(f"Database:         {coverage.database}")
print(f"Raw_Spread ticks: {coverage.raw_spread_ticks:,}")
print(f"Standard ticks:   {coverage.standard_ticks:,}")
print(f"OHLC bars:        {coverage.ohlc_bars:,}")
print(f"Date range:       {coverage.earliest_date} to {coverage.latest_date}")
print(f"Days covered:     {coverage.date_range_days}")
print(f"Storage:          {coverage.storage_bytes:,} bytes")
```

### CoverageInfo Fields

| Field              | Type  | Description                         |
| ------------------ | ----- | ----------------------------------- | ---------------------------------- |
| `database`         | `str` | ClickHouse database name (`exness`) |
| `raw_spread_ticks` | `int` | Total Raw_Spread tick count         |
| `standard_ticks`   | `int` | Total Standard tick count           |
| `ohlc_bars`        | `int` | Total 1-minute OHLC bars            |
| `earliest_date`    | `str  | None`                               | Earliest data timestamp (ISO 8601) |
| `latest_date`      | `str  | None`                               | Latest data timestamp (ISO 8601)   |
| `date_range_days`  | `int` | Calendar days of coverage           |
| `storage_bytes`    | `int` | Total storage in bytes              |

### Computed Properties

```python
# Total ticks across both variants
print(f"Total ticks: {coverage.total_ticks:,}")

# Coverage percentage estimate
print(f"Coverage: {coverage.coverage_percentage:.1f}%")

# Storage efficiency
print(f"Efficiency: {coverage.storage_efficiency_mb_per_million_ticks:.2f} MB/M ticks")
```

---

## Updating Data

### Initial Download

```python
# Download 3 years of history
result = processor.update_data(
    pair="EURUSD",
    start_date="2022-01-01",
    delete_zip=True,  # Clean up ZIP files after processing
)

print(f"Months added: {result.months_added}")
print(f"Raw_Spread ticks: {result.raw_ticks_added:,}")
print(f"Standard ticks: {result.standard_ticks_added:,}")
```

### Incremental Updates

```python
# Run again - only downloads new months since last update
result = processor.update_data(
    pair="EURUSD",
    start_date="2022-01-01",
)
print(f"Months added: {result.months_added} (0 if up to date)")
```

### Dry-Run Mode

Preview what would be downloaded without executing:

```python
result = processor.update_data(
    pair="EURUSD",
    start_date="2024-01-01",
    dry_run=True,
)

print(f"Would download: {result.would_download_months} months")
print(f"Estimated ticks: {result.estimated_total_ticks:,}")
print(f"Estimated size: {result.estimated_size_mb:.1f} MB")
print(f"Gap months: {', '.join(result.gap_months)}")
```

### UpdateResult Fields

| Field                  | Type  | Description                    |
| ---------------------- | ----- | ------------------------------ |
| `database`             | `str` | ClickHouse database name       |
| `months_added`         | `int` | Months successfully downloaded |
| `raw_ticks_added`      | `int` | Raw_Spread ticks inserted      |
| `standard_ticks_added` | `int` | Standard ticks inserted        |
| `ohlc_bars`            | `int` | Total OHLC bars after update   |
| `storage_bytes`        | `int` | Total storage in bytes         |

---

## 26-Column OHLC Schema

The `ohlc_1m` table contains 26 columns organized into categories:

### Core OHLC (5 columns)

| Column      | Type            | Description                          |
| ----------- | --------------- | ------------------------------------ |
| `timestamp` | `DateTime64(6)` | Minute-aligned bar timestamp         |
| `open`      | `Float64`       | Opening price (first Raw_Spread Bid) |
| `high`      | `Float64`       | Highest Bid in minute                |
| `low`       | `Float64`       | Lowest Bid in minute                 |
| `close`     | `Float64`       | Closing price (last Raw_Spread Bid)  |

### Dual Spreads (2 columns)

| Column                | Type      | Description                    |
| --------------------- | --------- | ------------------------------ |
| `raw_spread_avg`      | `Float64` | Average Raw_Spread (Ask - Bid) |
| `standard_spread_avg` | `Float64` | Average Standard spread        |

### Dual Tick Counts (2 columns)

| Column                  | Type     | Description             |
| ----------------------- | -------- | ----------------------- |
| `tick_count_raw_spread` | `UInt32` | Raw_Spread ticks in bar |
| `tick_count_standard`   | `UInt32` | Standard ticks in bar   |

### Normalized Metrics (4 columns)

| Column             | Type      | Description                             |
| ------------------ | --------- | --------------------------------------- |
| `range_per_spread` | `Float64` | (High - Low) / standard_spread_avg      |
| `range_per_tick`   | `Float64` | (High - Low) / tick_count_standard      |
| `body_per_spread`  | `Float64` | abs(Close - Open) / standard_spread_avg |
| `body_per_tick`    | `Float64` | abs(Close - Open) / tick_count_standard |

### Timezone/Session Tracking (4 columns)

| Column           | Type     | Description                          |
| ---------------- | -------- | ------------------------------------ |
| `ny_hour`        | `UInt8`  | New York hour (0-23)                 |
| `london_hour`    | `UInt8`  | London hour (0-23)                   |
| `ny_session`     | `String` | NY session name (e.g., "NY_Session") |
| `london_session` | `String` | London session name                  |

### Holiday Detection (3 columns)

| Column             | Type    | Description                     |
| ------------------ | ------- | ------------------------------- |
| `is_us_holiday`    | `UInt8` | 1 if US holiday, 0 otherwise    |
| `is_uk_holiday`    | `UInt8` | 1 if UK holiday, 0 otherwise    |
| `is_major_holiday` | `UInt8` | 1 if major holiday (both US+UK) |

### Global Exchange Sessions (10 columns)

| Column            | Exchange    | Trading Hours                       |
| ----------------- | ----------- | ----------------------------------- |
| `is_nyse_session` | NYSE (XNYS) | 09:30-16:00 ET                      |
| `is_lse_session`  | LSE (XLON)  | 08:00-16:30 GMT                     |
| `is_xswx_session` | SIX Swiss   | 09:00-17:30 CET                     |
| `is_xfra_session` | Frankfurt   | 09:00-17:30 CET                     |
| `is_xtse_session` | TSX         | 09:30-16:00 ET                      |
| `is_xnze_session` | NZE         | 10:00-16:45 NZST                    |
| `is_xtks_session` | TSE Tokyo   | 09:00-15:30 JST (lunch 11:30-12:30) |
| `is_xasx_session` | ASX         | 10:00-16:00 AEST                    |
| `is_xhkg_session` | HKEX        | 09:30-16:00 HKT (lunch 12:00-13:00) |
| `is_xses_session` | SGX         | 09:00-17:00 SGT (lunch 12:00-13:00) |

---

## Direct ClickHouse SQL Patterns

### Connect via clickhouse-client

```bash
clickhouse client --host localhost --port 9000
```

### Query Tick Data

```sql
-- Get ticks for specific date range
SELECT timestamp, bid, ask
FROM exness.raw_spread_ticks
WHERE instrument = 'EURUSD'
  AND timestamp >= '2024-01-01'
  AND timestamp < '2024-02-01'
ORDER BY timestamp
LIMIT 1000;

-- Count zero-spread ticks
SELECT count(*) AS zero_spreads
FROM exness.raw_spread_ticks
WHERE instrument = 'EURUSD'
  AND bid = ask;

-- Calculate spread statistics by day
SELECT
    toDate(timestamp) AS day,
    count() AS tick_count,
    avg(ask - bid) * 10000 AS avg_spread_pips
FROM exness.raw_spread_ticks
WHERE instrument = 'EURUSD'
  AND timestamp >= '2024-09-01'
GROUP BY day
ORDER BY day;
```

### Query OHLC Data

```sql
-- Get 1-minute bars
SELECT *
FROM exness.ohlc_1m
WHERE instrument = 'EURUSD'
  AND timestamp >= '2024-01-01'
  AND timestamp < '2024-02-01'
ORDER BY timestamp;

-- On-demand resample to 1-hour
SELECT
    toStartOfHour(timestamp) AS ts,
    argMin(open, timestamp) AS open,
    max(high) AS high,
    min(low) AS low,
    argMax(close, timestamp) AS close,
    sum(tick_count_raw_spread) AS tick_count
FROM exness.ohlc_1m
WHERE instrument = 'EURUSD'
  AND timestamp >= '2024-01-01'
GROUP BY ts
ORDER BY ts;

-- Filter for Asian session (Tokyo, Sydney, Hong Kong, Singapore)
SELECT *
FROM exness.ohlc_1m
WHERE instrument = 'EURUSD'
  AND timestamp >= '2024-09-01'
  AND (is_xtks_session = 1 OR is_xasx_session = 1 OR is_xhkg_session = 1 OR is_xses_session = 1);

-- Find London-New York overlap
SELECT *
FROM exness.ohlc_1m
WHERE instrument = 'EURUSD'
  AND timestamp >= '2024-09-01'
  AND is_lse_session = 1
  AND is_nyse_session = 1;

-- Find high-volatility bars (range > 5 spreads)
SELECT *
FROM exness.ohlc_1m
WHERE instrument = 'EURUSD'
  AND timestamp >= '2024-09-01'
  AND range_per_spread > 5.0
ORDER BY range_per_spread DESC
LIMIT 10;
```

### Schema Introspection

```sql
-- List all tables
SHOW TABLES FROM exness;

-- Describe table schema
DESCRIBE TABLE exness.ohlc_1m;

-- Get table sizes
SELECT
    table,
    formatReadableSize(sum(bytes_on_disk)) AS size,
    sum(rows) AS rows
FROM system.parts
WHERE database = 'exness'
GROUP BY table
ORDER BY sum(bytes_on_disk) DESC;

-- Get all instruments
SELECT DISTINCT instrument
FROM exness.raw_spread_ticks
ORDER BY instrument;
```

---

## mise Tasks for ClickHouse

### Server Management

```bash
# Start ClickHouse server (mise-installed)
mise run clickhouse:start

# Stop ClickHouse server
mise run clickhouse:stop

# Check connection status
mise run clickhouse:status

# Fail fast if ClickHouse not running
mise run clickhouse:ensure
```

### Validation Tasks

```bash
# Run full E2E validation (requires ClickHouse)
mise run validate

# Validate ClickHouse schema
mise run validate:clickhouse-schema

# Validate data queries
mise run validate:clickhouse-data

# Validate pagination
mise run validate:clickhouse-pagination

# Validate OHLC queries
mise run validate:clickhouse-ohlc
```

### Quick Reference

| Task                           | Description                     |
| ------------------------------ | ------------------------------- |
| `mise run clickhouse:start`    | Start mise-installed ClickHouse |
| `mise run clickhouse:stop`     | Stop ClickHouse server          |
| `mise run clickhouse:status`   | Check Python client connection  |
| `mise run clickhouse:ensure`   | Fail fast if not running        |
| `mise run validate`            | Full E2E validation pipeline    |
| `mise run validate:clickhouse` | All ClickHouse validations      |

---

## Environment Configuration

### Environment Variables

| Variable              | Default                        | Description        |
| --------------------- | ------------------------------ | ------------------ |
| `CLICKHOUSE_MODE`     | `local`                        | `local` or `cloud` |
| `CLICKHOUSE_HOST`     | `localhost`                    | Server hostname    |
| `CLICKHOUSE_PORT`     | `8123` (local), `8443` (cloud) | HTTP port          |
| `CLICKHOUSE_USER`     | `default`                      | Username           |
| `CLICKHOUSE_PASSWORD` | (empty)                        | Password           |
| `CLICKHOUSE_DATABASE` | `exness`                       | Default database   |

### mise Configuration

Configuration is defined in `.mise.toml`:

```toml
[env]
CLICKHOUSE_NAME = "exness-clickhouse-local"
CLICKHOUSE_MODE = "local"
CLICKHOUSE_HOST = "localhost"
CLICKHOUSE_PORT = "8123"
CLICKHOUSE_DATABASE = "exness"
```

---

## Pagination Patterns

### Cursor-Based Pagination

More efficient than OFFSET for large datasets:

```python
from exness_data_preprocess import ClickHouseQueryEngine

engine = ClickHouseQueryEngine()

# First page
result = engine.query_ticks_paginated(
    "EURUSD",
    variant="raw_spread",
    page_size=100_000,
)

print(f"Got {len(result.data)} rows, has_more={result.has_more}")

# Next page
if result.has_more:
    next_result = engine.query_ticks_paginated(
        "EURUSD",
        cursor=result.next_cursor,
        page_size=100_000,
    )

engine.close()
```

### Batch Iterator

Memory-efficient iteration through large datasets:

```python
engine = ClickHouseQueryEngine()

# Process 100K ticks at a time
for batch in engine.query_ticks_batches("EURUSD", batch_size=100_000):
    print(f"Processing batch: {len(batch)} rows")
    process(batch)
    # Batch garbage collected after each iteration

engine.close()
```

### LIMIT/OFFSET Pagination

```python
# Page 1
page1 = engine.query_ticks("EURUSD", limit=1000, offset=0)

# Page 2
page2 = engine.query_ticks("EURUSD", limit=1000, offset=1000)
```

---

## Troubleshooting

### ClickHouse Not Running

```
ERROR: ClickHouse not running on port 8123
```

**Solution**:

```bash
mise run clickhouse:start
```

### Connection Refused

```
ClickHouseConnectionError: Failed to connect to ClickHouse at localhost:8123
```

**Check**:

1. ClickHouse is running: `nc -z localhost 8123`
2. Port is correct: `echo $CLICKHOUSE_PORT`
3. Firewall allows connection

### Empty Query Results

If queries return empty DataFrames:

1. Check data exists: `processor.get_data_coverage("EURUSD")`
2. Verify date range has data
3. Run update if needed: `processor.update_data("EURUSD")`

### Schema Mismatch

If OHLC columns don't match expected 26-column schema:

```bash
# Regenerate OHLC for instrument
python -c "
from exness_data_preprocess import ExnessDataProcessor
p = ExnessDataProcessor()
p.ch_ohlc_generator.regenerate_ohlc('EURUSD')
p.close()
"
```

---

## Performance Reference

### Query Performance (13 months of data)

| Operation                   | Time  |
| --------------------------- | ----- |
| Query 880K ticks (1 month)  | <15ms |
| Query 1m OHLC (1 month)     | <10ms |
| Resample 1m -> 1h (1 month) | <15ms |
| Resample 1m -> 1d (1 year)  | <20ms |

### Storage Estimates (EURUSD)

| Duration | Raw_Spread Ticks | Standard Ticks | OHLC Bars | Total Size |
| -------- | ---------------- | -------------- | --------- | ---------- |
| 1 month  | ~1.5M            | ~1.6M          | ~32K      | ~160 MB    |
| 1 year   | ~18M             | ~19M           | ~384K     | ~1.9 GB    |
| 3 years  | ~54M             | ~57M           | ~1.15M    | ~5.7 GB    |

---

**Last Updated**: 2025-12-27
**Version**: 2.0.0 (ClickHouse-only backend)
**Maintainer**: Terry Li <terry@eonlabs.com>
