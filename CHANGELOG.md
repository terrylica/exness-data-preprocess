# Changelog

All notable changes to exness-data-preprocess will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).


### ♻️ Refactoring

- **schema**: Centralize OHLC schema in schema.py module - Create schema.py with OHLCSchema class as single source of truth - Reduce coupling from 42 to 5 update locations (88% reduction) - Replace hardcoded column lists in docs with pointers to schema.py - Delete obsolete PYDANTIC_TEST_STRATEGY.md (tests implemented) - Delete add_schema_comments.py (functionality merged into processor) - Update tests to use OHLCSchema.get_required_columns() - Achieve maximum DRY: future column additions require 1-2 file updates BREAKING CHANGE: None (additive refactoring, no API changes)


### ✨ Features

- Implement pydantic v2 models with dual-variant e2e testing - Add Pydantic v2 models (UpdateResult, CoverageInfo) for type-safe API - Update processor to use Pydantic types (PairType, TimeframeType, VariantType) - Remove deprecated api.py module (broken functionality) - Implement comprehensive test suite (48 tests, 100% passing): * test_models.py - Pydantic model validation (13 tests) * test_types.py - Type safety and helpers (15 tests) * test_processor_pydantic.py - Integration tests (6 tests) * test_functional_regression.py - v2.0.0 regression tests (10 tests) - Fix Standard variant downloads (variant="" not "Standard") - Add true end-to-end testing with real Exness downloads - Test data: EURUSD August 2024 (815K Raw_Spread + 877K Standard ticks) - Update documentation and add refactoring status tracking - Coverage: models.py 100%, __init__.py 100%, processor.py 45% BREAKING CHANGE: api.py removed (use ExnessDataProcessor directly)


### 🔧 Continuous Integration

- Modernize publish workflow with uv and validation pipeline Update GitHub Actions publish workflow to match gapless-crypto-data standards: Build System: - Replace pip+build with uv for consistency with local development - Add UV_SYSTEM_PYTHON=1 environment variable - Use uv sync --dev for dependency installation Validation Pipeline: - Add file encoding validation (UTF-8/ASCII enforcement) - Add ruff linting and format checking - Add pytest test suite execution before build Security: - Add Sigstore artifact signing for published packages - Maintain PyPI Trusted Publishing (OIDC) authentication Configuration: - Change environment name: release → pypi (semantic clarity) - Change artifact name: dist → python-package-distributions (consistency) - Add verbose output to PyPI publish step Security Note: - Added .token-info.md to .gitignore to prevent accidental token documentation commits - Workflow uses OIDC (no API token needed)


### 🧰 Maintenance

- **release**: Bump version 0.1.0 → 0.2.0 [skip ci]

- **release**: Bump version 0.2.0 → 0.3.0 [skip ci]


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

