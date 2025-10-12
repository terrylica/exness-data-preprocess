# Compression Benchmarks

## Overview

This directory contains empirical benchmarks that determined the optimal compression strategy for **exness-data-preprocess**. These benchmarks were conducted on actual Exness EURUSD tick data (not synthetic data) to ensure real-world applicability.

## Key Findings

### Winner: Parquet with Zstd-22 (Lossless)

**Metrics**:
- **Size**: 4.77 MB per month (9% smaller than ZIP baseline)
- **Write Time**: 0.78s
- **Read Time**: 0.014s
- **Queryability**: Direct DuckDB queries (no decode step)
- **Precision**: Lossless (zero error)

**Why It Won**:
1. **Lossless**: Financial data requires exact precision (36 pips error is unacceptable)
2. **Fast**: Sub-second write time, instant read
3. **Queryable**: DuckDB can query directly without loading into memory
4. **Practical**: Best balance of compression, speed, and usability

### Rejected: Brotli-11 (Too Slow)

**Metrics**:
- **Size**: 4.34 MB per month (17% smaller than ZIP)
- **Write Time**: 13.67s (17.5x slower than Zstd-22)
- **Read Time**: 0.012s

**Why Rejected**: 13.67s write time is unacceptable for batch processing multiple months of data. The 8% additional compression vs Zstd-22 doesn't justify the 17.5x slowdown.

### Rejected: Delta Encoding (Lossy)

**Metrics**:
- **Size**: 1.59 MB per month (69% smaller than ZIP)
- **Write Time**: 0.063s
- **Read Time**: 0.080s (includes decode step)
- **Precision Loss**: 36.16 pips average error (max 95.10 pips)

**Why Rejected**: **LOSSY compression is unacceptable for financial data**. The adversarial audit revealed:
1. **Precision Loss**: Converts float64 → int16, causing 36 pips average error
2. **Not Queryable**: Requires Python decode step (can't use DuckDB directly)
3. **5.7x Slower**: 0.080s read+decode vs 0.014s for normal Parquet
4. **Accumulating Error**: Error compounds in downstream calculations

## Benchmark Scripts

### 1. `test_parquet_compression_methods.py`

**Purpose**: Initial comprehensive test of Parquet compression codecs.

**Tested**:
- Snappy (default)
- Gzip-9
- Brotli-11
- Zstd-1, Zstd-9, Zstd-22
- LZ4

**Key Discovery**: Brotli-11 achieves 17.3% compression vs ZIP but takes 13.67s (too slow).

**Result**: Identified Zstd-22 as optimal lossless codec.

### 2. `test_all_compression_methods.py`

**Purpose**: Comprehensive benchmark across multiple columnar formats.

**Tested**:
- Apache Parquet (all codecs)
- Apache Arrow Feather
- Lance (modern columnar format)
- Delta encoding + Parquet
- HDF5
- ORC

**Key Discovery**: Delta encoding appeared optimal (69% compression) but fairness audit revealed it was lossy.

**Result**: Confirmed Parquet Zstd-22 as best lossless option.

### 3. `test_delta_encoding_properly.py`

**Purpose**: **Adversarial audit** of delta encoding fairness.

**Critical Finding**: Delta encoding is NOT a fair comparison:
1. **LOSSY**: 36.16 pips average error (max 95.10 pips)
2. **5.7x Slower**: 0.080s read+decode vs 0.014s for normal Parquet
3. **Not Queryable**: Requires Python decode step before DuckDB can query
4. **Reconstruction Error**: float64 → int16 conversion loses precision

**Code Analysis**:
```python
# Delta encoding (LOSSY)
df_delta['Bid_delta'] = (df['Bid'].diff() * 100000).astype('int16')
# Converts 1.08500123456789 → 10850 → 1.08500000000000
# Loss: 0.00000123456789 (12.3 pips)

# Normal Parquet (LOSSLESS)
table = pa.Table.from_pandas(df_original)
pq.write_table(table, normal_path, compression='zstd', compression_level=22)
# Preserves full float64 precision
```

**Result**: **Rejected delta encoding** despite 69% compression due to unacceptable precision loss.

## Methodology

### Data Source

All benchmarks used **actual Exness EURUSD tick data** from `Exness_EURUSD_Raw_Spread_2024_08.zip` (downloaded from ex2archive.com):
- **Period**: August 2024
- **Rows**: ~2,000,000 ticks
- **Size**: 5.25 MB (ZIP baseline)
- **Columns**: Timestamp (datetime64[ns, UTC]), Bid (float64), Ask (float64)

### Compression Baseline

**ZIP**: 5.25 MB (Exness original format)
- Used as 1.0x baseline for all comparisons
- All results reported as ratio to ZIP size

### Fairness Criteria

1. **Lossless**: No precision loss allowed (financial data requirement)
2. **Queryable**: Must support direct DuckDB queries without decode step
3. **Write Speed**: Must be practical for batch processing (< 2s per month)
4. **Read Speed**: Must support low-latency queries (< 0.1s)
5. **Reproducible**: All tests run on same hardware with same data

### Adversarial Audit

After initial benchmarks, conducted **adversarial audit** (requested by user) to verify fairness:
- Checked for lossy conversions
- Measured decode time separately from read time
- Verified queryability with DuckDB
- Tested reconstruction accuracy

**Result**: Audit revealed delta encoding was lossy and not fairly comparable.

## Architecture Decision

Based on these empirical benchmarks, **exness-data-preprocess** uses:

**Parquet with Zstd-22 compression**

**Rationale**:
1. **Lossless**: Zero precision loss (required for financial data)
2. **Fast**: 0.78s write, 0.014s read (practical for batch processing)
3. **Queryable**: Direct DuckDB queries without decode step
4. **Space-Efficient**: 9% smaller than ZIP (4.77 MB vs 5.25 MB)
5. **Industry Standard**: Used by ClickHouse, VictoriaMetrics, Databricks

## Reproducing Benchmarks

### Prerequisites

```bash
cd ~/eon/exness-data-preprocess
uv sync --dev
```

### Run Initial Compression Tests

```bash
uv run --active python -m docs.research.compression-benchmarks.test_parquet_compression_methods
```

**Expected Output**:
```
Method              Size      vs ZIP      Result
────────────────────────────────────────────────────────────
✓ Brotli level 11   4.34 MB   0.83x      17.3% SMALLER ✓
✓ ZSTD level 22     4.77 MB   0.91x       9.1% SMALLER ✓
✗ ZSTD default      7.35 MB   1.40x      40.2% LARGER ✗
✗ ZIP baseline      5.25 MB   1.00x      —
```

### Run Comprehensive Benchmark

```bash
uv run --active python -m docs.research.compression-benchmarks.test_all_compression_methods
```

**Expected Output**: Full comparison across Parquet, Feather, Lance, Delta, HDF5, ORC.

### Run Delta Encoding Audit

```bash
uv run --active python -m docs.research.compression-benchmarks.test_delta_encoding_properly
```

**Expected Output**:
```
PRECISION LOSS ANALYSIS
Bid errors:
  Mean error:   0.0036160346 (36.1603 pips)
  Max error:    0.0095100000 (95.1000 pips)

VERDICT
❌ Delta encoding is NOT a fair comparison because:
   1. LOSSY: 36.1603 pips avg error (max 95.10 pips)
   2. Not directly queryable (needs Python decode step)
   3. 5.7x slower when including decode time
   4. Can't use with DuckDB directly
```

## References

### Compression Research

1. **Zstd Algorithm** (Facebook/Meta):
   - https://facebook.github.io/zstd/
   - "Fast real-time compression algorithm"
   - Used by ClickHouse, VictoriaMetrics, Databricks

2. **Brotli Algorithm** (Google):
   - https://github.com/google/brotli
   - "Designed for HTTP compression (small files)"
   - NOT recommended for large datasets

3. **Time-Series Best Practices**:
   - ClickHouse: Zstd for time-series data
   - VictoriaMetrics: Zstd over Brotli
   - Databricks: Zstd as default for Parquet

### Columnar Formats

1. **Apache Parquet**: https://parquet.apache.org/
2. **Apache Arrow Feather**: https://arrow.apache.org/docs/python/feather.html
3. **Lance**: https://github.com/lancedb/lance
4. **ORC**: https://orc.apache.org/

## Summary

These benchmarks demonstrate that **Parquet with Zstd-22** is the optimal choice for Exness tick data:
- **9% smaller than ZIP** (practical compression)
- **Lossless** (zero precision loss)
- **Fast** (0.78s write, 0.014s read)
- **Queryable** (direct DuckDB access)
- **Industry Standard** (battle-tested by major platforms)

The adversarial audit was critical in rejecting delta encoding, which appeared optimal (69% compression) but was actually lossy with unacceptable precision loss for financial data.

---

**Files in this directory**:
- `/Users/terryli/eon/exness-data-preprocess/docs/research/compression-benchmarks/test_parquet_compression_methods.py`
- `/Users/terryli/eon/exness-data-preprocess/docs/research/compression-benchmarks/test_all_compression_methods.py`
- `/Users/terryli/eon/exness-data-preprocess/docs/research/compression-benchmarks/test_delta_encoding_properly.py`
- `/Users/terryli/eon/exness-data-preprocess/docs/research/compression-benchmarks/README.md` (this file)
