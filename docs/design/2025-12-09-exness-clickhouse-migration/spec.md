---
adr: /docs/adr/2025-12-09-exness-clickhouse-migration.md
status: implementing
date: 2025-12-09
author: Terry Li
---

# Design Spec: Exness Data Preprocess DuckDB to ClickHouse Migration

**ADR**: [Exness ClickHouse Migration](/docs/adr/2025-12-09-exness-clickhouse-migration.md)

## Executive Summary

Transform exness-data-preprocess from DuckDB to ClickHouse using **research-validated patterns**:

- **Single table** with `LowCardinality(String)` instrument column (70% storage reduction)
- **Parameterized Views** for data access (NOT Repository pattern)
- **Standard tables + JOINs** for lookups (NOT Dictionaries - overkill for <364 entries)
- **Comprehensive COMMENT ON** statements for AI-friendly schema (27% accuracy improvement)
- **Direct SQL** from application code
- **3-batch incremental refactoring** with commits after each batch

## Confirmed Decisions

| Decision      | Choice                               | Source                                        |
| ------------- | ------------------------------------ | --------------------------------------------- |
| Table design  | Single table + instrument column     | ClickHouse multi-tenancy best practice        |
| Data access   | Parameterized Views (NOT Repository) | ClickHouse OLAP pattern                       |
| Lookups       | **Standard tables + JOINs**          | Research: Dictionaries overkill for <364 rows |
| Refactoring   | 3 batches, modify in place           | Claude Code best practice                     |
| Deduplication | Never FINAL, scheduled OPTIMIZE      | FINAL is 100x slower (Architect skill)        |
| Timestamps    | **DoubleDelta + LZ4**                | Research: ZSTD provides no benefit for DD     |
| Floats        | Gorilla + ZSTD                       | Research: ZSTD(1) optimal for Gorilla         |
| ORDER BY      | (instrument, timestamp)              | Lowest cardinality first (instrument ~10)     |
| Schema docs   | **Comprehensive COMMENT ON**         | Research: 27% AI accuracy improvement         |

## ClickHouse-Native Architecture

**Data Flow**: Application Code → Parameterized Views → ClickHouse Tables

**Components**:

- `raw_spread_ticks` (ReplacingMergeTree)
- `standard_ticks` (ReplacingMergeTree)
- `ohlc_1m` (ReplacingMergeTree)
- `exchange_sessions` (MergeTree - standard table)
- `holidays` (MergeTree - standard table)

## Phase 1: ClickHouse Schema

### 1.1 Create Database

```sql
CREATE DATABASE IF NOT EXISTS exness;
```

### 1.2 Tick Tables

**ORDER BY Rationale**: `(instrument, timestamp)` - instrument has ~10 values (LOW cardinality), timestamp is unique (HIGH cardinality). Follows ClickHouse best practice of lowest cardinality first.

**Codec Rationale** (research-validated):

- `DateTime64`: DoubleDelta + **LZ4** (1.76x faster decompression, ZSTD provides no benefit for DoubleDelta)
- `Float64`: Gorilla + ZSTD (ZSTD(1) optimal for Gorilla-encoded floats)

```sql
CREATE TABLE exness.raw_spread_ticks (
    instrument LowCardinality(String) COMMENT 'Forex pair symbol (e.g., EURUSD). FK: conceptually links to instrument metadata.',
    timestamp DateTime64(6, 'UTC') CODEC(DoubleDelta, LZ4) COMMENT 'Tick timestamp with microsecond precision. Primary time dimension.',
    bid Float64 CODEC(Gorilla, ZSTD) COMMENT 'Bid price from Raw_Spread variant (97.81% zero-spread execution prices).',
    ask Float64 CODEC(Gorilla, ZSTD) COMMENT 'Ask price from Raw_Spread variant. Often equals bid (zero-spread).'
) ENGINE = ReplacingMergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (instrument, timestamp)
COMMENT 'Raw_Spread tick data from Exness. Primary source for BID-only OHLC construction. Deduplication via ReplacingMergeTree on (instrument, timestamp).';

CREATE TABLE exness.standard_ticks (
    instrument LowCardinality(String) COMMENT 'Forex pair symbol (e.g., EURUSD). FK: conceptually links to instrument metadata.',
    timestamp DateTime64(6, 'UTC') CODEC(DoubleDelta, LZ4) COMMENT 'Tick timestamp with microsecond precision. Primary time dimension.',
    bid Float64 CODEC(Gorilla, ZSTD) COMMENT 'Bid price from Standard variant (traditional quotes, always Bid < Ask).',
    ask Float64 CODEC(Gorilla, ZSTD) COMMENT 'Ask price from Standard variant. Always > bid (never zero-spread).'
) ENGINE = ReplacingMergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (instrument, timestamp)
COMMENT 'Standard tick data from Exness. Reference quotes for position ratio calculation. ASOF merged with raw_spread_ticks.';
```

### 1.3 OHLC Table (30 columns)

**Codec Selection** (research-validated):

- `DateTime64`: DoubleDelta + **LZ4** (1.76x faster, ZSTD no benefit)
- `Float64`: Gorilla + ZSTD (8-15x compression)
- `UInt8/UInt32`: T64 + ZSTD (5-10x compression)
- `LowCardinality(String)`: Dictionary encoding (4x query speed)

```sql
CREATE TABLE exness.ohlc_1m (
    instrument LowCardinality(String) COMMENT 'Forex pair symbol. FK: links to raw_spread_ticks and standard_ticks.',
    timestamp DateTime64(0, 'UTC') CODEC(DoubleDelta, LZ4) COMMENT 'Minute-aligned bar timestamp. Primary time dimension for OHLC.',
    open Float64 CODEC(Gorilla, ZSTD) COMMENT 'First BID price in minute from raw_spread_ticks.',
    high Float64 CODEC(Gorilla, ZSTD) COMMENT 'Maximum BID price in minute from raw_spread_ticks.',
    low Float64 CODEC(Gorilla, ZSTD) COMMENT 'Minimum BID price in minute from raw_spread_ticks.',
    close Float64 CODEC(Gorilla, ZSTD) COMMENT 'Last BID price in minute from raw_spread_ticks.',
    raw_spread_avg Nullable(Float64) CODEC(Gorilla, ZSTD) COMMENT 'AVG(ask-bid) from raw_spread_ticks. Usually ~0 (97.81% zero-spread).',
    standard_spread_avg Nullable(Float64) CODEC(Gorilla, ZSTD) COMMENT 'AVG(ask-bid) from standard_ticks. Always > 0 (~0.7 pips).',
    tick_count_raw_spread Nullable(UInt32) CODEC(T64, ZSTD) COMMENT 'COUNT(*) from raw_spread_ticks in this minute.',
    tick_count_standard Nullable(UInt32) CODEC(T64, ZSTD) COMMENT 'COUNT(*) from standard_ticks in this minute.',
    range_per_spread Nullable(Float32) CODEC(Gorilla, ZSTD) COMMENT 'Normalized metric: (high-low) / raw_spread_avg.',
    range_per_tick Nullable(Float32) CODEC(Gorilla, ZSTD) COMMENT 'Normalized metric: (high-low) / tick_count_raw_spread.',
    body_per_spread Nullable(Float32) CODEC(Gorilla, ZSTD) COMMENT 'Normalized metric: |close-open| / raw_spread_avg.',
    body_per_tick Nullable(Float32) CODEC(Gorilla, ZSTD) COMMENT 'Normalized metric: |close-open| / tick_count_raw_spread.',
    ny_hour UInt8 CODEC(T64, ZSTD) COMMENT 'Hour in New York timezone (0-23). FK: joins with exchange_sessions.',
    london_hour UInt8 CODEC(T64, ZSTD) COMMENT 'Hour in London timezone (0-23). FK: joins with exchange_sessions.',
    ny_session LowCardinality(String) COMMENT 'NY session label: pre_market, market_open, post_market, closed.',
    london_session LowCardinality(String) COMMENT 'London session label: pre_market, market_open, post_market, closed.',
    is_us_holiday UInt8 COMMENT 'Boolean: 1 if US market holiday. FK: joins with holidays table.',
    is_uk_holiday UInt8 COMMENT 'Boolean: 1 if UK market holiday. FK: joins with holidays table.',
    is_major_holiday UInt8 COMMENT 'Boolean: 1 if major holiday (Christmas, New Year, etc.).',
    is_nyse_session UInt8 COMMENT 'Boolean: 1 if NYSE is open. FK: joins with exchange_sessions (NYSE).',
    is_lse_session UInt8 COMMENT 'Boolean: 1 if LSE is open. FK: joins with exchange_sessions (LSE).',
    is_xswx_session UInt8 COMMENT 'Boolean: 1 if SIX Swiss Exchange is open.',
    is_xfra_session UInt8 COMMENT 'Boolean: 1 if Frankfurt Stock Exchange is open.',
    is_xtse_session UInt8 COMMENT 'Boolean: 1 if Toronto Stock Exchange is open.',
    is_xnze_session UInt8 COMMENT 'Boolean: 1 if New Zealand Stock Exchange is open.',
    is_xtks_session UInt8 COMMENT 'Boolean: 1 if Tokyo Stock Exchange is open.',
    is_xasx_session UInt8 COMMENT 'Boolean: 1 if Australian Securities Exchange is open.',
    is_xhkg_session UInt8 COMMENT 'Boolean: 1 if Hong Kong Stock Exchange is open.',
    is_xses_session UInt8 COMMENT 'Boolean: 1 if Singapore Exchange is open.'
) ENGINE = ReplacingMergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (instrument, timestamp)
COMMENT 'Phase7 30-column OHLC bars at 1-minute resolution. BID-only prices from raw_spread_ticks. Supports on-demand resampling to 5m/1h/1d.';
```

### 1.4 Lookup Tables (Exchange Sessions and Holidays)

**Why tables instead of Dictionaries** (research-validated):

- Dictionaries only benefit schemas with >364 entries (ClickHouse blog)
- exchange_sessions: ~10 rows (36x below threshold)
- holidays: ~1000 rows/year (still below practical benefit)
- v24.4+ optimizer handles small JOINs efficiently (8-10x improvement)
- Simpler architecture, better LLM training coverage for standard SQL

```sql
CREATE TABLE exness.exchange_sessions (
    exchange_code LowCardinality(String) COMMENT 'Exchange MIC code (NYSE, LSE, XHKG, etc.). Primary key.',
    name String COMMENT 'Full exchange name (e.g., New York Stock Exchange).',
    timezone String COMMENT 'IANA timezone (e.g., America/New_York).',
    open_hour UInt8 COMMENT 'Market open hour in local timezone (0-23).',
    open_minute UInt8 COMMENT 'Market open minute (0-59). Usually 0 or 30.',
    close_hour UInt8 COMMENT 'Market close hour in local timezone (0-23).',
    close_minute UInt8 COMMENT 'Market close minute (0-59). Usually 0 or 30.'
) ENGINE = MergeTree()
ORDER BY exchange_code
COMMENT 'Exchange trading hours. ~10 rows. JOIN with ohlc_1m on is_*_session columns.';

CREATE TABLE exness.holidays (
    date Date COMMENT 'Holiday date. Part of composite primary key.',
    exchange_code LowCardinality(String) COMMENT 'Exchange MIC code. FK: exchange_sessions.exchange_code.',
    holiday_name String COMMENT 'Holiday name (e.g., Christmas Day, Independence Day).'
) ENGINE = MergeTree()
ORDER BY (exchange_code, date)
COMMENT 'Exchange holidays. ~1000 rows/year. JOIN with ohlc_1m on is_*_holiday columns.';
```

### 1.5 Parameterized Views

```sql
CREATE VIEW exness.instrument_ticks AS
SELECT timestamp, bid, ask
FROM exness.raw_spread_ticks
WHERE instrument = {instrument:String}
  AND timestamp >= {start_date:DateTime64}
  AND timestamp < {end_date:DateTime64}
ORDER BY timestamp;

CREATE VIEW exness.instrument_ohlc AS
SELECT
    toStartOfInterval(timestamp, INTERVAL {minutes:UInt32} MINUTE) AS bar_time,
    argMin(open, timestamp) AS open,
    max(high) AS high,
    min(low) AS low,
    argMax(close, timestamp) AS close
FROM exness.ohlc_1m
WHERE instrument = {instrument:String}
  AND timestamp >= {start_date:DateTime64}
  AND timestamp < {end_date:DateTime64}
GROUP BY bar_time
ORDER BY bar_time;
```

## Phase 2: Implementation (3 Batches)

### Batch 1: Client + Database Manager

**Files**: `clickhouse_client.py` (NEW), `database_manager.py` (REWRITE)

**Validation**: `uv run pytest tests/test_database.py`

**Commit**: `git commit -m "refactor: batch 1 - clickhouse client + database_manager"`

### Batch 2: Gap Detector + Query Engine

**Files**: `gap_detector.py` (REWRITE), `query_engine.py` (REWRITE)

**Validation**: `uv run pytest tests/test_queries.py`

**Commit**: `git commit -m "refactor: batch 2 - gap_detector + query_engine"`

### Batch 3: OHLC Generator + Processor + Cleanup

**Files**: `ohlc_generator.py` (REWRITE), `processor.py` (UPDATE), `pyproject.toml` (UPDATE)

**Validation**: `uv run pytest`

**Commit**: `git commit -m "refactor: batch 3 - ohlc_generator + processor + cleanup"`

## Files Summary

| File                   | Action                          | Batch |
| ---------------------- | ------------------------------- | ----- |
| `clickhouse_client.py` | NEW                             | 1     |
| `database_manager.py`  | REWRITE                         | 1     |
| `gap_detector.py`      | REWRITE                         | 2     |
| `query_engine.py`      | REWRITE                         | 2     |
| `ohlc_generator.py`    | REWRITE                         | 3     |
| `processor.py`         | UPDATE                          | 3     |
| `pyproject.toml`       | UPDATE (add clickhouse-connect) | 3     |
| `session_detector.py`  | UPDATE (use ClickHouse JOIN)    | 3     |
| `schema.py`            | UPDATE (ClickHouse types)       | 3     |

## Critical File Paths

| File             | Path                                                                                       | Lines |
| ---------------- | ------------------------------------------------------------------------------------------ | ----- |
| Database Manager | `/Users/terryli/eon/exness-data-preprocess/src/exness_data_preprocess/database_manager.py` | 209   |
| Gap Detector     | `/Users/terryli/eon/exness-data-preprocess/src/exness_data_preprocess/gap_detector.py`     | 135   |
| OHLC Generator   | `/Users/terryli/eon/exness-data-preprocess/src/exness_data_preprocess/ohlc_generator.py`   | 266   |
| Query Engine     | `/Users/terryli/eon/exness-data-preprocess/src/exness_data_preprocess/query_engine.py`     | 291   |
| Processor        | `/Users/terryli/eon/exness-data-preprocess/src/exness_data_preprocess/processor.py`        | 766   |
| Session Detector | `/Users/terryli/eon/exness-data-preprocess/src/exness_data_preprocess/session_detector.py` | 188   |
| Schema           | `/Users/terryli/eon/exness-data-preprocess/src/exness_data_preprocess/schema.py`           | 324   |

## Validation Checklist

- [ ] `exness` database created in ClickHouse
- [ ] Tick tables with LowCardinality instrument column + COMMENT statements
- [ ] Lookup tables (exchange_sessions, holidays) with COMMENT statements
- [ ] Parameterized views working
- [ ] Batch 1: Client + database_manager passes tests
- [ ] Batch 2: gap_detector + query_engine passes tests
- [ ] Batch 3: ohlc_generator + processor passes all tests
- [ ] No DuckDB imports remaining
- [ ] All tables have comprehensive COMMENT statements for AI understanding
- [ ] Documentation updated

## Independent Validation (2025-12-09)

### Fixes Applied (vs Original Architect Recommendations)

| Issue                | Original Skill | Research-Validated     | Reason                                     |
| -------------------- | -------------- | ---------------------- | ------------------------------------------ |
| Timestamp codec      | ZSTD           | **LZ4**                | ZSTD provides no benefit for DoubleDelta   |
| Float codec          | ZSTD           | ZSTD (confirmed)       | ZSTD(1) optimal for Gorilla-encoded floats |
| Lookups              | Dictionaries   | **Standard tables**    | <364 rows = no benefit, adds complexity    |
| Schema documentation | Not mentioned  | **COMMENT statements** | 20-27% AI accuracy improvement (research)  |

### Codec Safety Note (Historical Context)

**Status**: The Delta+Gorilla corruption bug was **fixed in v23.2** (Jan 2023, PR #45615). Your v25.11.2 is safe.

The combination is still **blocked by default** (`allow_suspicious_codecs`) because it's **redundant** (Gorilla already does delta internally), not because it's dangerous.

```sql
-- REDUNDANT (blocked by default, not dangerous in v23.2+)
column Float64 CODEC(Delta, Gorilla, ZSTD)

-- OPTIMAL - Use codecs independently
price Float64 CODEC(Gorilla, ZSTD)              -- Floats
timestamp DateTime64 CODEC(DoubleDelta, LZ4)    -- Timestamps (LZ4 optimal)
```

### Validation Queries (Post-Implementation)

```sql
-- Check compression effectiveness
SELECT
    column,
    type,
    compression_codec,
    formatReadableSize(data_compressed_bytes) AS compressed,
    formatReadableSize(data_uncompressed_bytes) AS uncompressed,
    round(data_uncompressed_bytes / data_compressed_bytes, 2) AS ratio
FROM system.columns
WHERE database = 'exness'
ORDER BY data_uncompressed_bytes DESC;

-- Check part count per partition (should be < 300)
SELECT
    table,
    partition,
    count() AS parts
FROM system.parts
WHERE database = 'exness' AND active
GROUP BY table, partition
HAVING parts > 100
ORDER BY parts DESC;
```
