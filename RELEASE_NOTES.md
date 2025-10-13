# Changelog

All notable changes to exness-data-preprocess will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).


### ✨ Features

- Implement pydantic v2 models with dual-variant e2e testing - Add Pydantic v2 models (UpdateResult, CoverageInfo) for type-safe API - Update processor to use Pydantic types (PairType, TimeframeType, VariantType) - Remove deprecated api.py module (broken functionality) - Implement comprehensive test suite (48 tests, 100% passing): * test_models.py - Pydantic model validation (13 tests) * test_types.py - Type safety and helpers (15 tests) * test_processor_pydantic.py - Integration tests (6 tests) * test_functional_regression.py - v2.0.0 regression tests (10 tests) - Fix Standard variant downloads (variant="" not "Standard") - Add true end-to-end testing with real Exness downloads - Test data: EURUSD August 2024 (815K Raw_Spread + 877K Standard ticks) - Update documentation and add refactoring status tracking - Coverage: models.py 100%, __init__.py 100%, processor.py 45% BREAKING CHANGE: api.py removed (use ExnessDataProcessor directly)


### 🔧 Continuous Integration

- Modernize publish workflow with uv and validation pipeline Update GitHub Actions publish workflow to match gapless-crypto-data standards: Build System: - Replace pip+build with uv for consistency with local development - Add UV_SYSTEM_PYTHON=1 environment variable - Use uv sync --dev for dependency installation Validation Pipeline: - Add file encoding validation (UTF-8/ASCII enforcement) - Add ruff linting and format checking - Add pytest test suite execution before build Security: - Add Sigstore artifact signing for published packages - Maintain PyPI Trusted Publishing (OIDC) authentication Configuration: - Change environment name: release → pypi (semantic clarity) - Change artifact name: dist → python-package-distributions (consistency) - Add verbose output to PyPI publish step Security Note: - Added .token-info.md to .gitignore to prevent accidental token documentation commits - Workflow uses OIDC (no API token needed)


### 🧰 Maintenance

- **release**: Bump version 0.1.0 → 0.2.0 [skip ci]

