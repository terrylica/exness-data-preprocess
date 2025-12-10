---
adr: 2025-12-09-codebase-pruning
source: ~/.claude/plans/lively-splashing-steele.md
implementation-status: in_progress
phase: phase-1
last-updated: 2025-12-09
---

# Codebase Pruning Implementation Spec

**ADR**: [Codebase Pruning ADR](/docs/adr/2025-12-09-codebase-pruning.md)

## Overview

Full pruning of exness-data-preprocess codebase:

- 80+ MB dependency reduction
- 18 files archived
- 400+ lines of code removed

## Implementation Tasks

### Phase A: Dependency Cleanup ✅

**File**: `pyproject.toml`

- [x] Remove `httpx>=0.25.0` from dependencies
- [x] Remove `pyarrow>=16.0.0` from dependencies
- [x] Remove `polars>=1.34.0` from dependency-groups
- [x] Move `tqdm>=4.65.0` to `[project.optional-dependencies] examples`
- [x] Consolidate dev dependencies (remove conflicting `[project.optional-dependencies] dev`)
- [x] Verify: `uv sync` succeeds
- [x] Verify: `pytest tests/` passes (48/48)

### Phase B: Documentation Cleanup ✅

**Files**: `.gitignore`, `docs/archive/`, `docs/README.md`

- [x] Add to `.gitignore`: `node_modules/`, `.lychee*`, `.lycheecache`, `.token-info.md`
- [x] Create `docs/archive/` directory if not exists
- [x] Move 17 planning docs from `docs/plans/` to `docs/archive/`
- [x] Move 2 research docs from `docs/research/` to `docs/archive/`
- [x] Move `docs/phases/PHASE4_DRY_RUN_CONFIG_PLAN.yaml` to `docs/archive/`
- [x] Update `docs/README.md` to reflect archival

### Phase C: Code Cleanup ✅

**Files**: `clickhouse_base.py` (NEW), `clickhouse_*.py` (4), `api.py` (DELETE), `cli.py` (DELETE)

- [x] Create `src/exness_data_preprocess/clickhouse_base.py` with `ClickHouseClientMixin`
- [x] Refactor `clickhouse_manager.py` to use mixin
- [x] Refactor `clickhouse_gap_detector.py` to use mixin
- [x] Refactor `clickhouse_query_engine.py` to use mixin
- [x] Refactor `clickhouse_ohlc_generator.py` to use mixin
- [x] Delete `src/exness_data_preprocess/api.py` (304 lines)
- [x] Delete `src/exness_data_preprocess/cli.py` (252 lines, dependent on api.py)
- [x] Remove CLI entry point from `pyproject.toml`
- [x] Verify: `pytest tests/` passes (48/48)

## Success Criteria

| Metric                   | Before  | After   | Target          |
| ------------------------ | ------- | ------- | --------------- |
| Dependencies (install)   | ~200 MB | ~120 MB | 40% reduction   |
| docs/plans/ files        | 17      | 2       | 15 archived     |
| api.py lines             | 304     | 0       | Deleted         |
| Duplicate lifecycle code | 60      | 15      | ~45 lines saved |
| Test count               | 48      | 48      | No regression   |

## Files to Modify

| File                                            | Action                                    |
| ----------------------------------------------- | ----------------------------------------- |
| `pyproject.toml`                                | Remove 3 deps, move tqdm, consolidate dev |
| `.gitignore`                                    | Add node_modules, lychee patterns         |
| `src/exness_data_preprocess/api.py`             | **DELETE**                                |
| `src/exness_data_preprocess/__init__.py`        | Remove api.py exports                     |
| `src/exness_data_preprocess/clickhouse_base.py` | **CREATE** mixin                          |
| `src/exness_data_preprocess/clickhouse_*.py`    | Refactor to use mixin                     |
| `docs/plans/*.md` (15 files)                    | Move to archive                           |
| `docs/research/GAP_*.md` (2 files)              | Move to archive                           |
| `docs/README.md`                                | Update after archival                     |

## Risk Assessment

| Item           | Risk   | Mitigation                              |
| -------------- | ------ | --------------------------------------- |
| Remove httpx   | None   | Zero imports confirmed                  |
| Remove pyarrow | Low    | Research scripts need manual install    |
| Remove polars  | None   | Zero imports confirmed                  |
| Archive docs   | Low    | git mv preserves history                |
| Remove api.py  | Medium | User approved; document breaking change |
| Mixin refactor | Low    | Tests verify no regression              |
