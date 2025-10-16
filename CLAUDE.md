# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**Project**: Forex tick data preprocessing with unified DuckDB storage
**Version**: 2.0.0 (Architecture) + 1.3.0 (Implementation)
**Last Updated**: 2025-10-16

---

## Documentation Hub

**Architecture**: Link Farm + Hub-and-Spoke with Progressive Disclosure

### User Documentation
- **[README.md](README.md)** - Installation, API reference, usage examples

### AI Assistant Documentation
- **[docs/README.md](docs/README.md)** - Architecture, planning, research findings
- **[Makefile](Makefile)** - Module introspection commands (module-stats, module-complexity, module-deps)

### Implementation
- **[src/exness_data_preprocess/](src/exness_data_preprocess/)** - Source code modules
- **[tests/](tests/)** - Test suite (48 tests)
- **[examples/](examples/)** - Usage examples (basic_usage.py, batch_processing.py)

---

## Architecture Summary

### Storage Pattern (v2.0.0)
- **Single DuckDB file per instrument** (eurusd.duckdb)
- **Incremental updates** with automatic gap detection
- **PRIMARY KEY constraints** prevent duplicates
- **Sub-15ms query performance** with date range filtering

### Module Pattern (v1.3.0)
- **Facade orchestrator** (processor.py) coordinating 7 specialized modules
- **Separation of concerns**: downloader, tick_loader, database_manager, session_detector, gap_detector, ohlc_generator, query_engine
- **SLO-based design**: Availability, Correctness, Observability, Maintainability
- **Off-the-shelf libraries**: httpx, pandas, DuckDB, exchange_calendars

### Schema (v1.5.0)
- **Phase7 30-column OHLC** with dual-variant spreads (Raw_Spread + Standard)
- **10 global exchange sessions** covering 24-hour forex trading
- **Self-documenting** via DuckDB COMMENT ON statements

**Complete Details**: See [`docs/README.md`](docs/README.md) - Architecture documentation hub

**Database Schema**: See [`docs/DATABASE_SCHEMA.md`](docs/DATABASE_SCHEMA.md) - Complete schema reference

**Data Sources**: See [`docs/EXNESS_DATA_SOURCES.md`](docs/EXNESS_DATA_SOURCES.md) - URL patterns and variants

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
# Run all tests (48 tests)
uv run pytest

# Run with coverage
uv run pytest --cov=exness_data_preprocess --cov-report=html

# Run specific test
uv run pytest tests/test_processor.py::test_update_data -v
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
# Show current line counts
make module-stats

# Show cyclomatic complexity (requires radon)
make module-complexity

# Show dependency tree (requires pipdeptree)
make module-deps
```

**Details**: See [`Makefile`](Makefile) - Introspection command implementations

### Building and Publishing
```bash
# Build package
uv build

# Test installation locally
uv tool install --editable .

# Publish to PyPI (requires PYPI_TOKEN)
doppler run --project claude-config --config dev -- uv publish --token "$PYPI_TOKEN"
```

**CI/CD Setup**: See [`GITHUB_PYPI_SETUP.md`](GITHUB_PYPI_SETUP.md) - Complete GitHub Actions + PyPI configuration

---

## References

- **Exness Data**: https://ticks.ex2archive.com/ - Public tick data repository
- **DuckDB**: https://duckdb.org/ - Embedded OLAP database
- **exchange_calendars**: https://github.com/gerrymanoim/exchange_calendars - Trading calendar library

---

**Maintenance**: Review this file when adding new top-level documentation or changing core architecture patterns
