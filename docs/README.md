# Documentation Hub

**Architecture**: Link Farm + Hub-and-Spoke with Progressive Disclosure

**Project Overview**: [`../README.md`](../README.md) - Full project documentation

**Project Memory**: [`../CLAUDE.md`](../CLAUDE.md) - Essential architecture decisions and quick links

---

## Architecture & Planning

### Unified Single-File DuckDB Architecture v2.0.0

**Comprehensive Plan**: [`UNIFIED_DUCKDB_PLAN_v2.md`](UNIFIED_DUCKDB_PLAN_v2.md)

**Database Schema**: [`DATABASE_SCHEMA.md`](DATABASE_SCHEMA.md) - Complete table structure, relationships, and query examples

**Decision**: Single DuckDB file per instrument (eurusd.duckdb, not monthly files)

**Key Advantages**:

- ✅ **Single file per instrument**: All years in one database (no file fragmentation)
- ✅ **Incremental updates**: Automatic gap detection, download only missing months
- ✅ **PRIMARY KEY constraints**: Prevents duplicates during incremental updates
- ✅ **Performance**: <15ms queries for all timeframes
- ✅ **Phase7 Compliant**: Dual-variant 13-column (v1.2.0) schema
- ✅ **SQL on Ticks**: Direct tick analysis with date range filtering
- ✅ **Scalability**: 2.08 GB for 13 months, ~4.8 GB for 3 years

**Validation**: Real EURUSD Oct 2024 - Oct 2025 (18.6M Raw_Spread ticks, 19.6M Standard ticks, 413K OHLC bars)

**Implementation Status**: ✅ Completed and validated (2025-10-12)

**Legacy Plan**: [`archive/UNIFIED_DUCKDB_PLAN_v1.0.0_LEGACY.md`](archive/UNIFIED_DUCKDB_PLAN_v1.0.0_LEGACY.md) - Monthly-file architecture (archived)

---

### Implementation Architecture v1.3.0

**Refactoring Plans**:
- [`plans/PHASE7_v1.6.0_REFACTORING_PROGRESS.md`](plans/PHASE7_v1.6.0_REFACTORING_PROGRESS.md) - Complete refactoring progress
- [`plans/REFACTORING_CHECKLIST.md`](plans/REFACTORING_CHECKLIST.md) - Quick reference checklist

**Pattern**: Facade with 7 specialized modules (414 lines processor, 1,146 lines extracted)

**Key Modules**:
- **processor.py** (414 lines) - Thin orchestrator facade, delegates to modules
- **downloader.py** (89 lines) - HTTP download operations (httpx)
- **tick_loader.py** (67 lines) - CSV parsing (pandas)
- **database_manager.py** (213 lines) - Database operations (DuckDB)
- **session_detector.py** (121 lines) - Holiday and session detection (exchange_calendars)
- **gap_detector.py** (163 lines) - Incremental update logic
- **ohlc_generator.py** (210 lines) - Phase7 30-column OHLC generation
- **query_engine.py** (283 lines) - Query operations with on-demand resampling

**Design Principles**:
- ✅ **Separation of concerns**: Each module has single responsibility
- ✅ **SLO-based design**: All modules define Availability, Correctness, Observability, Maintainability
- ✅ **Off-the-shelf libraries**: httpx, pandas, DuckDB, exchange_calendars (no custom implementations)
- ✅ **Zero regressions**: All 48 tests pass after 7-module extraction (53% line reduction)

**Status**: Phase 4 Complete (2025-10-15)

---

## Data Sources

### Exness Tick Data

**Complete Guide**: [`EXNESS_DATA_SOURCES.md`](EXNESS_DATA_SOURCES.md)

**Quick Reference**:

- **URL Pattern**: `https://ticks.ex2archive.com/ticks/{VARIANT}/{YEAR}/{MONTH}/`
- **4 Variants**: Standard, Raw_Spread, Standart_Plus, Zero_Spread
- **Phase7 Requires**: Raw_Spread (primary) + Standard (reference)
- **Storage**: ~11 MB per month per instrument (unified DuckDB)

**Discovery**:

```bash
curl -s "https://ticks.ex2archive.com/ticks/" | jq -r '.[] | .name' | grep -i "EURUSD"
```

---

## Research Findings

### Compression Benchmarks

**Location**: [`research/compression-benchmarks/README.md`](research/compression-benchmarks/README.md)

**Decision**: Parquet with Zstd-22 (lossless, 9% smaller than ZIP)

**Key Findings**:

- ✅ **Zstd-22**: 4.77 MB, 0.78s write, 0.014s read, queryable
- ❌ **Brotli-11**: 4.34 MB but 13.67s write (17.5x slower)
- ❌ **Delta Encoding**: 1.59 MB but LOSSY (36 pips error)

**Scripts**:

- `test_parquet_compression_methods.py` - Initial codec comparison
- `test_all_compression_methods.py` - Comprehensive benchmark
- `test_delta_encoding_properly.py` - Adversarial audit (revealed lossiness)

---

### Zero-Spread Deviation Analysis

**Location**: [`research/eurusd-zero-spread-deviations/README.md`](research/eurusd-zero-spread-deviations/README.md)

**Period**: Sep 2024 baseline + 16-month validation (Jan-Aug 2024+2025)

**Key Findings**:

- ✅ **Mean Reversion**: 87.3% ± 1.9% stable (ROBUST signal)
- ⚠️ **Volatility Prediction**: Regime shift 2024→2025 (R²: 0.371→0.209)
- ✅ **Phase7 Methodology**: Dual-variant BID-only OHLC validated

**Documentation Structure**:

- [`01-methodology.md`](research/eurusd-zero-spread-deviations/01-methodology.md) - Data sources, formulas, SLOs
- [`03-multiperiod-validation.md`](research/eurusd-zero-spread-deviations/03-multiperiod-validation.md) - Temporal stability testing
- [`04-discoveries-and-plan-evolution.md`](research/eurusd-zero-spread-deviations/04-discoveries-and-plan-evolution.md) - Version-tracked findings
- [`data/plan/phase7_bid_ohlc_construction_v1.1.0.md`](research/eurusd-zero-spread-deviations/data/plan/phase7_bid_ohlc_construction_v1.1.0.md) - OHLC specification

**Phase7 Schema** (30 columns, v1.5.0):
- **Definition**: [`../src/exness_data_preprocess/schema.py`](../src/exness_data_preprocess/schema.py)
- **Comprehensive Guide**: [`DATABASE_SCHEMA.md`](DATABASE_SCHEMA.md)
- **Architecture**: Exchange Registry Pattern with 10 global exchange sessions

---

### EURUSD Spread Analysis

**Location**: [`research/eurusd-spread-analysis/README.md`](research/eurusd-spread-analysis/README.md)

**Method**: Modal-band-excluded variance estimation

---

## Implementation Plans

### OpenAPI Specifications

- **[`implementation-plan.yaml`](implementation-plan.yaml)** - Machine-readable project specification (OpenAPI 3.1.1)
- **[`planning-index.yaml`](planning-index.yaml)** - Planning document index

**Usage**: AI coding assistants (Cursor IDE, Claude Code CLI) can parse these specs

---

## Validation & Test Artifacts

### Unified DuckDB Architecture Test

**Location**: `/tmp/exness-duckdb-test/`

**Key Files**:

- `FINDINGS.md` - Validation report (real EURUSD Sep 2024 data)
- `test_real_unified.py` - Test script (925K + 1.08M ticks)
- `eurusd_real_2024_09.duckdb` - Test database (11.26 MB)
- `real_results.json` - Benchmark results

**Validation Results**:

- ✅ Irregular ticks (1µs to 130.61s intervals)
- ✅ Regular OHLC (0 unaligned bars)
- ✅ Phase7 30-column (v1.5.0) schema with 10 global exchange sessions
- ✅ Query performance (<15ms all timeframes)

**Conclusion**: Unified DuckDB architecture is production-ready

---

## Quick Navigation

| Topic                       | Document                                                                                                                                                                             | Type                   |
| --------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ---------------------- |
| **v2.0.0 Architecture**     | [`UNIFIED_DUCKDB_PLAN_v2.md`](UNIFIED_DUCKDB_PLAN_v2.md)                                                                                                                             | ⭐ Implementation Plan |
| **Database Schema**         | [`DATABASE_SCHEMA.md`](DATABASE_SCHEMA.md)                                                                                                                                            | ⭐ Schema Reference    |
| **v1.0.0 Architecture**     | [`archive/UNIFIED_DUCKDB_PLAN_v1.0.0_LEGACY.md`](archive/UNIFIED_DUCKDB_PLAN_v1.0.0_LEGACY.md)                                                                                       | Archived Plan          |
| **Data Sources**            | [`EXNESS_DATA_SOURCES.md`](EXNESS_DATA_SOURCES.md)                                                                                                                                   | Guide                  |
| **Compression**             | [`research/compression-benchmarks/README.md`](research/compression-benchmarks/README.md)                                                                                             | Research               |
| **Zero-Spread**             | [`research/eurusd-zero-spread-deviations/README.md`](research/eurusd-zero-spread-deviations/README.md)                                                                               | Research               |
| **Phase7 v1.1.0**           | [`research/eurusd-zero-spread-deviations/data/plan/phase7_bid_ohlc_construction_v1.1.0.md`](research/eurusd-zero-spread-deviations/data/plan/phase7_bid_ohlc_construction_v1.1.0.md) | Specification          |
| **Methodology**             | [`research/eurusd-zero-spread-deviations/01-methodology.md`](research/eurusd-zero-spread-deviations/01-methodology.md)                                                               | Reference              |
| **API Reference**           | [`../README.md`](../README.md)                                                                                                                                                       | Main Doc               |
| **Examples**                | [`../examples/`](../examples/)                                                                                                                                                       | Code Samples           |

---

## Contributing to Documentation

### Structure Principles

1. **Link Farm + Hub-and-Spoke**: Each directory has README.md as hub
2. **Progressive Disclosure**: Essentials first, links to deeper content
3. **Single Source of Truth**: One authoritative document per topic
4. **Absolute Paths**: Always use absolute paths in documentation

### Documentation Types

- **Research**: Empirical findings with reproducible scripts
- **Guides**: How-to documentation with examples
- **Specifications**: OpenAPI/JSON Schema machine-readable specs
- **References**: Technical specifications and methodologies

### File Naming Conventions

- **README.md**: Hub document (directory index)
- **{topic}\_v{version}.md**: Versioned specifications (e.g., `phase7_bid_ohlc_construction_v1.1.0.md`)
- **{phase}-{topic}.md**: Sequential documents (e.g., `01-methodology.md`)
- **{topic}-report.md**: Research findings (e.g., `phase2-mean-reversion-report.md`)

---

**Last Updated**: 2025-10-15
**Maintainer**: Terry Li <terry@eonlabs.com>
