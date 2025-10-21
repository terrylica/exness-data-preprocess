# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**Architecture**: Forex tick data preprocessing with unified single-file DuckDB storage

**Full Documentation**: [`README.md`](README.md) - Installation, usage, API reference

---

## Documentation Hub

### User Documentation
- **[README.md](README.md)** - Installation, API reference, usage examples
- **[examples/basic_usage.py](examples/basic_usage.py)** - Download, query, coverage operations
- **[examples/batch_processing.py](examples/batch_processing.py)** - Multi-instrument parallel processing

### AI Assistant Documentation
- **[docs/README.md](docs/README.md)** - Architecture, planning, research findings
- **[docs/MODULE_ARCHITECTURE.md](docs/MODULE_ARCHITECTURE.md)** - Complete module documentation with SLOs (v1.7.0)
- **[docs/DATABASE_SCHEMA.md](docs/DATABASE_SCHEMA.md)** - Complete database schema with self-documentation
- **[docs/RESEARCH_PATTERNS.md](docs/RESEARCH_PATTERNS.md)** - Research lifecycle and tool selection (v1.0.0)
- **[docs/UNIFIED_DUCKDB_PLAN_v2.md](docs/UNIFIED_DUCKDB_PLAN_v2.md)** - v2.0.0 architecture specification
- **[docs/EXNESS_DATA_SOURCES.md](docs/EXNESS_DATA_SOURCES.md)** - Data source variants and URLs
- **[Makefile](Makefile)** - Module introspection commands (module-stats, module-complexity, module-deps)

### Optimization Plans (v1.7.0)
- **[docs/PHASE2_SESSION_VECTORIZATION_PLAN.yaml](docs/PHASE2_SESSION_VECTORIZATION_PLAN.yaml)** - SSoT plan v2.0.0 (2.2x speedup)
- **[docs/PHASE3_SQL_GAP_DETECTION_PLAN.yaml](docs/PHASE3_SQL_GAP_DETECTION_PLAN.yaml)** - SSoT plan v2.0.0 (complete coverage)
- **[docs/validation/SPIKE_TEST_RESULTS_PHASE1_2025-10-18.md](docs/validation/SPIKE_TEST_RESULTS_PHASE1_2025-10-18.md)** - Phase 1 validation
- **[docs/validation/SPIKE_TEST_RESULTS_PHASE2_2025-10-18.md](docs/validation/SPIKE_TEST_RESULTS_PHASE2_2025-10-18.md)** - Phase 2 validation

### Implementation
- **src/exness_data_preprocess/** - Source code (7 specialized modules + facade)
- **tests/** - Test suite (48 tests, 100% passing)
- **[CONTRIBUTING.md](CONTRIBUTING.md)** - Contribution guidelines

---

## Architecture Summary

### Storage Pattern (v2.0.0)
- **Single DuckDB file per instrument** (e.g., eurusd.duckdb containing all historical data)
- **Dual-variant storage** (Raw_Spread + Standard in same database)
- **Incremental updates** with automatic gap detection
- **PRIMARY KEY constraints** prevent duplicates during updates
- **Sub-15ms query performance** with date range filtering
- **On-demand resampling** to any timeframe (5m, 1h, 1d)

**Complete Specification**: [`docs/UNIFIED_DUCKDB_PLAN_v2.md`](docs/UNIFIED_DUCKDB_PLAN_v2.md)

### Module Pattern (v1.7.0)
- **Facade orchestrator** (processor.py) coordinating 7 specialized modules
- **Separation of concerns** with single-responsibility modules
- **SLO-based design** (Availability, Correctness, Observability, Maintainability)
- **Off-the-shelf libraries** (httpx, pandas, DuckDB, exchange_calendars)
- **Zero regressions** (48 tests pass)

**Modules**:
1. **processor.py** - Thin orchestrator facade
2. **downloader.py** - HTTP download operations
3. **tick_loader.py** - CSV parsing
4. **database_manager.py** - Database operations
5. **session_detector.py** - Holiday and session detection (v1.7.0: vectorized, 2.2x speedup)
6. **gap_detector.py** - Incremental update logic (v1.7.0: SQL gap detection, complete coverage)
7. **ohlc_generator.py** - Phase7 OHLC generation (v1.7.0: incremental, 7.3x speedup)
8. **query_engine.py** - Query operations

**Complete Details**: [`docs/MODULE_ARCHITECTURE.md`](docs/MODULE_ARCHITECTURE.md)

### Performance Optimizations (v1.7.0)
- **Incremental OHLC Generation** (Phase 1): 7.3x speedup
  - Optional date-range filtering for regeneration
  - Measured: 8.05s → 1.10s for incremental updates (7 months)
  - SSoT: [`docs/validation/SPIKE_TEST_RESULTS_PHASE1_2025-10-18.md`](docs/validation/SPIKE_TEST_RESULTS_PHASE1_2025-10-18.md)

- **Session Vectorization** (Phase 2): 2.2x speedup
  - Pre-compute trading minutes, vectorized .isin() lookup
  - Measured: 5.99s → 2.69s for 302K bars across 10 exchanges
  - Combined Phase 1+2: **~16x total speedup** (8.05s → 0.50s)
  - SSoT: [`docs/PHASE2_SESSION_VECTORIZATION_PLAN.yaml`](docs/PHASE2_SESSION_VECTORIZATION_PLAN.yaml)
  - Validation: [`docs/validation/SPIKE_TEST_RESULTS_PHASE2_2025-10-18.md`](docs/validation/SPIKE_TEST_RESULTS_PHASE2_2025-10-18.md)

- **SQL Gap Detection** (Phase 3): Complete coverage + 46% LOC reduction
  - SQL EXCEPT query detects ALL gaps (internal + edges)
  - Bug fix: Now detects internal gaps missed by Python MIN/MAX
  - Measured: 41 → 42 gaps detected (spike test validation)
  - SSoT: [`docs/PHASE3_SQL_GAP_DETECTION_PLAN.yaml`](docs/PHASE3_SQL_GAP_DETECTION_PLAN.yaml)

**Pattern**: Spike test first (validate theory) → Implement → Iterative SSoT plan updates

### Schema (v1.6.0)
- **Phase7 30-column OHLC** with dual-variant spreads
- **BID-only OHLC** from Raw_Spread execution prices
- **Normalized metrics** (range_per_spread, range_per_tick, body_per_spread, body_per_tick)
- **10 global exchange sessions with trading hour detection** (NYSE, LSE, XSWX, XFRA, XTSE, XNZE, XTKS, XASX, XHKG, XSES)
- **Holiday tracking** (US, UK, major holidays)
- **Self-documenting** via COMMENT ON statements

**Complete Schema**: [`docs/DATABASE_SCHEMA.md`](docs/DATABASE_SCHEMA.md)

### Data Sources
- **Source**: https://ticks.ex2archive.com/ (public Exness tick data)
- **Primary**: Raw_Spread variant (97.81% zero-spreads, execution prices)
- **Reference**: Standard variant (0% zero-spreads, market quotes)
- **Format**: Monthly ZIP files with microsecond-precision CSV

**Complete Guide**: [`docs/EXNESS_DATA_SOURCES.md`](docs/EXNESS_DATA_SOURCES.md)

### Research Patterns (v1.0.0)
- **Lifecycle**: Explore (pandas/Polars) → Validate → Graduate (DuckDB) → Query (SQL)
- **ASOF Performance**: pandas/Polars 0.04s, DuckDB 0.89s at 880K ticks (24x difference)
- **Tool Selection**: pandas/Polars for tick-level temporal matching, DuckDB for materialized results
- **Hybrid Pattern**: ASOF operations stay in pandas, validated findings materialize to DuckDB tables
- **Single Source of Truth**: DuckDB stores validated research outcomes with COMMENT ON documentation

**Complete Specification**: [`docs/RESEARCH_PATTERNS.md`](docs/RESEARCH_PATTERNS.md)

---

## Development Commands

### Setup
```bash
# Install with development dependencies
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

# Run specific test file
uv run pytest tests/test_basic.py -v
```

### Code Quality
```bash
# Format code
uv run ruff format .

# Lint and auto-fix
uv run ruff check --fix .

# Type checking
uv run mypy src/
```

### Module Introspection
```bash
# Show current line counts (always accurate)
make module-stats

# Show cyclomatic complexity (requires radon)
make module-complexity

# Show dependency tree (requires pipdeptree)
make module-deps
```

### Building and Publishing
```bash
# Build package
uv build

# Test installation locally
uv tool install --editable .

# Publish to PyPI (requires PYPI_TOKEN)
doppler run --project claude-config --config dev -- uv publish --token "$PYPI_TOKEN"
```

**Complete Development Guide**: [`README.md`](README.md) (Installation section)

---

## References

- **Exness Data**: https://ticks.ex2archive.com/
- **DuckDB**: https://duckdb.org/
- **Apache Parquet**: https://parquet.apache.org/
- **Zstd Compression**: https://facebook.github.io/zstd/

---

**Version**: 2.0.0 (Architecture) + 1.7.0 (Implementation) + 1.0.0 (Research Patterns)
**Last Updated**: 2025-10-18
**Architecture**: Unified Single-File DuckDB Storage with Incremental Updates
**Implementation**: Facade Pattern with 7 Specialized Modules + Performance Optimizations (~16x speedup)
**Research**: Hybrid Materialization (pandas/Polars exploration, DuckDB validated results)
