# Database Schema Documentation - exness-data-preprocess v2.0.0

**Database Type**: DuckDB (embedded OLAP database)
**Architecture**: Single-file per instrument (unified multi-year storage)
**Schema Version**: 2.0.0 (Phase7 9-column OHLC)
**Last Updated**: 2025-10-12

---

## Overview

Each currency pair is stored in a **single DuckDB file** containing:
- **All historical tick data** from both variants (Raw_Spread + Standard)
- **Pre-computed 1-minute OHLC bars** with Phase7 9-column schema
- **Metadata** tracking coverage and update history

**File Naming Convention**: `{instrument_lowercase}.duckdb`

**Examples**:
- EURUSD → `eurusd.duckdb`
- XAUUSD → `xauusd.duckdb`
- GBPUSD → `gbpusd.duckdb`

**Default Location**: `~/eon/exness-data/`

---

## Table Structure

Each instrument database contains **4 tables**:

```
eurusd.duckdb
├── raw_spread_ticks      (Primary execution data)
├── standard_ticks        (Reference market data)
├── ohlc_1m              (Pre-computed OHLC bars)
└── metadata             (Coverage tracking)
```

---

## Table 1: `raw_spread_ticks`

**Purpose**: Stores execution prices from Exness Raw_Spread variant (98% zero-spreads)

**Use Case**: Primary data source for OHLC generation and execution analysis

**Data Source**: `https://ticks.ex2archive.com/ticks/EURUSD_Raw_Spread/{YEAR}/{MONTH}/`

### Schema

| Column      | Type                       | Constraints   | Description                                    |
|-------------|----------------------------|---------------|------------------------------------------------|
| `Timestamp` | TIMESTAMP WITH TIME ZONE   | PRIMARY KEY   | Microsecond-precision tick timestamp (UTC)     |
| `Bid`       | DOUBLE                     | NOT NULL      | Bid price (execution price)                    |
| `Ask`       | DOUBLE                     | NOT NULL      | Ask price (execution price)                    |

### Indexes

- **Automatic Index**: PRIMARY KEY constraint on `Timestamp` automatically creates an index for efficient queries
- No explicit index creation needed - DuckDB optimizes PRIMARY KEY columns automatically

### Constraints

- **PRIMARY KEY on Timestamp**: Ensures no duplicate ticks during incremental updates
- **NOT NULL constraints**: Ensures data integrity

### Table Comments

**Stored in Database**: The following comments are automatically added when the database is created (see `processor.py` lines 138-146).

```sql
COMMENT ON TABLE raw_spread_ticks IS
'Exness Raw_Spread variant (execution prices, ~98% zero-spreads).
 Data source: https://ticks.ex2archive.com/ticks/{SYMBOL}_Raw_Spread/{YEAR}/{MONTH}/';

-- Column comments
COMMENT ON COLUMN raw_spread_ticks.Timestamp IS 'Microsecond-precision tick timestamp (UTC)';
COMMENT ON COLUMN raw_spread_ticks.Bid IS 'Bid price (execution price)';
COMMENT ON COLUMN raw_spread_ticks.Ask IS 'Ask price (execution price)';
```

**Retrieve Comments**:
```sql
-- Query all table comments
SELECT table_name, comment FROM duckdb_tables();

-- Query column comments
SELECT table_name, column_name, data_type, comment
FROM duckdb_columns()
WHERE table_name = 'raw_spread_ticks';
```

### Characteristics

- **Zero-Spreads**: ~98% of ticks have Bid = Ask
- **Tick Frequency**: Variable (1µs to 130s intervals)
- **Monthly Volume**: ~1.2M - 2.9M ticks per month
- **Storage Size**: ~150 MB per year

### Example Data

```
Timestamp                       | Bid      | Ask
--------------------------------|----------|----------
2024-09-01 14:05:22.053000+00  | 1.10500  | 1.10500  (zero-spread)
2024-09-01 14:05:22.154000+00  | 1.10505  | 1.10505  (zero-spread)
2024-09-01 14:05:22.256000+00  | 1.10502  | 1.10503  (non-zero spread)
```

### Query Examples

```sql
-- Get all ticks for September 2024
SELECT * FROM raw_spread_ticks
WHERE Timestamp >= '2024-09-01' AND Timestamp < '2024-10-01'
ORDER BY Timestamp;

-- Count zero-spread ticks
SELECT COUNT(*) as zero_spreads
FROM raw_spread_ticks
WHERE Bid = Ask;

-- Get tick statistics
SELECT
    DATE_TRUNC('day', Timestamp) as day,
    COUNT(*) as tick_count,
    MIN(Bid) as min_bid,
    MAX(Bid) as max_bid,
    AVG(Ask - Bid) as avg_spread
FROM raw_spread_ticks
WHERE Timestamp >= '2024-09-01'
GROUP BY day
ORDER BY day;
```

---

## Table 2: `standard_ticks`

**Purpose**: Stores traditional market quotes from Exness Standard variant (0% zero-spreads)

**Use Case**: Reference data for spread comparison and position ratio calculation

**Data Source**: `https://ticks.ex2archive.com/ticks/EURUSD/{YEAR}/{MONTH}/`

### Schema

| Column      | Type                       | Constraints   | Description                                    |
|-------------|----------------------------|---------------|------------------------------------------------|
| `Timestamp` | TIMESTAMP WITH TIME ZONE   | PRIMARY KEY   | Microsecond-precision tick timestamp (UTC)     |
| `Bid`       | DOUBLE                     | NOT NULL      | Bid price (always < Ask)                       |
| `Ask`       | DOUBLE                     | NOT NULL      | Ask price (always > Bid)                       |

### Indexes

- **Automatic Index**: PRIMARY KEY constraint on `Timestamp` automatically creates an index for efficient queries
- No explicit index creation needed - DuckDB optimizes PRIMARY KEY columns automatically

### Constraints

- **PRIMARY KEY on Timestamp**: Ensures no duplicate ticks during incremental updates
- **NOT NULL constraints**: Ensures data integrity
- **Implicit constraint**: Bid < Ask (validated at application level)

### Table Comments

**Stored in Database**: The following comments are automatically added when the database is created (see `processor.py` lines 158-166).

```sql
COMMENT ON TABLE standard_ticks IS
'Exness Standard variant (traditional quotes, 0% zero-spreads, always Bid < Ask).
 Data source: https://ticks.ex2archive.com/ticks/{SYMBOL}/{YEAR}/{MONTH}/';

-- Column comments
COMMENT ON COLUMN standard_ticks.Timestamp IS 'Microsecond-precision tick timestamp (UTC)';
COMMENT ON COLUMN standard_ticks.Bid IS 'Bid price (always < Ask)';
COMMENT ON COLUMN standard_ticks.Ask IS 'Ask price (always > Bid)';
```

**Retrieve Comments**:
```sql
SELECT table_name, column_name, data_type, comment
FROM duckdb_columns()
WHERE table_name = 'standard_ticks';
```

### Characteristics

- **Zero-Spreads**: 0% (always Bid < Ask)
- **Tick Frequency**: Variable (similar to Raw_Spread)
- **Monthly Volume**: ~1.4M - 3.0M ticks per month
- **Storage Size**: ~160 MB per year

### Example Data

```
Timestamp                       | Bid      | Ask
--------------------------------|----------|----------
2024-09-01 14:05:22.053000+00  | 1.10498  | 1.10502  (spread = 0.4 pips)
2024-09-01 14:05:22.154000+00  | 1.10503  | 1.10507  (spread = 0.4 pips)
2024-09-01 14:05:22.256000+00  | 1.10500  | 1.10504  (spread = 0.4 pips)
```

### Query Examples

```sql
-- Get all ticks for September 2024
SELECT * FROM standard_ticks
WHERE Timestamp >= '2024-09-01' AND Timestamp < '2024-10-01'
ORDER BY Timestamp;

-- Calculate average spread
SELECT AVG(Ask - Bid) * 10000 as avg_spread_pips
FROM standard_ticks
WHERE Timestamp >= '2024-09-01';

-- Compare tick counts by hour
SELECT
    DATE_TRUNC('hour', Timestamp) as hour,
    COUNT(*) as tick_count
FROM standard_ticks
WHERE Timestamp >= '2024-09-01'
GROUP BY hour
ORDER BY hour;
```

---

## Table 3: `ohlc_1m`

**Purpose**: Pre-computed 1-minute OHLC bars with Phase7 9-column schema

**Use Case**: Primary data source for backtesting and technical analysis

**Generation Method**: Aggregated from `raw_spread_ticks` and `standard_ticks` tables

### Schema (Phase7 9-Column)

| Column                   | Type                       | Constraints   | Description                                           |
|--------------------------|----------------------------|---------------|-------------------------------------------------------|
| `Timestamp`              | TIMESTAMP WITH TIME ZONE   | PRIMARY KEY   | Minute-aligned bar timestamp                          |
| `Open`                   | DOUBLE                     | NOT NULL      | Opening price (first Raw_Spread Bid)                  |
| `High`                   | DOUBLE                     | NOT NULL      | High price (max Raw_Spread Bid)                       |
| `Low`                    | DOUBLE                     | NOT NULL      | Low price (min Raw_Spread Bid)                        |
| `Close`                  | DOUBLE                     | NOT NULL      | Closing price (last Raw_Spread Bid)                   |
| `raw_spread_avg`         | DOUBLE                     | NULL          | Average spread from Raw_Spread variant (NULL if no ticks) |
| `standard_spread_avg`    | DOUBLE                     | NULL          | Average spread from Standard variant (NULL if no Standard ticks for that minute) |
| `tick_count_raw_spread`  | BIGINT                     | NULL          | Number of ticks from Raw_Spread variant (NULL if no ticks) |
| `tick_count_standard`    | BIGINT                     | NULL          | Number of ticks from Standard variant (NULL if no Standard ticks for that minute) |

### Indexes

- **Automatic Index**: PRIMARY KEY constraint on `Timestamp` automatically creates an index for efficient queries
- No explicit index creation needed - DuckDB optimizes PRIMARY KEY columns automatically

### Constraints

- **PRIMARY KEY on Timestamp**: Ensures unique 1-minute bars
- **NOT NULL constraints**: Only on OHLC price columns (Open, High, Low, Close) to ensure price data integrity
- **NULLABLE columns**: Spread and tick count columns (raw_spread_avg, standard_spread_avg, tick_count_raw_spread, tick_count_standard) can be NULL when LEFT JOIN with Standard ticks yields no matches for that minute

### Table Comments

**Stored in Database**: The following comments are automatically added when the database is created (see `processor.py` lines 201-215).

```sql
COMMENT ON TABLE ohlc_1m IS
'Phase7 v1.1.0 1-minute OHLC bars (BID-only from Raw_Spread, dual-variant spreads and tick counts).
 OHLC Source: Raw_Spread BID prices. Spreads: Dual-variant (Raw_Spread + Standard).';

-- Column comments
COMMENT ON COLUMN ohlc_1m.Timestamp IS 'Minute-aligned bar timestamp';
COMMENT ON COLUMN ohlc_1m.Open IS 'Opening price (first Raw_Spread Bid)';
COMMENT ON COLUMN ohlc_1m.High IS 'High price (max Raw_Spread Bid)';
COMMENT ON COLUMN ohlc_1m.Low IS 'Low price (min Raw_Spread Bid)';
COMMENT ON COLUMN ohlc_1m.Close IS 'Closing price (last Raw_Spread Bid)';
COMMENT ON COLUMN ohlc_1m.raw_spread_avg IS 'Average spread from Raw_Spread variant (NULL if no ticks)';
COMMENT ON COLUMN ohlc_1m.standard_spread_avg IS 'Average spread from Standard variant (NULL if no Standard ticks for that minute)';
COMMENT ON COLUMN ohlc_1m.tick_count_raw_spread IS 'Number of ticks from Raw_Spread variant (NULL if no ticks)';
COMMENT ON COLUMN ohlc_1m.tick_count_standard IS 'Number of ticks from Standard variant (NULL if no Standard ticks for that minute)';
```

**Retrieve Comments**:
```sql
SELECT table_name, column_name, data_type, comment
FROM duckdb_columns()
WHERE table_name = 'ohlc_1m';
```

### Generation Query

```sql
INSERT INTO ohlc_1m
SELECT
    DATE_TRUNC('minute', r.Timestamp) as Timestamp,
    FIRST(r.Bid ORDER BY r.Timestamp) as Open,
    MAX(r.Bid) as High,
    MIN(r.Bid) as Low,
    LAST(r.Bid ORDER BY r.Timestamp) as Close,
    AVG(r.Ask - r.Bid) as raw_spread_avg,
    AVG(s.Ask - s.Bid) as standard_spread_avg,
    COUNT(r.Timestamp) as tick_count_raw_spread,
    COUNT(s.Timestamp) as tick_count_standard
FROM raw_spread_ticks r
LEFT JOIN standard_ticks s
    ON DATE_TRUNC('minute', r.Timestamp) = DATE_TRUNC('minute', s.Timestamp)
GROUP BY DATE_TRUNC('minute', r.Timestamp)
ORDER BY Timestamp;
```

### Characteristics

- **Timeframe**: 1-minute bars (minute-aligned)
- **OHLC Methodology**: BID-only from Raw_Spread variant
- **Dual Spreads**: Both Raw_Spread and Standard spreads tracked
- **Monthly Volume**: ~30K - 32K bars per month
- **Storage Size**: ~3 MB per year

### Example Data

```
Timestamp            | Open    | High    | Low     | Close   | raw_spread_avg | standard_spread_avg | tick_count_raw_spread | tick_count_standard
---------------------|---------|---------|---------|---------|----------------|---------------------|-----------------------|--------------------
2024-09-01 14:05:00  | 1.10500 | 1.10520 | 1.10495 | 1.10515 | 0.00001        | 0.00004             | 25                    | 28
2024-09-01 14:06:00  | 1.10515 | 1.10525 | 1.10510 | 1.10520 | 0.00001        | 0.00004             | 23                    | 26
2024-09-01 14:07:00  | 1.10520 | 1.10530 | 1.10515 | 1.10525 | 0.00001        | 0.00004             | 27                    | 30
```

### Query Examples

```sql
-- Get 1-minute bars for September 2024
SELECT * FROM ohlc_1m
WHERE Timestamp >= '2024-09-01' AND Timestamp < '2024-10-01'
ORDER BY Timestamp;

-- Resample to 1-hour bars
SELECT
    DATE_TRUNC('hour', Timestamp) as hour,
    FIRST(Open ORDER BY Timestamp) as Open,
    MAX(High) as High,
    MIN(Low) as Low,
    LAST(Close ORDER BY Timestamp) as Close,
    AVG(raw_spread_avg) as raw_spread_avg,
    AVG(standard_spread_avg) as standard_spread_avg,
    SUM(tick_count_raw_spread) as tick_count_raw_spread,
    SUM(tick_count_standard) as tick_count_standard
FROM ohlc_1m
WHERE Timestamp >= '2024-09-01'
GROUP BY hour
ORDER BY hour;

-- Get daily statistics
SELECT
    DATE_TRUNC('day', Timestamp) as day,
    COUNT(*) as bar_count,
    MIN(Low) as day_low,
    MAX(High) as day_high,
    AVG(raw_spread_avg) * 10000 as avg_raw_spread_pips
FROM ohlc_1m
WHERE Timestamp >= '2024-09-01'
GROUP BY day
ORDER BY day;
```

---

## Table 4: `metadata`

**Purpose**: Tracks database coverage, update history, and statistics

**Use Case**: Quick coverage checks without scanning entire database

### Schema

| Column        | Type                       | Constraints   | Description                             |
|---------------|----------------------------|---------------|-----------------------------------------|
| `key`         | VARCHAR                    | PRIMARY KEY   | Metadata key identifier                 |
| `value`       | VARCHAR                    | NOT NULL      | Metadata value (string representation)  |
| `updated_at`  | TIMESTAMP WITH TIME ZONE   | DEFAULT NOW() | Last update timestamp                   |

### Common Metadata Keys

| Key                      | Description                          | Example Value        |
|--------------------------|--------------------------------------|----------------------|
| `earliest_date`          | Earliest tick timestamp              | `2022-01-01`         |
| `latest_date`            | Latest tick timestamp                | `2025-10-12`         |
| `last_update`            | Last database update timestamp       | `2025-10-12T15:30Z`  |
| `total_months`           | Number of months of data             | `46`                 |
| `raw_spread_tick_count`  | Total Raw_Spread ticks               | `18619662`           |
| `standard_tick_count`    | Total Standard ticks                 | `19596407`           |
| `ohlc_bar_count`         | Total 1-minute OHLC bars             | `413453`             |
| `database_version`       | Schema version                       | `2.0.0`              |

### Example Data

```
key                      | value              | updated_at
-------------------------|--------------------|--------------------------
earliest_date            | 2024-09-01         | 2025-10-12 15:30:00+00
latest_date              | 2025-10-10         | 2025-10-12 15:30:00+00
last_update              | 2025-10-12T15:30Z  | 2025-10-12 15:30:00+00
total_months             | 13                 | 2025-10-12 15:30:00+00
raw_spread_tick_count    | 18619662           | 2025-10-12 15:30:00+00
standard_tick_count      | 19596407           | 2025-10-12 15:30:00+00
ohlc_bar_count           | 413453             | 2025-10-12 15:30:00+00
database_version         | 2.0.0              | 2025-10-12 15:30:00+00
```

### Query Examples

```sql
-- Get all metadata
SELECT * FROM metadata ORDER BY key;

-- Get specific metadata
SELECT value FROM metadata WHERE key = 'earliest_date';

-- Get coverage statistics
SELECT
    (SELECT value FROM metadata WHERE key = 'earliest_date') as earliest,
    (SELECT value FROM metadata WHERE key = 'latest_date') as latest,
    (SELECT value FROM metadata WHERE key = 'total_months') as months,
    (SELECT value FROM metadata WHERE key = 'raw_spread_tick_count') as raw_ticks,
    (SELECT value FROM metadata WHERE key = 'ohlc_bar_count') as ohlc_bars;
```

---

## DuckDB Introspection & Self-Documentation

**Feature**: DuckDB provides built-in metadata functions and `COMMENT ON` statements for self-documenting databases

### Querying Table Information

```sql
-- Get all tables with comments
SELECT
    schema_name,
    table_name,
    estimated_size,
    column_count,
    comment
FROM duckdb_tables()
WHERE database_name = current_database()
ORDER BY table_name;
```

### Querying Column Information

```sql
-- Get all columns with types and comments
SELECT
    table_name,
    column_name,
    data_type,
    is_nullable,
    comment
FROM duckdb_columns()
WHERE database_name = current_database()
ORDER BY table_name, column_index;
```

### Querying Constraints

```sql
-- Get all PRIMARY KEY constraints
SELECT
    table_name,
    constraint_type,
    constraint_text
FROM duckdb_constraints()
WHERE database_name = current_database()
ORDER BY table_name;
```

### Comprehensive Schema Introspection

```sql
-- Get complete schema information for a table
SELECT
    c.table_name,
    c.column_name,
    c.data_type,
    c.is_nullable,
    c.comment as column_comment,
    t.comment as table_comment,
    con.constraint_type
FROM duckdb_columns() c
LEFT JOIN duckdb_tables() t
    ON c.table_name = t.table_name
LEFT JOIN duckdb_constraints() con
    ON c.table_name = con.table_name
    AND c.column_name = ANY(string_split(con.constraint_text, ','))
WHERE c.table_name = 'raw_spread_ticks'
ORDER BY c.column_index;
```

### Benefits of Self-Documentation

1. **Machine-Readable**: BI tools, IDEs, and scripts can query metadata programmatically
2. **Version-Controlled**: Comments are stored in database schema, not external files
3. **Single Source of Truth**: Documentation lives with the data
4. **Tool Integration**: Modern database clients display inline help from comments
5. **No External Dependencies**: Schema is fully self-explanatory

### Implementation

All tables and columns have embedded documentation via `COMMENT ON` statements:
- **Table comments**: Purpose, data source URLs, characteristics
- **Column comments**: Type, constraints, nullability explanations

See `processor.py` lines 138-215 for implementation details.

---

## Table Relationships

### Conceptual Relationship Diagram

```
┌─────────────────────┐
│  raw_spread_ticks   │
│  (Primary Source)   │
│  - Timestamp (PK)   │
│  - Bid              │
│  - Ask              │
└──────────┬──────────┘
           │
           │ LEFT JOIN on DATE_TRUNC('minute', Timestamp)
           │
           ├──────────────────────────┐
           │                          │
           ▼                          ▼
┌─────────────────────┐    ┌─────────────────────┐
│  standard_ticks     │    │     ohlc_1m         │
│  (Reference)        │    │  (Pre-computed)     │
│  - Timestamp (PK)   │    │  - Timestamp (PK)   │
│  - Bid              │    │  - Open, High...    │
│  - Ask              │    │  - Dual Spreads     │
└─────────────────────┘    │  - Dual Tick Counts │
                           └─────────────────────┘
                                     │
                                     │ Tracked by
                                     ▼
                           ┌─────────────────────┐
                           │     metadata        │
                           │  (Coverage Info)    │
                           │  - key (PK)         │
                           │  - value            │
                           │  - updated_at       │
                           └─────────────────────┘
```

### Relationship Details

1. **raw_spread_ticks → ohlc_1m**: Raw_Spread ticks are aggregated to create OHLC bars
2. **standard_ticks → ohlc_1m**: Standard ticks are joined to add reference spread statistics
3. **All tables → metadata**: Metadata tracks statistics for all tables

---

## Storage Projections

### Per Instrument (EURUSD)

| Duration  | Raw_Spread Ticks | Standard Ticks | OHLC Bars | Total Size |
|-----------|------------------|----------------|-----------|------------|
| 1 month   | ~1.5M            | ~1.6M          | ~32K      | ~160 MB    |
| 1 year    | ~18M             | ~19M           | ~384K     | ~1.9 GB    |
| 3 years   | ~54M             | ~57M           | ~1.15M    | ~5.7 GB    |

### Multi-Instrument

| Instruments       | Duration | Total Size |
|-------------------|----------|------------|
| EURUSD            | 3 years  | ~5.7 GB    |
| EURUSD + XAUUSD   | 3 years  | ~11.4 GB   |
| EURUSD + XAUUSD + GBPUSD | 3 years | ~17.1 GB |

**Validation**: Based on real EURUSD data (13 months = 2.08 GB)

---

## Query Performance

### Performance Benchmarks (13 months of data)

| Operation                      | Time    | Notes                               |
|--------------------------------|---------|-------------------------------------|
| Query 880K ticks (1 month)     | <15ms   | Indexed timestamp queries           |
| Query 1m OHLC (1 month)        | <10ms   | 32K bars                            |
| Resample 1m → 1h (1 month)     | <15ms   | 32K → 720 bars                      |
| Resample 1m → 1d (1 year)      | <20ms   | 384K → 365 bars                     |
| Count all ticks                | <50ms   | Full table scan                     |
| Get coverage metadata          | <5ms    | Small metadata table                |

### Index Strategy

All tables use **Timestamp indexes** (implicitly created by PRIMARY KEY constraints) for optimal date range queries:

```sql
-- Automatically optimized by DuckDB
SELECT * FROM raw_spread_ticks
WHERE Timestamp >= '2024-09-01' AND Timestamp < '2024-10-01';
```

---

## Maintenance Operations

### Incremental Updates

When new data is added, the database automatically:
1. Downloads missing months from Exness
2. Appends ticks to `raw_spread_ticks` and `standard_ticks` (PRIMARY KEY prevents duplicates)
3. Regenerates OHLC for new date ranges
4. Updates metadata table

### OHLC Regeneration

OHLC bars are regenerated only for affected date ranges:

```sql
-- Delete old OHLC for date range
DELETE FROM ohlc_1m
WHERE Timestamp >= '2024-09-01' AND Timestamp < '2024-10-01';

-- Regenerate OHLC for date range
INSERT INTO ohlc_1m
SELECT ... FROM raw_spread_ticks r
LEFT JOIN standard_ticks s ON ...
WHERE r.Timestamp >= '2024-09-01' AND r.Timestamp < '2024-10-01';
```

### Database Integrity

- **PRIMARY KEY constraints**: Prevent duplicate ticks during incremental updates
- **NOT NULL constraints**: Applied to critical columns (Timestamp, Bid, Ask, OHLC prices) to ensure core data integrity
- **NULLABLE columns**: Spread and tick count columns in ohlc_1m allow NULL when LEFT JOIN yields no matches
- **Index maintenance**: Automatic by DuckDB

---

## Data Quality

### Validation Checks

1. **No Duplicates**: PRIMARY KEY constraints on Timestamp
2. **No Missing Minutes**: OHLC bars should have no gaps during market hours
3. **Price Sanity**: High ≥ Low, Open/Close within [Low, High]
4. **Spread Validity**: Raw_Spread avg ≥ 0 when NOT NULL, Standard avg > 0 when NOT NULL
5. **Tick Count**: Raw_Spread tick_count should be > 0 for each bar; Standard tick_count can be NULL (no matching Standard ticks for that minute)

### Known Characteristics

- **Zero-Spreads**: Raw_Spread ~98%, Standard 0%
- **Tick Frequency**: Variable (1µs to 130s intervals)
- **Market Hours**: Sunday 14:00 UTC to Friday 21:00 UTC
- **Weekend Gaps**: No ticks during market closure

---

## Access Patterns

### Read-Only Access

```python
import duckdb

# Connect in read-only mode
conn = duckdb.connect('~/eon/exness-data/eurusd.duckdb', read_only=True)

# Query data
df = conn.execute("""
    SELECT * FROM ohlc_1m
    WHERE Timestamp >= '2024-09-01'
    ORDER BY Timestamp
""").df()

conn.close()
```

### Write Access (Incremental Updates)

```python
from exness_data_preprocess import ExnessDataProcessor

processor = ExnessDataProcessor()

# Automatic incremental update
result = processor.update_data(
    pair="EURUSD",
    start_date="2022-01-01",
    delete_zip=True
)

print(f"Months added: {result['months_added']}")
```

---

## Version History

### v2.0.0 (2025-10-12)

- **Change**: Single-file per instrument (not monthly files)
- **Added**: Phase7 9-column OHLC schema
- **Added**: Dual-variant storage (Raw_Spread + Standard)
- **Added**: PRIMARY KEY constraints for duplicate prevention
- **Added**: Metadata table for coverage tracking
- **Added**: Incremental update support

### v1.0.0 (Legacy)

- **Structure**: Monthly files (eurusd_2024_09.duckdb)
- **OHLC Schema**: 7 columns (no dual spreads)
- **Variants**: Raw_Spread only
- **Updates**: Manual monthly processing

---

## Related Documentation

- **Architecture Plan**: [`UNIFIED_DUCKDB_PLAN_v2.md`](UNIFIED_DUCKDB_PLAN_v2.md)
- **Phase7 OHLC Spec**: [`research/eurusd-zero-spread-deviations/data/plan/phase7_bid_ohlc_construction_v1.1.0.md`](research/eurusd-zero-spread-deviations/data/plan/phase7_bid_ohlc_construction_v1.1.0.md)
- **Data Sources**: [`EXNESS_DATA_SOURCES.md`](EXNESS_DATA_SOURCES.md)
- **API Reference**: [`../README.md`](../README.md)
- **Examples**: [`../examples/basic_usage.py`](../examples/basic_usage.py)

---

**Last Updated**: 2025-10-12
**Maintainer**: Terry Li <terry@eonlabs.com>
**Schema Version**: 2.0.0
