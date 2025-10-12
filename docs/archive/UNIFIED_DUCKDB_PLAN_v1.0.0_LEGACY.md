# Unified DuckDB Architecture - Comprehensive Plan

**Version**: 1.0.0
**Status**: APPROVED (validated with real data 2025-10-12)
**Previous**: Separate Parquet + DuckDB approach

---

## Executive Summary

**Recommendation**: Adopt **Unified DuckDB with Optional Parquet Export** architecture

**Rationale**:

- ✅ **Validated**: Real EURUSD Sep 2024 data (2M ticks, 30K bars)
- ✅ **Simpler**: 1 file vs 3 files per month
- ✅ **Phase7 Compliant**: Dual-variant 9-column schema works perfectly
- ✅ **Fast**: <15ms queries for all timeframes (vs 3.37s OHLC generation)
- ✅ **Scalable**: 11.26 MB per month (vs 10.32 MB separate files, only 9% larger)
- ✅ **Flexible**: Optional Parquet export for interchange

---

## Architecture Options Review

### Option A: Current Approach (Separate Files) ❌

**Structure**:

```
~/eon/exness-data/
├── parquet/
│   ├── eurusd_raw_spread_2024_09.parquet (~4.77 MB)
│   └── eurusd_standard_2024_09.parquet (~4.77 MB)
└── duckdb/
    └── eurusd_ohlc_2024_09.duckdb (~0.78 MB)

Total: ~10.32 MB per month
Files: 3 files per month
```

**Schema** (OHLC only, 7 columns):

```sql
Timestamp, Open, High, Low, Close, spread_avg, tick_count
```

**Current Issues**:

1. ❌ **Wrong URL pattern**: Uses flat structure, should be `/ticks/{variant}/{year}/{month}/`
2. ❌ **Single variant**: Only downloads Raw_Spread, missing Standard for phase7
3. ❌ **Incomplete schema**: 7 columns, phase7 requires 9 (dual spreads + dual tick counts)
4. ❌ **Multiple files**: Need to manage 3 files per month
5. ❌ **Complex queries**: Must join Parquet + DuckDB for analysis
6. ❌ **No tick queries**: Must load Parquet into memory for tick analysis

**Pros**:

- ✅ Parquet is interchange format (portable)
- ✅ Slightly smaller (9% savings)
- ✅ Proven compression benchmarks

**Cons**:

- ❌ NOT phase7 compliant (missing dual-variant)
- ❌ Complex file management
- ❌ Requires Parquet reader for tick analysis
- ❌ No SQL queries on raw ticks

**Verdict**: ❌ **REJECT** - Not phase7 compliant, unnecessarily complex

---

### Option B: Unified DuckDB (All Data) ✅ RECOMMENDED

**Structure**:

```
~/eon/exness-data/
└── eurusd_2024_09.duckdb (~11.26 MB)
    ├── raw_spread_ticks (925,780 rows)
    ├── standard_ticks (1,082,145 rows)
    └── ohlc_1m (30,240 rows)

Total: ~11.26 MB per month
Files: 1 file per month
```

**Schema** (Phase7 9 columns):

```sql
-- OHLC table
Timestamp               TIMESTAMP WITH TIME ZONE  -- Minute-aligned
Open                    DOUBLE                    -- Raw_Spread BID first
High                    DOUBLE                    -- Raw_Spread BID max
Low                     DOUBLE                    -- Raw_Spread BID min
Close                   DOUBLE                    -- Raw_Spread BID last
raw_spread_avg          DOUBLE                    -- AVG(Ask-Bid) from Raw_Spread
standard_spread_avg     DOUBLE                    -- AVG(Ask-Bid) from Standard
tick_count_raw_spread   BIGINT                    -- COUNT(*) from Raw_Spread
tick_count_standard     BIGINT                    -- COUNT(*) from Standard

-- Tick tables (3 columns each)
Timestamp               TIMESTAMP WITH TIME ZONE
Bid                     DOUBLE
Ask                     DOUBLE
```

**Validation Results** (Real Data, Sep 2024):

- ✅ **Irregular ticks**: 1µs to 130.61s intervals
- ✅ **Regular OHLC**: 0 unaligned bars (100% minute-aligned)
- ✅ **Phase7 schema**: 9 columns confirmed
- ✅ **Query performance**: 0.22ms tick count, 13.98ms OHLC query, 3.63ms 5m resample
- ✅ **Storage**: 11.26 MB (only 9% larger than separate files)

**Pros**:

- ✅ **Single source of truth**: All data in one file
- ✅ **Phase7 compliant**: Dual-variant methodology
- ✅ **SQL queries on ticks**: Direct tick analysis without loading into memory
- ✅ **Fast resampling**: <15ms for any timeframe (no need to pre-compute)
- ✅ **Simple management**: 1 file to backup/restore
- ✅ **Embedded metadata**: SQL COMMENT statements
- ✅ **DuckDB compression**: Columnar compression comparable to Parquet Zstd-22

**Cons**:

- ❌ **9% larger**: 11.26 MB vs 10.32 MB (negligible for modern storage)
- ❌ **Not portable**: DuckDB format (but can export to Parquet on-demand)

**Verdict**: ✅ **RECOMMENDED** - Best balance of simplicity, performance, and phase7 compliance

---

### Option C: Unified DuckDB + Optional Parquet Export ⭐ OPTIMAL

**Structure**:

```
~/eon/exness-data/
├── eurusd_2024_09.duckdb (~11.26 MB)  # Primary storage
│   ├── raw_spread_ticks
│   ├── standard_ticks
│   └── ohlc_1m
└── export/  # Optional, on-demand only
    ├── eurusd_raw_spread_2024_09.parquet (exported when needed)
    └── eurusd_standard_2024_09.parquet (exported when needed)
```

**Workflow**:

1. **Primary**: Store everything in unified DuckDB
2. **Optional**: Export ticks to Parquet only when needed (e.g., sharing data, external tools)

**Export Command**:

```sql
-- Export Raw_Spread ticks to Parquet
COPY raw_spread_ticks TO '/path/to/eurusd_raw_spread_2024_09.parquet'
(FORMAT PARQUET, COMPRESSION ZSTD, COMPRESSION_LEVEL 22);

-- Export Standard ticks to Parquet
COPY standard_ticks TO '/path/to/eurusd_standard_2024_09.parquet'
(FORMAT PARQUET, COMPRESSION ZSTD, COMPRESSION_LEVEL 22);
```

**Pros**:

- ✅ **All benefits of Option B** (unified, phase7, fast, simple)
- ✅ **Parquet available on-demand**: Export when needed for interchange
- ✅ **No redundant storage**: Only export when necessary
- ✅ **Flexibility**: Best of both worlds

**Cons**:

- None significant (exports are optional and fast)

**Verdict**: ⭐ **OPTIMAL** - Combines simplicity of unified approach with flexibility of Parquet export

---

### Option D: Pre-compute Multiple Timeframes ❌

**Structure**:

```
~/eon/exness-data/
└── eurusd_2024_09.duckdb
    ├── raw_spread_ticks
    ├── standard_ticks
    ├── ohlc_1m (30,240 bars)
    ├── ohlc_5m (6,079 bars)    # Pre-computed
    ├── ohlc_1h (507 bars)      # Pre-computed
    └── ohlc_1d (21 bars)       # Pre-computed
```

**Rationale**: Avoid resampling overhead

**Performance Reality**:

- ✅ 1m query: 13.98ms (stored)
- ✅ 5m resample: 3.63ms (on-demand)
- ✅ 1h resample: 9.75ms (on-demand)

**Conclusion**: Resampling is **FASTER** than reading pre-computed data from disk!

**Verdict**: ❌ **REJECT** - Unnecessary redundancy, resampling is instant (<15ms)

---

### Option E: Store All 4 Variants ❌

**Structure**:

```
~/eon/exness-data/
└── eurusd_2024_09.duckdb (~40-50 MB)
    ├── raw_spread_ticks        # Phase7 primary
    ├── standard_ticks          # Phase7 reference
    ├── standart_plus_ticks     # Wider spreads
    ├── zero_spread_ticks       # Similar to Raw_Spread
    └── ohlc_1m
```

**Analysis**:

- Raw_Spread and Zero_Spread are 97.81% identical (redundant)
- Standart_Plus has 70% wider spreads (not needed for phase7)
- Phase7 only requires Raw_Spread + Standard

**Verdict**: ❌ **REJECT** - Unnecessary storage, phase7 only needs 2 variants

---

## Recommended Architecture: Unified DuckDB with Optional Export

### File Structure

```
~/eon/exness-data/
├── eurusd_2024_08.duckdb (11 MB)
├── eurusd_2024_09.duckdb (11 MB)
├── eurusd_2024_10.duckdb (11 MB)
├── xauusd_2024_08.duckdb (11 MB)
└── export/  # Optional, created on-demand
    └── (Parquet files when exported)
```

### Database Schema

**Per-instrument DuckDB file** (e.g., `eurusd_2024_09.duckdb`):

**Table 1: `raw_spread_ticks`**

```sql
CREATE TABLE raw_spread_ticks (
    Timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    Bid DOUBLE NOT NULL,
    Ask DOUBLE NOT NULL
);

COMMENT ON TABLE raw_spread_ticks IS
'Exness EURUSD Raw_Spread variant (execution prices, 98% zero-spreads).
 Downloaded from: https://ticks.ex2archive.com/ticks/EURUSD_Raw_Spread/2024/09/
 Generated: 2024-10-12T01:17:28Z
 Ticks: 925,780 (21 trading days)
 Zero-spreads: 98.03%';

COMMENT ON COLUMN raw_spread_ticks.Timestamp IS
'Tick timestamp (millisecond precision, UTC, irregular intervals)';

COMMENT ON COLUMN raw_spread_ticks.Bid IS
'BID price (float64, used for OHLC construction)';

COMMENT ON COLUMN raw_spread_ticks.Ask IS
'ASK price (float64, used for spread calculation)';
```

**Table 2: `standard_ticks`**

```sql
CREATE TABLE standard_ticks (
    Timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    Bid DOUBLE NOT NULL,
    Ask DOUBLE NOT NULL
);

COMMENT ON TABLE standard_ticks IS
'Exness EURUSD Standard variant (traditional quotes, always Bid < Ask).
 Downloaded from: https://ticks.ex2archive.com/ticks/EURUSD/2024/09/
 Generated: 2024-10-12T01:17:28Z
 Ticks: 1,082,145 (21 trading days)
 Zero-spreads: 0%
 Used for: Position ratio calculation (ASOF merge with Raw_Spread)';

COMMENT ON COLUMN standard_ticks.Timestamp IS
'Tick timestamp (millisecond precision, UTC, irregular intervals)';

COMMENT ON COLUMN standard_ticks.Bid IS
'BID price (float64, reference for position ratio)';

COMMENT ON COLUMN standard_ticks.Ask IS
'ASK price (float64, reference for position ratio)';
```

**Table 3: `ohlc_1m`** (Phase7 9-column schema)

```sql
CREATE TABLE ohlc_1m AS
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

COMMENT ON TABLE ohlc_1m IS
'EURUSD 1-minute OHLC bars (Phase7 v1.1.0 dual-variant methodology).
 Generated: 2024-10-12T01:17:28Z
 Bars: 30,240 (21 trading days × 1440 minutes/day)
 OHLC Source: Raw_Spread BID prices
 Spreads: Dual-variant (Raw_Spread + Standard)
 Tick Counts: Dual-variant for liquidity analysis
 Specification: docs/research/eurusd-zero-spread-deviations/data/plan/phase7_bid_ohlc_construction_v1.1.0.md';

COMMENT ON COLUMN ohlc_1m.Timestamp IS 'Bar start time (minute boundary, UTC)';
COMMENT ON COLUMN ohlc_1m.Open IS 'First BID price from Raw_Spread in this minute';
COMMENT ON COLUMN ohlc_1m.High IS 'Maximum BID price from Raw_Spread in this minute';
COMMENT ON COLUMN ohlc_1m.Low IS 'Minimum BID price from Raw_Spread in this minute';
COMMENT ON COLUMN ohlc_1m.Close IS 'Last BID price from Raw_Spread in this minute';
COMMENT ON COLUMN ohlc_1m.raw_spread_avg IS 'Mean spread (Ask-Bid) from Raw_Spread variant';
COMMENT ON COLUMN ohlc_1m.standard_spread_avg IS 'Mean spread (Ask-Bid) from Standard variant';
COMMENT ON COLUMN ohlc_1m.tick_count_raw_spread IS 'Number of ticks from Raw_Spread in this minute';
COMMENT ON COLUMN ohlc_1m.tick_count_standard IS 'Number of ticks from Standard in this minute';
```

### Storage Projections

**Per Month** (21 trading days, EURUSD):

- Unified DuckDB: **11.26 MB** (validated with real Sep 2024 data)

**Annual** (12 months):

- Single instrument: 12 × 11.26 MB = **135 MB/year**

**Multi-Instrument** (EURUSD + XAUUSD):

- Two instruments: 2 × 135 MB = **270 MB/year**

**5-Year History**:

- Single instrument: 5 × 135 MB = **675 MB**
- Two instruments: 5 × 270 MB = **1.35 GB**

**Conclusion**: Extremely manageable for modern storage

---

## API Design

### Core Methods

```python
class ExnessDataProcessor:
    """Process Exness tick data with unified DuckDB storage."""

    def process_month(
        self,
        year: int,
        month: int,
        pair: str = "EURUSD",
        variants: list[str] = ["Raw_Spread", ""]
    ) -> Dict[str, Any]:
        """
        Complete processing workflow for one month (unified DuckDB).

        Workflow:
        1. Download both variants (Raw_Spread + Standard)
        2. Create unified DuckDB with 3 tables
        3. Generate phase7 OHLC (9 columns)
        4. Add embedded metadata
        5. Delete temporary ZIPs

        Args:
            year: Year (e.g., 2024)
            month: Month (1-12)
            pair: Currency pair (default: EURUSD)
            variants: List of variants ["Raw_Spread", ""] for dual-variant

        Returns:
            Dictionary with results:
                - duckdb_path: Path to unified DuckDB file
                - raw_spread_tick_count: Number of Raw_Spread ticks
                - standard_tick_count: Number of Standard ticks
                - ohlc_bar_count: Number of 1-minute bars
                - duckdb_size_mb: DuckDB file size in MB
        """
        pass

    def query_ticks(
        self,
        year: int,
        month: int,
        pair: str = "EURUSD",
        variant: str = "raw_spread",
        filter_sql: str = None
    ) -> pd.DataFrame:
        """
        Query tick data from unified DuckDB.

        Args:
            year: Year
            month: Month
            pair: Currency pair
            variant: "raw_spread" or "standard"
            filter_sql: Optional SQL WHERE clause

        Returns:
            DataFrame with tick data

        Example:
            >>> processor = ExnessDataProcessor()
            >>> # Get all Raw_Spread ticks
            >>> df = processor.query_ticks(2024, 9, variant="raw_spread")
            >>>
            >>> # Get ticks with zero spread
            >>> df_zero = processor.query_ticks(
            ...     2024, 9,
            ...     variant="raw_spread",
            ...     filter_sql="Bid = Ask"
            ... )
        """
        pass

    def query_ohlc(
        self,
        year: int,
        month: int,
        pair: str = "EURUSD",
        timeframe: str = "1m"
    ) -> pd.DataFrame:
        """
        Query OHLC data (stored or resampled on-demand).

        Args:
            year: Year
            month: Month
            pair: Currency pair
            timeframe: "1m" (stored), "5m", "15m", "1h", "4h", "1d" (resampled)

        Returns:
            DataFrame with OHLC data (phase7 9 columns)

        Example:
            >>> processor = ExnessDataProcessor()
            >>> df_1m = processor.query_ohlc(2024, 9, timeframe="1m")
            >>> df_1h = processor.query_ohlc(2024, 9, timeframe="1h")  # <15ms
        """
        pass

    def export_to_parquet(
        self,
        year: int,
        month: int,
        pair: str = "EURUSD",
        variant: str = "raw_spread",
        output_dir: Path = None
    ) -> Path:
        """
        Export tick data to Parquet (optional, on-demand).

        Args:
            year: Year
            month: Month
            pair: Currency pair
            variant: "raw_spread" or "standard"
            output_dir: Output directory (default: ~/eon/exness-data/export/)

        Returns:
            Path to exported Parquet file

        Example:
            >>> processor = ExnessDataProcessor()
            >>> parquet_path = processor.export_to_parquet(2024, 9)
            >>> print(f"Exported to: {parquet_path}")
        """
        pass
```

---

## Migration Strategy

### Phase 1: Parallel Implementation (Backward Compatible)

**Goal**: Add unified DuckDB without breaking existing code

1. **New directory structure**:

   ```
   ~/eon/exness-data/
   ├── parquet/          # Existing (keep for now)
   ├── duckdb/           # Existing (keep for now)
   └── unified/          # New unified DuckDB files
       ├── eurusd_2024_09.duckdb
       └── ...
   ```

2. **Processor changes**:
   - Add `use_unified: bool = True` parameter to `process_month()`
   - Default to unified approach, fallback to separate files if `use_unified=False`

3. **API backward compatibility**:
   - Existing methods continue working with separate files
   - New methods (`query_ticks`, `export_to_parquet`) only work with unified

### Phase 2: Full Migration (After Validation)

**Goal**: Migrate all existing data to unified format

1. **Conversion utility**:

   ```python
   def migrate_to_unified(
       self,
       year: int,
       month: int,
       pair: str = "EURUSD",
       delete_old: bool = False
   ) -> Path:
       """Convert existing Parquet + DuckDB to unified DuckDB."""
       pass
   ```

2. **Batch migration**:

   ```python
   processor = ExnessDataProcessor()
   for year, month in [(2024, 8), (2024, 9), (2024, 10)]:
       processor.migrate_to_unified(year, month, delete_old=True)
   ```

3. **Remove legacy code**:
   - Remove separate Parquet/DuckDB directories
   - Remove `use_unified` parameter (always use unified)
   - Update documentation

### Phase 3: Optional Parquet Export

**Goal**: Add on-demand Parquet export for interchange

1. **Export directory**:

   ```
   ~/eon/exness-data/
   ├── unified/          # Primary storage
   └── export/           # Optional Parquet exports
       └── (created on-demand)
   ```

2. **Export workflow**:
   ```python
   # Export when needed for sharing/external tools
   processor.export_to_parquet(2024, 9, variant="raw_spread")
   processor.export_to_parquet(2024, 9, variant="standard")
   ```

---

## Implementation Checklist

### Priority 1: Core Unified DuckDB (Week 1)

- [ ] Update `download_exness_zip()` to support dual-variant downloads
  - [ ] Fix URL pattern: `/ticks/{variant}/{year}/{month}/`
  - [ ] Download Raw_Spread variant
  - [ ] Download Standard variant
- [ ] Create `_create_unified_duckdb()` method
  - [ ] Create three tables: `raw_spread_ticks`, `standard_ticks`, `ohlc_1m`
  - [ ] Load Raw_Spread ticks from ZIP
  - [ ] Load Standard ticks from ZIP
  - [ ] Generate phase7 OHLC (9 columns)
  - [ ] Add embedded metadata (SQL COMMENT statements)
- [ ] Update `process_month()` to use unified approach
- [ ] Add `use_unified: bool = True` parameter for backward compatibility

### Priority 2: Query Methods (Week 1)

- [ ] Implement `query_ticks()` - Direct SQL queries on tick tables
- [ ] Update `query_ohlc()` to work with unified DuckDB
  - [ ] Support stored 1m bars
  - [ ] Support on-demand resampling (5m, 1h, 1d, etc.)
- [ ] Add tick filtering with SQL WHERE clauses

### Priority 3: Parquet Export (Week 2)

- [ ] Implement `export_to_parquet()` method
- [ ] Create export directory structure
- [ ] Add compression options (Zstd-22 default)
- [ ] Update documentation with export examples

### Priority 4: Migration & Cleanup (Week 2)

- [ ] Create `migrate_to_unified()` utility
- [ ] Write migration guide
- [ ] Test with existing Parquet files
- [ ] Batch migration script for all existing data
- [ ] Update examples/ with unified approach

### Priority 5: Documentation (Week 2)

- [ ] Update README.md with unified architecture
- [ ] Update CLAUDE.md project memory
- [ ] Add phase7 methodology reference
- [ ] Document API changes
- [ ] Add migration guide

---

## Performance Targets

Based on real data validation (Sep 2024):

| Operation                 | Target | Actual (Validated)    |
| ------------------------- | ------ | --------------------- |
| **Download + Load**       | <5s    | 2.74s (1.28s + 1.46s) |
| **OHLC Generation**       | <5s    | 3.37s                 |
| **Tick Count Query**      | <1ms   | 0.22ms ⚡             |
| **OHLC Query (30K bars)** | <20ms  | 13.98ms ⚡            |
| **5m Resample**           | <10ms  | 3.63ms ⚡             |
| **1h Resample**           | <15ms  | 9.75ms ⚡             |
| **Total File Size**       | <15 MB | 11.26 MB ⚡           |

**Conclusion**: All targets exceeded! Performance is excellent.

---

## Success Criteria

### Functional

- ✅ Download both variants (Raw_Spread + Standard)
- ✅ Create unified DuckDB with 3 tables
- ✅ Generate phase7 9-column OHLC
- ✅ Support SQL queries on ticks
- ✅ Support on-demand OHLC resampling
- ✅ Embedded metadata persistence

### Performance

- ✅ Query performance: <15ms for all timeframes
- ✅ Storage efficiency: <15 MB per month per instrument
- ✅ OHLC generation: <5s

### Quality

- ✅ Zero precision loss (lossless storage)
- ✅ 100% minute-aligned OHLC bars
- ✅ Phase7 v1.1.0 compliance
- ✅ Backward compatible API

---

## Conclusion

**Recommended Architecture**: **Unified DuckDB with Optional Parquet Export** (Option C)

**Key Advantages**:

1. **Simplicity**: 1 file vs 3 files (67% reduction)
2. **Performance**: <15ms queries, instant resampling
3. **Phase7 Compliance**: Dual-variant 9-column schema
4. **SQL on Ticks**: Direct tick analysis without loading into memory
5. **Flexibility**: Optional Parquet export when needed
6. **Scalability**: 135 MB/year per instrument (extremely efficient)

**Next Steps**:

1. Implement core unified DuckDB methods (Priority 1-2)
2. Add Parquet export option (Priority 3)
3. Create migration utility (Priority 4)
4. Update documentation (Priority 5)

**Validation**: ✅ Tested with real EURUSD Sep 2024 data (2M ticks, 30K bars)

---

**References**:

- **Validation Report**: [`/tmp/exness-duckdb-test/FINDINGS.md`](/tmp/exness-duckdb-test/FINDINGS.md)
- **Test Script**: [`/tmp/exness-duckdb-test/test_real_unified.py`](/tmp/exness-duckdb-test/test_real_unified.py)
- **Phase7 Spec**: [`docs/research/eurusd-zero-spread-deviations/data/plan/phase7_bid_ohlc_construction_v1.1.0.md`](research/eurusd-zero-spread-deviations/data/plan/phase7_bid_ohlc_construction_v1.1.0.md)
- **Compression Benchmarks**: [`docs/research/compression-benchmarks/README.md`](research/compression-benchmarks/README.md)
- **Data Sources Guide**: [`docs/EXNESS_DATA_SOURCES.md`](EXNESS_DATA_SOURCES.md)
