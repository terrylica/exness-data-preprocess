---
adr: 2025-12-10-clickhouse-e2e-validation-pipeline
source: ~/.claude/plans/lively-splashing-steele.md
implementation-status: completed
phase: phase-2
last-updated: 2025-12-10
---

# ClickHouse E2E Validation Pipeline - Implementation Spec

**ADR**: [ClickHouse E2E Validation Pipeline ADR](/docs/adr/2025-12-10-clickhouse-e2e-validation-pipeline.md)

## Overview

**Goal**: Make `exness-data-preprocess` fully functional as a data supplier with ClickHouse as the cloud cache backend.

**User Requirements**:

- Backend: ClickHouse (local first, then cloud) - must switch easily between both
- Query patterns: Date-range + Full history iteration + On-demand batches
- Validation gaps to address: ALL (pagination, tests, streaming/batch API)
- **Local-first testing**: Fully validate on local ClickHouse before cloud deployment

---

## Executive Summary

| Gap                     | Status      | Priority | Impact                                     |
| ----------------------- | ----------- | -------- | ------------------------------------------ |
| **Pagination**          | ✅ RESOLVED | P0       | Multi-year queries OOM without limits      |
| **ClickHouse Tests**    | ✅ RESOLVED | P1       | 6 modules (~800 lines) untested            |
| **Batch/Streaming API** | ✅ RESOLVED | P1       | No memory-efficient full history iteration |

---

## Implementation Tasks

### Phase 0: Local ClickHouse Server Management

- [x] Add `clickhouse:start` task to `.mise.toml`
- [x] Add `clickhouse:stop` task to `.mise.toml`
- [x] Add `clickhouse:status` task to `.mise.toml`
- [x] Test: `mise run clickhouse:start` starts mise ClickHouse server
- [x] Test: `mise run clickhouse:status` confirms connection
- [x] Test: `mise run clickhouse:stop` stops server cleanly

### Phase 1: Pagination API (P0 - Critical)

#### 1.1 Add CursorResult Model

- [x] Add `CursorResult` Pydantic model to `models.py`:

  ```python
  class CursorResult(BaseModel):
      data: Any  # pd.DataFrame
      next_cursor: str | None
      has_more: bool
      page_size: int
  ```

#### 1.2 Add LIMIT/OFFSET to Query Methods

- [x] Add `limit`, `offset` to `clickhouse_query_engine.py` `query_ticks()`
- [x] Add `limit`, `offset` to `clickhouse_query_engine.py` `query_ohlc()`
- [ ] Mirror in `query_engine.py` (DuckDB) for parity (deferred - out of scope)

#### 1.3 Add Cursor-Based Pagination

- [x] Implement `query_ticks_paginated()` with cursor in `clickhouse_query_engine.py`

#### 1.4 Add Batch Iterator

- [x] Implement `query_ticks_batches()` iterator in `clickhouse_query_engine.py`

### Phase 2: mise E2E Validation Tasks (P1)

- [x] Add `validate:clickhouse-schema` task
- [x] Add `validate:clickhouse-data` task
- [x] Add `validate:clickhouse-pagination` task
- [x] Add `validate:clickhouse-ohlc` task
- [x] Add `validate:clickhouse` orchestrator task
- [x] Update main `validate` task to include `validate:mixin`

---

## Critical Files

| File                                                    | Changes                                                  |
| ------------------------------------------------------- | -------------------------------------------------------- |
| `.mise.toml`                                            | Add server tasks + E2E validation tasks (primary change) |
| `src/exness_data_preprocess/clickhouse_query_engine.py` | Add pagination: limit, offset, cursor, iterator          |
| `src/exness_data_preprocess/query_engine.py`            | DuckDB pagination parity                                 |
| `src/exness_data_preprocess/models.py`                  | Add CursorResult model                                   |
| `src/exness_data_preprocess/processor.py`               | Expose pagination methods (optional facade)              |

---

## Success Criteria

**ALL VALIDATION USES REAL DATA - NO MOCKS**

### Server Management

- [x] `mise run clickhouse:start` starts mise ClickHouse server
- [x] `mise run clickhouse:status` confirms connection via Python client
- [x] `mise run clickhouse:stop` stops server cleanly

### Pagination API

- [x] `query_ticks(limit=N, offset=M)` works with real data
- [x] `query_ohlc(limit=N, offset=M)` works with real data
- [x] `query_ticks_paginated()` returns CursorResult with cursor navigation
- [x] `query_ticks_batches()` iterates large datasets without OOM

### mise E2E Validation Pipeline

- [x] `mise run validate:clickhouse-schema` creates tables on real ClickHouse
- [x] `mise run validate:clickhouse-data` queries real Exness tick data
- [x] `mise run validate:clickhouse-pagination` validates LIMIT/OFFSET/cursor/batch
- [x] `mise run validate:clickhouse-ohlc` generates and queries real OHLC bars
- [x] `mise run validate:clickhouse` runs all above as orchestrator
- [x] `mise run validate` includes `validate:mixin` (ClickHouse opt-in via separate command)

### Local → Cloud Switching

- [x] Same validation tasks work when switching to cloud (env vars only)
- [x] CLICKHOUSE_HOST, CLICKHOUSE_SECURE env vars control backend
