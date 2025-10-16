# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**Architecture**: Professional forex tick data preprocessing with unified single-file DuckDB storage

**Full Documentation**: [`README.md`](README.md) - Installation, usage, API reference

---

## Documentation Hub

### User Documentation
- **[README.md](README.md)** - Installation, API reference, usage examples
- **[examples/basic_usage.py](examples/basic_usage.py)** - Download, query, coverage operations
- **[examples/batch_processing.py](examples/batch_processing.py)** - Multi-instrument parallel processing

### AI Assistant Documentation
- **[docs/README.md](docs/README.md)** - Architecture, planning, research findings
- **[docs/MODULE_ARCHITECTURE.md](docs/MODULE_ARCHITECTURE.md)** - Complete module documentation with SLOs
- **[docs/DATABASE_SCHEMA.md](docs/DATABASE_SCHEMA.md)** - Complete database schema with self-documentation
- **[docs/UNIFIED_DUCKDB_PLAN_v2.md](docs/UNIFIED_DUCKDB_PLAN_v2.md)** - v2.0.0 architecture specification
- **[docs/EXNESS_DATA_SOURCES.md](docs/EXNESS_DATA_SOURCES.md)** - Data source variants and URLs
- **[Makefile](Makefile)** - Module introspection commands (module-stats, module-complexity, module-deps)

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

### Module Pattern (v1.3.0)
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
5. **session_detector.py** - Holiday and session detection
6. **gap_detector.py** - Incremental update logic
7. **ohlc_generator.py** - Phase7 OHLC generation
8. **query_engine.py** - Query operations

**Complete Details**: [`docs/MODULE_ARCHITECTURE.md`](docs/MODULE_ARCHITECTURE.md)

### Schema (v1.5.0)
- **Phase7 30-column OHLC** with dual-variant spreads
- **BID-only OHLC** from Raw_Spread execution prices
- **Normalized metrics** (range_per_spread, range_per_tick, body_per_spread, body_per_tick)
- **10 global exchange sessions** (NYSE, LSE, XSWX, XFRA, XTSE, XNZE, XTKS, XASX, XHKG, XSES)
- **Holiday tracking** (US, UK, major holidays)
- **Self-documenting** via COMMENT ON statements

**Complete Schema**: [`docs/DATABASE_SCHEMA.md`](docs/DATABASE_SCHEMA.md)

### Data Sources
- **Source**: https://ticks.ex2archive.com/ (public Exness tick data)
- **Primary**: Raw_Spread variant (97.81% zero-spreads, execution prices)
- **Reference**: Standard variant (0% zero-spreads, market quotes)
- **Format**: Monthly ZIP files with microsecond-precision CSV

**Complete Guide**: [`docs/EXNESS_DATA_SOURCES.md`](docs/EXNESS_DATA_SOURCES.md)

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
uv run pytest tests/test_processor.py -v
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

**Version**: 2.0.0 (Architecture) + 1.3.0 (Implementation)
**Last Updated**: 2025-10-16
**Architecture**: Unified Single-File DuckDB Storage with Incremental Updates
**Implementation**: Facade Pattern with 7 Specialized Modules
