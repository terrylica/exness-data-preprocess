# Changelog

All notable changes to exness-data-preprocess will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.5.0] - 2025-10-18

### ⚡ Performance

- **ohlc**: Implement incremental OHLC generation with 7.3x speedup

  Replace full regeneration with incremental updates for new data only.

  Implementation:
  - Add optional `start_date`/`end_date` parameters to `regenerate_ohlc()`
  - Support three modes: full regeneration, incremental append, range update
  - Use `INSERT OR IGNORE` pattern with PRIMARY KEY for duplicate handling
  - Track `earliest_added_month` in processor for incremental triggers

  Performance (measured via spike test):
  - Full regeneration: 8.05s (303K bars, 7 months)
  - Incremental update: 1.10s (43K new bars, 1 month)
  - Speedup: 7.3x (86.3% time reduction)

  Validation:
  - Spike test: 100% row count match, zero duplicates
  - All 48 existing tests pass (backward compatible)

  SSoT: docs/validation/SPIKE_TEST_RESULTS_PHASE1_2025-10-18.md

  BREAKING CHANGE: None (optional parameters maintain existing API)

- **session**: Implement vectorized session detection with 2.2x speedup

  Pre-compute trading minutes for vectorized `.isin()` lookup instead of per-timestamp `.apply()` calls.

  Implementation:
  - Add `_precompute_trading_minutes()` helper in SessionDetector
  - Replace `.apply()` loop with vectorized `.isin()` lookup
  - Preserve accuracy via exchange_calendars.is_open_on_minute()
  - Handle lunch breaks (Tokyo 11:30-12:30, Hong Kong/Singapore 12:00-13:00)

  Performance (measured via spike test):
  - Current approach: 5.99s (302K bars, 10 exchanges)
  - Vectorized approach: 2.69s (302K bars, 10 exchanges)
  - Speedup: 2.2x (55.2% time reduction)
  - Combined Phase 1+2: ~16x total speedup (8.05s → 0.50s)

  Validation:
  - Spike test: 100% accuracy match across all 10 exchanges
  - All 48 existing tests pass (backward compatible)

  SSoT: docs/PHASE2_SESSION_VECTORIZATION_PLAN.yaml (v2.0.0)
  Validation: docs/validation/SPIKE_TEST_RESULTS_PHASE2_2025-10-18.md

  BREAKING CHANGE: None (transparent drop-in replacement)

- **gap**: Implement SQL gap detection with complete coverage

  Replace Python iteration with SQL EXCEPT query to detect ALL gaps (before + within + after), not just edge gaps.

  Implementation:
  - Replace lines 94-155 (62 lines) with SQL EXCEPT query (34 lines)
  - Use DuckDB `generate_series()` + EXCEPT operator
  - Detect internal gaps missed by Python MIN/MAX approach

  Correctness (measured via spike test):
  - Python approach: 41 gaps detected (missed internal gap 2022-03)
  - SQL approach: 42 gaps detected (correctly found 2022-03)
  - Bug fixed: Internal gaps now detected

  Maintainability:
  - LOC reduction: 46% (62 → 34 lines)
  - Complexity: O(n) Python loops → O(1) SQL query

  Validation:
  - Spike test: SQL detects gaps Python iteration misses
  - All 48 existing tests pass (backward compatible)

  SSoT: docs/PHASE3_SQL_GAP_DETECTION_PLAN.yaml (v2.0.0)

  BREAKING CHANGE: None (same method signature, better correctness)

### 📚 Documentation

- Add comprehensive SSoT plans with spike test validation

  Create machine-readable OpenAPI 3.1.0 specifications documenting implementation plans with SLOs and discovered nuances.

  Files Added:
  - docs/PHASE2_SESSION_VECTORIZATION_PLAN.yaml (v1.0.0 → v2.0.0)
  - docs/PHASE3_SQL_GAP_DETECTION_PLAN.yaml (v1.0.0 → v2.0.0)
  - docs/validation/SPIKE_TEST_RESULTS_PHASE1_2025-10-18.md
  - docs/validation/SPIKE_TEST_RESULTS_PHASE2_2025-10-18.md
  - docs/validation/DOCUMENTATION_SURVEY_v1.7.0.md

  SLOs Defined:
  - Availability: API surface backward compatible
  - Correctness: Exact match with existing implementation
  - Observability: Print statements show progress
  - Maintainability: Off-the-shelf libraries, no custom code

  Pattern Established:
  - Spike test first (validate theory before implementation)
  - Iterative SSoT plan updates (v1.0.0 → v2.0.0 with discoveries)
  - Measured results (no theoretical claims without validation)

### ♻️ Refactoring

- **schema**: Centralize OHLC schema in schema.py module - Create schema.py with OHLCSchema class as single source of truth - Reduce coupling from 42 to 5 update locations (88% reduction) - Replace hardcoded column lists in docs with pointers to schema.py - Delete obsolete PYDANTIC_TEST_STRATEGY.md (tests implemented) - Delete add_schema_comments.py (functionality merged into processor) - Update tests to use OHLCSchema.get_required_columns() - Achieve maximum DRY: future column additions require 1-2 file updates BREAKING CHANGE: None (additive refactoring, no API changes)

- Extract 7 specialized modules from processor.py (Phase 1-5) Refactor processor.py using facade pattern with 7 focused modules implementing separation of concerns. Modules Created: - downloader.py: HTTP download operations - tick_loader.py: CSV parsing - database_manager.py: Database operations - session_detector.py: Holiday/session detection - gap_detector.py: Incremental update logic - ohlc_generator.py: Phase7 OHLC generation - query_engine.py: Query operations Design Principles: - Facade pattern: processor.py delegates to specialized modules - SLO-based: All modules define Availability, Correctness, Observability, Maintainability - Off-the-shelf: httpx, pandas, DuckDB, exchange_calendars (no custom implementations) - Zero regressions: All 48 tests pass, all ruff checks pass Documentation: - Updated CLAUDE.md with module structure and facade pattern - Updated docs/README.md with implementation architecture v1.3.0 - Added planning documents (REFACTORING_CHECKLIST.md, PHASE7_v1.6.0_REFACTORING_PROGRESS.md) Version: 1.3.0 (Implementation) Validation: 48 tests pass, ruff checks pass, backward compatible


### ✨ Features

- Implement pydantic v2 models with dual-variant e2e testing - Add Pydantic v2 models (UpdateResult, CoverageInfo) for type-safe API - Update processor to use Pydantic types (PairType, TimeframeType, VariantType) - Remove deprecated api.py module (broken functionality) - Implement comprehensive test suite (48 tests, 100% passing): * test_models.py - Pydantic model validation (13 tests) * test_types.py - Type safety and helpers (15 tests) * test_processor_pydantic.py - Integration tests (6 tests) * test_functional_regression.py - v2.0.0 regression tests (10 tests) - Fix Standard variant downloads (variant="" not "Standard") - Add true end-to-end testing with real Exness downloads - Test data: EURUSD August 2024 (815K Raw_Spread + 877K Standard ticks) - Update documentation and add refactoring status tracking - Coverage: models.py 100%, __init__.py 100%, processor.py 45% BREAKING CHANGE: api.py removed (use ExnessDataProcessor directly)


### 📚 Documentation

- Update all schema references from 9-column to 13-column (v1.2.0) Update outdated "9-column" or "Phase7 9 columns" references to "13-column (v1.2.0)" across all documentation files to reflect the current schema version with normalized spread metrics. Files updated: - GITHUB_PYPI_SETUP.md - Release notes reference - PYDANTIC_REFACTORING_PLAN.md - API documentation and examples (4 locations) - docs/DATABASE_SCHEMA.md - Version history (2 locations) - docs/README.md - Validation results - docs/UNIFIED_DUCKDB_PLAN_v2.md - Table descriptions and return types (2 locations) - tests/README.md - Test descriptions (2 locations) All outdated schema references now consistently reference the Phase7 13-column (v1.2.0) schema with normalized metrics (range_per_spread, range_per_tick, body_per_spread, body_per_tick). CHANGELOG.md and research/archive files intentionally preserved for historical accuracy.


### 🔧 Continuous Integration

- Modernize publish workflow with uv and validation pipeline Update GitHub Actions publish workflow to match gapless-crypto-data standards: Build System: - Replace pip+build with uv for consistency with local development - Add UV_SYSTEM_PYTHON=1 environment variable - Use uv sync --dev for dependency installation Validation Pipeline: - Add file encoding validation (UTF-8/ASCII enforcement) - Add ruff linting and format checking - Add pytest test suite execution before build Security: - Add Sigstore artifact signing for published packages - Maintain PyPI Trusted Publishing (OIDC) authentication Configuration: - Change environment name: release → pypi (semantic clarity) - Change artifact name: dist → python-package-distributions (consistency) - Add verbose output to PyPI publish step Security Note: - Added .token-info.md to .gitignore to prevent accidental token documentation commits - Workflow uses OIDC (no API token needed)


### 🧰 Maintenance

- **release**: Bump version 0.1.0 → 0.2.0 [skip ci]

- **release**: Bump version 0.2.0 → 0.3.0 [skip ci]

- **release**: Bump version 0.3.0 → 0.3.1 [skip ci]


### ✨ Features

- Initial commit with v2.0.0 unified DuckDB architecture - Unified single-file DuckDB storage per instrument (eurusd.duckdb) - Phase7 9-column OHLC schema with dual-variant spreads - Sub-15ms query performance with date range filtering - PRIMARY KEY constraints prevent duplicates - Automatic gap detection for incremental updates - DuckDB self-documentation with COMMENT ON statements - GitHub Actions CI/CD with PyPI Trusted Publishing - Pre-commit hooks (ruff, commitizen, basic checks) - Professional README with shields.io badges


### 🐛 Bug Fixes

- Force add .pre-commit-config.yaml (was incorrectly gitignored)

- Remove .pre-commit-config.yaml from .gitignore Pre-commit config should be version controlled, not ignored.

- **pre-commit**: Enable unsafe fixes for ruff to resolve remaining errors

- **research**: Resolve remaining linting errors in research scripts - Fix bare except clause in 02_volatility_model_simple.py (E722) - Move math.erf imports to top in 03_liquidity_crisis_detection.py (E402) - Move math.erf imports to top in 04_regime_detection_analysis.py (E402)


### 💅 Code Style

- Apply pre-commit formatting fixes - Fix end-of-file newlines in 2 MD files - Apply ruff quote style fixes (200 errors fixed) - Reformat 26 files with ruff-format


### 🔧 CI/CD Improvements

- **ci**: Add pre-commit config and basic tests - Add .pre-commit-config.yaml to repository - Create basic test suite (test_basic.py) for CI - Add GITHUB_PYPI_SETUP.md with complete setup instructions Fixes CI failures: - Pre-commit hook now finds config file - Pytest now finds and runs tests successfully


### 🧰 Maintenance

- Prepare v0.1.0 release
