# Documentation

Start with the project [README](/README.md) (install, API, schema summary). The schema DDL in [`clickhouse_manager.py`](/src/exness_data_preprocess/clickhouse_manager.py) is authoritative; tasks are in [`moon.yml`](/moon.yml).

## Guides

| Document                                                   | Covers                                                        |
| ---------------------------------------------------------- | ------------------------------------------------------------- |
| [CLICKHOUSE_USER_GUIDE.md](/docs/CLICKHOUSE_USER_GUIDE.md) | Connecting, querying, pagination, resampling, troubleshooting |
| [EXNESS_DATA_SOURCES.md](/docs/EXNESS_DATA_SOURCES.md)     | ticks.ex2archive.com layout, Raw_Spread vs Standard variants  |

## Decisions

Architecture Decision Records in [`adr/`](/docs/adr/), each with an implementation spec in [`design/`](/docs/design/) under the same date-slug. They are historical records: they describe the repository as it was when written and are not edited afterwards.

| ADR                                                                                                         | Decision                                   |
| ----------------------------------------------------------------------------------------------------------- | ------------------------------------------ |
| [2025-12-09 exness-clickhouse-migration](/docs/adr/2025-12-09-exness-clickhouse-migration.md)               | Move storage from DuckDB to ClickHouse     |
| [2025-12-09 codebase-pruning](/docs/adr/2025-12-09-codebase-pruning.md)                                     | Dependency, documentation and code pruning |
| [2025-12-10 clickhouse-e2e-validation-pipeline](/docs/adr/2025-12-10-clickhouse-e2e-validation-pipeline.md) | Pagination API and E2E validation          |
| [2025-12-10 clickhouse-pydantic-config](/docs/adr/2025-12-10-clickhouse-pydantic-config.md)                 | Pydantic connection config, DBeaver output |
| [2025-12-11 duckdb-removal-clickhouse](/docs/adr/2025-12-11-duckdb-removal-clickhouse.md)                   | ClickHouse-only backend (the 2.x line)     |

## Research

Completed studies with their scripts. Several predate the ClickHouse backend and were run on DuckDB; their findings are about the data, not the storage.

- [eurusd-spread-analysis/](/docs/research/eurusd-spread-analysis/README.md): Raw_Spread vs Standard spread variance
- [eurusd-zero-spread-deviations/](/docs/research/eurusd-zero-spread-deviations/README.md): zero-spread deviation multi-period study
- [compression-benchmarks/](/docs/research/compression-benchmarks/README.md): tick storage compression comparison
- [HYBRID_SESSION_DETECTION_ANALYSIS.md](/docs/research/HYBRID_SESSION_DETECTION_ANALYSIS.md): session and holiday detection approach
