# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**Package**: `exness-data-preprocess` — Forex tick data preprocessing with ClickHouse backend

**Version**: See [`pyproject.toml`](/pyproject.toml) line 3 (SSoT via semantic-release)

**Quick Start**: [`README.md`](/README.md) — Installation, API reference, usage examples

---

## Documentation Hub (Progressive Disclosure)

### Essential Links

| Topic            | SSoT Document                                                                                          | Purpose                      |
| ---------------- | ------------------------------------------------------------------------------------------------------ | ---------------------------- |
| **User Guide**   | [`README.md`](/README.md)                                                                               | Installation, API, examples  |
| **Architecture** | [`docs/adr/2025-12-11-duckdb-removal-clickhouse.md`](/docs/adr/2025-12-11-duckdb-removal-clickhouse.md) | ClickHouse-only decision     |
| **Schema**       | [`docs/DATABASE_SCHEMA.md`](/docs/DATABASE_SCHEMA.md)                                                   | 26-column OHLC specification |
| **Modules**      | [`docs/MODULE_ARCHITECTURE.md`](/docs/MODULE_ARCHITECTURE.md)                                           | 13 modules with SLOs         |
| **Data Sources** | [`docs/EXNESS_DATA_SOURCES.md`](/docs/EXNESS_DATA_SOURCES.md)                                           | Exness tick data variants    |
| **Tasks**        | [`.mise.toml`](/.mise.toml)                                                                             | Validation, ClickHouse tasks |
| **Contributing** | [`CONTRIBUTING.md`](/CONTRIBUTING.md)                                                                   | Development guidelines       |

### Deep Dives (On-Demand)

| Topic              | Location                               | When to Read              |
| ------------------ | -------------------------------------- | ------------------------- |
| ADRs               | [`docs/adr/`](/docs/adr/)               | Architecture decisions    |
| Design Specs       | [`docs/design/`](/docs/design/)         | Implementation blueprints |
| Validation Results | [`docs/validation/`](/docs/validation/) | Spike test proofs         |

---

## Architecture Overview (v2.0.0)

### ClickHouse-Only Backend

**ADR**: [`docs/adr/2025-12-11-duckdb-removal-clickhouse.md`](/docs/adr/2025-12-11-duckdb-removal-clickhouse.md)

| Feature         | Description                                      |
| --------------- | ------------------------------------------------ |
| **Database**    | `exness` (single database for all instruments)   |
| **Tables**      | `raw_spread_ticks`, `standard_ticks`, `ohlc_1m`  |
| **Engine**      | ReplacingMergeTree (deduplication at merge time) |
| **Connection**  | localhost:8123 (local) or cloud via env vars     |
| **Entry Point** | `ExnessDataProcessor`                            |

### Module Structure (13 Modules)

**ClickHouse Backend (7 modules)**:

- `processor.py` — Main orchestrator with ClickHouse backend
- `clickhouse_manager.py` — Schema management, data loading
- `clickhouse_gap_detector.py` — Gap detection for incremental updates
- `clickhouse_query_engine.py` — Query with pagination
- `clickhouse_ohlc_generator.py` — OHLC generation
- `clickhouse_client.py` — Connection factory with error handling
- `clickhouse_base.py` — Shared mixin for client lifecycle

**Shared (6 modules)**:

- `downloader.py` — HTTP download operations
- `tick_loader.py` — CSV parsing
- `session_detector.py` — Holiday/session detection (vectorized)
- `config.py` — Configuration management
- `models.py` — Pydantic models (UpdateResult, CoverageInfo, etc.)
- `exchanges.py` — Exchange calendar integration

**Deleted in v2.0.0**:

- ~~`database_manager.py`~~ — DuckDB database operations
- ~~`gap_detector.py`~~ — DuckDB gap detection
- ~~`ohlc_generator.py`~~ — DuckDB OHLC generation
- ~~`query_engine.py`~~ — DuckDB query operations
- ~~`schema.py`~~ — DuckDB SQL schema definitions

---

## Development Commands

### Quick Reference

```bash
# Setup
uv sync --dev

# Testing (45 tests)
uv run pytest                          # All tests
mise run validate                      # Full E2E validation (requires ClickHouse)

# Linting
uv run ruff check --fix src/ tests/

# ClickHouse (required for full validation)
mise run clickhouse:start              # Start local server
mise run clickhouse:status             # Check connection
mise run clickhouse:ensure             # Fail fast if not running

# Build & Publish
uv build
```

### mise Tasks

All validation and tooling tasks are defined in [`.mise.toml`](/.mise.toml):

| Task                           | Description                             |
| ------------------------------ | --------------------------------------- |
| `mise run validate`            | Full E2E pipeline (requires ClickHouse) |
| `mise run clickhouse:ensure`   | Fail fast if ClickHouse not running     |
| `mise run clickhouse:start`    | Start mise-installed ClickHouse         |
| `mise run validate:clickhouse` | ClickHouse E2E tests                    |

---

## Key Changes in v2.0.0

### Breaking Changes

| v1.x (DuckDB)     | v2.0.0 (ClickHouse)             |
| ----------------- | ------------------------------- |
| `duckdb_path`     | `database` (str)                |
| `duckdb_size_mb`  | `storage_bytes` (int)           |
| `database_exists` | removed                         |
| `base_dir` param  | removed (ClickHouse manages)    |
| 30-column OHLC    | 26-column OHLC (4 cols removed) |

### Removed Files

```
src/exness_data_preprocess/database_manager.py   (209 lines)
src/exness_data_preprocess/gap_detector.py       (134 lines)
src/exness_data_preprocess/ohlc_generator.py     (266 lines)
src/exness_data_preprocess/query_engine.py       (291 lines)
src/exness_data_preprocess/schema.py             (324 lines)
```

**Total: ~1,224 lines deleted**

---

## References

- **Exness Data**: <https://ticks.ex2archive.com/>
- **ClickHouse**: <https://clickhouse.com/>

---

**Last Updated**: 2025-12-11
