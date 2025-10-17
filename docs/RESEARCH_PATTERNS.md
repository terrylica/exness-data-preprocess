# Research Patterns

**Version**: 1.0.0
**Date**: 2025-10-17
**Status**: Canonical Architecture Decision

This document defines the research lifecycle pattern and tool selection for tick-level temporal analysis.

---

## Architecture Principle

**DuckDB as Single Source of Truth**: DuckDB stores validated research outcomes (materialized results with COMMENT ON), not exploratory analysis tools. The research lifecycle separates exploration (pandas/Polars) from validated knowledge (DuckDB tables + SQL views).

---

## Research Lifecycle

### Phase 1: Exploration
- **Tools**: pandas or Polars for tick-level temporal operations
- **Operations**: ASOF merges, statistical tests, hypothesis validation
- **Outputs**: Research scripts, plots, findings
- **State**: Temporary, fast iteration

### Phase 2: Validation
- **Actions**: Confirm statistical significance, test temporal stability
- **Criteria**: Multi-period validation, reproducible methodology
- **Outputs**: Research reports with validated findings

### Phase 3: Graduation to DuckDB
- **Action**: Materialize validated results (not the operation)
- **Process**: Pre-compute metrics, store in DuckDB tables
- **Documentation**: COMMENT ON statements linking to research source
- **Interface**: SQL views for querying

### Phase 4: Production Queries
- **Consumers**: Downstream analysis queries materialized tables
- **Performance**: Sub-15ms for pre-computed metrics
- **Source**: DuckDB single source of truth

---

## Tool Selection

### Temporal Matching (ASOF Joins)

**Performance Benchmark** (880K ticks, 1 month EURUSD):

| Tool                | Time    | Relative | Use Case                        |
| ------------------- | ------- | -------- | ------------------------------- |
| pandas merge_asof   | 0.0374s | 1.00x    | Exploration (tick-level)        |
| Polars join_asof    | 0.0381s | 1.02x    | Exploration (alternative)       |
| DuckDB ASOF JOIN    | 0.8911s | 23.83x   | Not suitable for this use case  |

**Benchmark Source**: `/tmp/test_asof_spike.py` (2025-10-17)

**Decision**: Use pandas or Polars for tick-level temporal matching in research. Both deliver equivalent sub-40ms performance at realistic scale.

**DuckDB ASOF Limitation**: Despite being production-ready (added Sept 2023), DuckDB ASOF JOIN is 24x slower than pandas for microsecond-precision temporal matching. DuckDB is optimized for analytical queries over large datasets, not in-memory tick-level operations.

### When to Use Each Tool

**pandas/Polars**:
- Tick-level ASOF merges (microsecond precision)
- Statistical analysis requiring temporal alignment
- Research exploration requiring fast iteration
- Operations where performance = sub-40ms

**DuckDB**:
- Storing validated research results (materialized tables)
- SQL views for querying pre-computed metrics
- Date range filtering on tick data
- OHLC generation (GROUP BY minute aggregations)
- Operations where performance = sub-15ms on materialized data

---

## Hybrid Materialization Pattern

### What Gets Materialized

**Don't materialize**: ASOF merge operations (keep in pandas)
**Do materialize**: Validated research results (position_ratio, deviation metrics)

### Example: Zero-Spread Deviation Analysis

**Phase 1-2: Exploration and Validation** (pandas)
```python
# Research script: docs/research/eurusd-zero-spread-deviations/scripts/
merged = pd.merge_asof(
    raw_spread_data.sort_values("Timestamp"),
    standard_data.sort_values("Timestamp"),
    on="Timestamp",
    direction="backward",
    tolerance=pd.Timedelta(seconds=10),
)
merged["position_ratio"] = (merged["raw_mid"] - merged["std_bid"]) / (
    merged["std_ask"] - merged["std_bid"]
)
```

**Phase 3: Graduation to DuckDB** (materialize results)
```sql
-- Store validated findings (created via pandas, stored in DuckDB)
CREATE TABLE eurusd_spread_deviations AS
SELECT
    Timestamp,
    raw_mid,
    std_bid,
    std_ask,
    (raw_mid - std_bid) / (std_ask - std_bid) as position_ratio,
    ABS((raw_mid - std_bid) / (std_ask - std_bid)) as deviation_magnitude
FROM (pandas_merge_asof_result);

COMMENT ON TABLE eurusd_spread_deviations IS
'Validated zero-spread deviation analysis (Oct 2024 - Oct 2025, 13 months).
Mean reversion: 87.3% ± 1.9% stable across 16-month validation.
Temporal matching: pandas merge_asof with 10s tolerance, backward direction.
Research source: docs/research/eurusd-zero-spread-deviations/
Methodology: docs/research/eurusd-zero-spread-deviations/01-methodology.md
Validation: docs/research/eurusd-zero-spread-deviations/03-multiperiod-validation.md';

COMMENT ON COLUMN eurusd_spread_deviations.position_ratio IS
'Position of Raw_Spread execution price within Standard spread band.
Formula: (raw_mid - std_bid) / (std_ask - std_bid)
Range: Typically [-0.5, 1.5] for valid spreads, extreme values indicate zero-spread deviations.
Mean reversion validated: 87.3% of extreme deviations revert within 10 ticks.';
```

**Phase 4: Query via SQL Views** (sub-15ms)
```sql
-- SQL view for querying (fast on materialized data)
CREATE VIEW extreme_deviations AS
SELECT
    Timestamp,
    position_ratio,
    deviation_magnitude,
    CASE
        WHEN position_ratio < 0 THEN 'Below Bid'
        WHEN position_ratio > 1 THEN 'Above Ask'
        ELSE 'Within Spread'
    END as deviation_type
FROM eurusd_spread_deviations
WHERE ABS(position_ratio) > 2.0;

COMMENT ON VIEW extreme_deviations IS
'Zero-spread extreme deviations (position_ratio magnitude > 2.0).
Occurs during Raw_Spread zero-spread periods (97.81% of ticks).
Mean reversion validated: 87.3% revert within 10 ticks.';
```

---

## Implementation Guidelines

### Research Script Organization

**Location**: `docs/research/{research-topic}/scripts/`

**Naming**: `phase{N}_{operation}.py` (e.g., `phase2_mean_reversion.py`)

**Requirements**:
- Use pandas or Polars for ASOF operations
- Document data sources and temporal tolerance
- Include validation methodology
- Link to research reports

### Materialization Script

**Future LHF Feature**: `make materialize-research` command

**Process**:
1. Load validated research results (CSV, Parquet, or pandas DataFrame)
2. Create DuckDB table with appropriate schema
3. Generate COMMENT ON statements from research documentation
4. Create SQL views for common query patterns
5. Update database schema documentation

**Example**:
```bash
# Future command (not yet implemented)
make materialize-research \
    RESEARCH_DIR=docs/research/eurusd-zero-spread-deviations \
    OUTPUT_TABLE=eurusd_spread_deviations \
    DATABASE=data/eurusd.duckdb
```

---

## Performance Considerations

### ASOF Join Tolerance

**Recommendation**: 10-second tolerance for tick-level temporal matching

**Rationale**: Balances precision with data availability. Exness tick data shows irregular intervals (1µs to 130.61s), requiring tolerance for sparse periods.

### Materialization Frequency

**Research Results**: One-time materialization after validation
**Production Data**: Not applicable (research findings are static)

### Query Optimization

**On Materialized Tables**:
- Date range filtering: `WHERE Timestamp BETWEEN x AND y`
- Aggregations: `GROUP BY DATE_TRUNC('hour', Timestamp)`
- Views: Pre-defined query patterns with COMMENT ON

**Performance Target**: Sub-15ms for all queries on materialized research results

---

## References

- **DuckDB ASOF JOIN**: https://duckdb.org/docs/stable/guides/sql_features/asof_join (added Sept 2023)
- **pandas merge_asof**: https://pandas.pydata.org/docs/reference/api/pandas.merge_asof.html
- **Polars join_asof**: https://docs.pola.rs/api/python/stable/reference/dataframe/api/polars.DataFrame.join_asof.html
- **Performance Benchmark**: `/tmp/test_asof_spike.py` (880K ticks, 1 month EURUSD)

---

**Next Steps**: Implement `make materialize-research` command for research lifecycle automation.
