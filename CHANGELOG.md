# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial release of exness-data-preprocess
- Core `ExnessDataProcessor` class for tick data preprocessing
- Simple Python API with wrapper functions
- Command-line interface with `process`, `query`, `analyze`, and `stats` commands
- Parquet compression with Zstd-22 (9% smaller than ZIP, lossless)
- DuckDB OHLC generation with embedded metadata
- Automatic resampling to higher timeframes (5m, 15m, 30m, 1h, 4h, 1d)
- On-demand tick data analysis capabilities
- Atomic file operations for data integrity
- Comprehensive test suite with >90% coverage
- Full documentation with usage examples and benchmarks

### Technical Details
- Optimal compression: Parquet + Zstd-22 (4.77 MB per month EURUSD)
- DuckDB storage: 0.78 MB per month OHLC data
- Zero precision loss (lossless compression)
- Direct queryability via DuckDB SQL
- Support for Python 3.9+

## [0.1.0] - 2025-10-12

Initial PyPI release.

[Unreleased]: https://github.com/terrylica/exness-data-preprocess/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/terrylica/exness-data-preprocess/releases/tag/v0.1.0
