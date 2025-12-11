# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**Package**: `exness-data-preprocess` — Forex tick data preprocessing with DuckDB (local) and ClickHouse (cloud) backends

**Version**: See [`pyproject.toml`](pyproject.toml) line 3 (SSoT via semantic-release)

**Quick Start**: [`README.md`](README.md) — Installation, API reference, usage examples

---

## Documentation Hub (Progressive Disclosure)

### Essential Links

| Topic            | SSoT Document                                                      | Purpose                               |
| ---------------- | ------------------------------------------------------------------ | ------------------------------------- |
| **User Guide**   | [`README.md`](README.md)                                           | Installation, API, examples           |
| **Architecture** | [`docs/UNIFIED_DUCKDB_PLAN_v2.md`](docs/UNIFIED_DUCKDB_PLAN_v2.md) | Unified single-file DuckDB design     |
| **Schema**       | [`docs/DATABASE_SCHEMA.md`](docs/DATABASE_SCHEMA.md)               | Phase7 30-column OHLC specification   |
| **Modules**      | [`docs/MODULE_ARCHITECTURE.md`](docs/MODULE_ARCHITECTURE.md)       | 19 modules with SLOs                  |
| **Data Sources** | [`docs/EXNESS_DATA_SOURCES.md`](docs/EXNESS_DATA_SOURCES.md)       | Exness tick data variants             |
| **Research**     | [`docs/RESEARCH_PATTERNS.md`](docs/RESEARCH_PATTERNS.md)           | Hybrid materialization lifecycle      |
| **Tasks**        | [`.mise.toml`](.mise.toml)                                         | Validation, ClickHouse, DBeaver tasks |
| **Contributing** | [`CONTRIBUTING.md`](CONTRIBUTING.md)                               | Development guidelines                |

### Deep Dives (On-Demand)

| Topic              | Location                               | When to Read                     |
| ------------------ | -------------------------------------- | -------------------------------- |
| ADRs               | [`docs/adr/`](docs/adr/)               | Architecture decisions           |
| Design Specs       | [`docs/design/`](docs/design/)         | Implementation blueprints        |
| Optimization Plans | [`docs/phases/`](docs/phases/)         | Phase 2/3 SSoT YAML plans        |
| Validation Results | [`docs/validation/`](docs/validation/) | Spike test proofs                |
| Research Analysis  | [`docs/research/`](docs/research/)     | Zero-spread, compression studies |

---

## Architecture Overview

### Dual Backend Design

| Backend        | Storage                                   | Use Case          | Entry Point           |
| -------------- | ----------------------------------------- | ----------------- | --------------------- |
| **DuckDB**     | One file per instrument (`eurusd.duckdb`) | Local development | `ExnessDataProcessor` |
| **ClickHouse** | Single table with instrument column       | Cloud deployment  | `ClickHouseManager`   |

### Module Structure (19 Modules)

**DuckDB Backend (8 modules)**:

- `processor.py` — Thin orchestrator facade
- `downloader.py` — HTTP download operations
- `tick_loader.py` — CSV parsing
- `database_manager.py` — Database operations
- `session_detector.py` — Holiday/session detection (vectorized)
- `gap_detector.py` — Incremental update logic (SQL-based)
- `ohlc_generator.py` — Phase7 OHLC generation
- `query_engine.py` — Query operations

**ClickHouse Backend (7 modules)**:

- `clickhouse_manager.py` — Schema management, data loading
- `clickhouse_gap_detector.py` — Gap detection for ClickHouse
- `clickhouse_query_engine.py` — Query with pagination
- `clickhouse_ohlc_generator.py` — OHLC generation
- `clickhouse_client.py` — Connection factory with error handling
- `clickhouse_base.py` — Shared mixin for client lifecycle
- `clickhouse_cloud.py` — Cloud-specific configuration

**Shared (4 modules)**:

- `config.py` — Configuration management
- `models.py` — Pydantic models (UpdateResult, CoverageInfo, etc.)
- `schema.py` — SQL schema definitions
- `exchanges.py` — Exchange calendar integration

**Complete Details**: [`docs/MODULE_ARCHITECTURE.md`](docs/MODULE_ARCHITECTURE.md)

---

## Development Commands

### Quick Reference

```bash
# Setup
uv sync --dev

# Testing (48 tests)
uv run pytest                          # All tests
mise run validate                      # Full E2E validation

# Linting
uv run ruff check --fix src/ tests/

# ClickHouse
mise run clickhouse:start              # Start local server
mise run clickhouse:status             # Check connection
mise run validate:clickhouse           # E2E ClickHouse tests

# Build & Publish
uv build
mise run db-client-generate            # Generate DBeaver config
```

### mise Tasks

All validation and tooling tasks are defined in [`.mise.toml`](.mise.toml):

| Task                           | Description                                                               |
| ------------------------------ | ------------------------------------------------------------------------- |
| `mise run validate`            | Full E2E pipeline (imports, lint, typecheck, test, build, install, mixin) |
| `mise run validate:clickhouse` | ClickHouse E2E tests (requires running server)                            |
| `mise run clickhouse:start`    | Start mise-installed ClickHouse                                           |
| `mise run db-client-generate`  | Generate DBeaver config from Pydantic model                               |
| `mise run ci`                  | Simulate CI pipeline locally                                              |

---

## Key Patterns

### Performance Optimizations (~16x total speedup)

| Phase | Optimization          | Speedup           | SSoT                                                                                                                 |
| ----- | --------------------- | ----------------- | -------------------------------------------------------------------------------------------------------------------- |
| 1     | Incremental OHLC      | 7.3x              | [`docs/validation/SPIKE_TEST_RESULTS_PHASE1_2025-10-18.md`](docs/validation/SPIKE_TEST_RESULTS_PHASE1_2025-10-18.md) |
| 2     | Session Vectorization | 2.2x              | [`docs/phases/PHASE2_SESSION_VECTORIZATION_PLAN.yaml`](docs/phases/PHASE2_SESSION_VECTORIZATION_PLAN.yaml)           |
| 3     | SQL Gap Detection     | 46% LOC reduction | [`docs/phases/PHASE3_SQL_GAP_DETECTION_PLAN.yaml`](docs/phases/PHASE3_SQL_GAP_DETECTION_PLAN.yaml)                   |

### Research Lifecycle

```
Explore (pandas/Polars) → Validate → Graduate (DuckDB) → Query (SQL)
```

**SSoT**: [`docs/RESEARCH_PATTERNS.md`](docs/RESEARCH_PATTERNS.md)

---

## References

- **Exness Data**: <https://ticks.ex2archive.com/>
- **DuckDB**: <https://duckdb.org/>
- **ClickHouse**: <https://clickhouse.com/>

---

**Last Updated**: 2025-12-10
