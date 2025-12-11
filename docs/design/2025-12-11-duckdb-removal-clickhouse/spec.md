---
adr: 2025-12-11-duckdb-removal-clickhouse
source: ~/.claude/plans/lively-splashing-steele.md
implementation-status: in_progress
phase: phase-1
last-updated: 2025-12-11
---

# ClickHouse-Only Data Pipeline (DuckDB Removal)

**ADR**: [DuckDB Removal - ClickHouse-Only Backend](/docs/adr/2025-12-11-duckdb-removal-clickhouse.md)

**Goal**: Remove DuckDB entirely, make ClickHouse the sole storage backend, integrate ClickHouse E2E into main `mise run validate` pipeline.

**Architecture**: Hybrid - ClickHouse for storage/OHLC, Python `session_detector.py` for DST-aware session detection.

**Breaking Change**: v2.0.0 release (direct replacement, no abstraction layer)

---

## Revised Decisions (Post-Audit)

| Decision               | Choice                         | Rationale                                                                                          |
| ---------------------- | ------------------------------ | -------------------------------------------------------------------------------------------------- |
| **Materialized Views** | DROPPED                        | 6 critical limitations. Existing parameterized views in `clickhouse_query_engine.py` already work. |
| **DuckDB Removal**     | Direct replacement             | Accept 26 broken tests. Rewrite tests for ClickHouse.                                              |
| **Model Fields**       | Rename to ClickHouse-idiomatic | `duckdb_path` -> `database`, `duckdb_size_mb` -> `storage_bytes`                                   |
| **Normalized Metrics** | Remove for now                 | Can add back later when needed. Focus on data integration.                                         |

---

## Summary of Changes

| Category     | Action                               | Files                                                                               |
| ------------ | ------------------------------------ | ----------------------------------------------------------------------------------- |
| **Delete**   | 5 DuckDB modules (~1,300 LOC)        | database_manager.py, gap_detector.py, ohlc_generator.py, query_engine.py, schema.py |
| **Refactor** | processor.py to ClickHouse-only      | processor.py                                                                        |
| **Rename**   | Model fields to ClickHouse-idiomatic | models.py                                                                           |
| **Rewrite**  | 26 broken tests                      | 5 test files                                                                        |
| **Update**   | Validation pipeline                  | .mise.toml                                                                          |

---

## Implementation Tasks

### Task 1: Delete DuckDB Modules

**Status**: [ ] Not Started

Delete these files:

```
src/exness_data_preprocess/database_manager.py   (209 lines)
src/exness_data_preprocess/gap_detector.py       (134 lines)
src/exness_data_preprocess/ohlc_generator.py     (266 lines)
src/exness_data_preprocess/query_engine.py       (291 lines)
src/exness_data_preprocess/schema.py             (324 lines)
```

**Total: ~1,224 lines deleted**

---

### Task 2: Refactor processor.py

**Status**: [ ] Not Started

#### 2.1 Remove DuckDB Imports

```python
# DELETE these imports
import duckdb
from exness_data_preprocess.database_manager import DatabaseManager
from exness_data_preprocess.gap_detector import GapDetector
from exness_data_preprocess.ohlc_generator import OHLCGenerator
from exness_data_preprocess.query_engine import QueryEngine

# ADD these imports
from exness_data_preprocess.clickhouse_client import get_client
from exness_data_preprocess.clickhouse_manager import ClickHouseManager
from exness_data_preprocess.clickhouse_gap_detector import ClickHouseGapDetector
from exness_data_preprocess.clickhouse_ohlc_generator import ClickHouseOHLCGenerator
from exness_data_preprocess.clickhouse_query_engine import ClickHouseQueryEngine
```

#### 2.2 Refactor `__init__`

```python
def __init__(self, config: Optional[ConfigModel] = None):
    # Temp dir for downloads only
    self.temp_dir = Path.home() / "eon" / "exness-data" / "temp"
    self.temp_dir.mkdir(parents=True, exist_ok=True)

    # ClickHouse modules
    self._ch_client = get_client()
    self.ch_manager = ClickHouseManager(self._ch_client)
    self.ch_gap_detector = ClickHouseGapDetector(self._ch_client)
    self.session_detector = SessionDetector()
    self.ch_ohlc_generator = ClickHouseOHLCGenerator(self.session_detector, self._ch_client)
    self.ch_query_engine = ClickHouseQueryEngine(self._ch_client)

    # Ensure schema
    self.ch_manager.ensure_schema()

    # Downloader
    self.downloader = ExnessDownloader(self.temp_dir)
```

#### 2.3 Method Delegation

| Method                | Delegate To                                                            |
| --------------------- | ---------------------------------------------------------------------- |
| `update_data()`       | Use `ch_manager.insert_ticks()`, `ch_ohlc_generator.regenerate_ohlc()` |
| `query_ticks()`       | `ch_query_engine.query_ticks()`                                        |
| `query_ohlc()`        | `ch_query_engine.query_ohlc()`                                         |
| `get_data_coverage()` | `ch_query_engine.get_data_coverage()`                                  |

#### 2.4 Remove Private Methods

Delete these DuckDB-specific private methods:

- `_get_or_create_db()`
- `_append_ticks_to_db()`
- `_regenerate_ohlc()` (replaced by delegation)

---

### Task 3: Rename Model Fields (ClickHouse-Idiomatic)

**Status**: [ ] Not Started

#### models.py Changes

```python
class UpdateResult(BaseModel):
    """Result of update_data() operation."""

    # RENAMED: ClickHouse-idiomatic names
    database: str = Field(
        description="ClickHouse database name (e.g., 'exness')"
    )
    storage_bytes: int = Field(
        default=0,
        ge=0,
        description="Total storage in bytes (from system.tables)"
    )

    # Keep other fields unchanged
    instrument: str
    variant: str
    months_processed: int
    rows_added: int
    ohlc_bars: int
    # ... etc


class CoverageInfo(BaseModel):
    """Data coverage information."""

    # RENAMED: ClickHouse-idiomatic names
    database: str = Field(
        description="ClickHouse database name"
    )
    storage_bytes: int = Field(
        default=0,
        ge=0,
        description="Total storage in bytes"
    )

    # Keep other fields
    instrument: str
    earliest_date: Optional[datetime]
    latest_date: Optional[datetime]
    # ... etc
```

#### Breaking Change Documentation

```python
# Add to models.py docstring
"""
BREAKING CHANGES (v2.0.0):
- Renamed: duckdb_path -> database (str, not Path)
- Renamed: duckdb_size_mb -> storage_bytes (int, bytes not MB)
- Removed: All DuckDB file path references
- Backend: ClickHouse is now the only supported backend
"""
```

---

### Task 4: Simplify OHLC Schema (Remove Normalized Metrics)

**Status**: [ ] Not Started

#### Remove These Columns from ohlc_1m

```sql
-- REMOVE these 4 columns (cause aggregation issues)
range_per_spread Nullable(Float32)
range_per_tick Nullable(Float32)
body_per_spread Nullable(Float32)
body_per_tick Nullable(Float32)
```

#### Updated Schema (26 columns instead of 30)

Keep:

- Core OHLC: instrument, timestamp, open, high, low, close (6)
- Spreads: raw_spread_avg, standard_spread_avg (2)
- Tick counts: tick_count_raw_spread, tick_count_standard (2)
- Timezone: ny_hour, london_hour, ny_session, london_session (4)
- Holidays: is_us_holiday, is_uk_holiday, is_major_holiday (3)
- Sessions: 10 exchange session flags (10)

**Total: 26 columns** (down from 30)

---

### Task 5: Update Validation Pipeline

**Status**: [ ] Not Started

#### .mise.toml Changes

```toml
[tasks.validate]
description = "Run full E2E validation pipeline"
depends = [
    "clickhouse:ensure",        # Fail fast if ClickHouse not running
    "validate:imports",
    "validate:lint",
    "validate:typecheck",
    "validate:test",
    "validate:build",
    "validate:install",
    "validate:mixin",
    "validate:clickhouse",      # ClickHouse E2E validation
]

[tasks."clickhouse:ensure"]
description = "Ensure ClickHouse is running"
run = '''
#!/usr/bin/env bash
set -e
if ! nc -z localhost 8123 2>/dev/null; then
    echo "ERROR: ClickHouse not running on port 8123" >&2
    echo "Start with: mise run clickhouse:start" >&2
    exit 1
fi
echo "ClickHouse connection verified"
'''
```

---

### Task 6: Rewrite Tests

**Status**: [ ] Not Started

#### Tests That Will Break (26 tests)

| File                            | Tests | Issue                                       |
| ------------------------------- | ----- | ------------------------------------------- |
| `test_functional_regression.py` | 21    | Uses `_get_or_create_db()`, `import duckdb` |
| `test_processor_pydantic.py`    | 5     | Uses DuckDB fixtures, `duckdb_path` field   |

#### Test Migration Strategy

1. **Remove DuckDB imports**: Delete `import duckdb` from test files
2. **Update fixtures**: Replace `processor_with_real_data` to use ClickHouse
3. **Update assertions**: Change `duckdb_path` to `database`, `duckdb_size_mb` to `storage_bytes`
4. **Skip if no ClickHouse**: Add `@pytest.mark.skipif` for environments without ClickHouse

#### New conftest.py Fixtures

```python
@pytest.fixture
def clickhouse_client():
    """ClickHouse client fixture."""
    try:
        client = get_client()
        yield client
        client.close()
    except ClickHouseConnectionError:
        pytest.skip("ClickHouse not available")

@pytest.fixture
def processor_with_clickhouse(temp_dir, clickhouse_client):
    """Processor with ClickHouse backend."""
    processor = ExnessDataProcessor()
    yield processor
    processor.close()
```

---

### Task 7: Update **init**.py exports

**Status**: [ ] Not Started

Remove DuckDB module exports, keep only ClickHouse exports.

---

### Task 8: Remove duckdb from pyproject.toml

**Status**: [ ] Not Started

Remove `duckdb>=0.9.0` from dependencies list.

---

### Task 9: Update Documentation

**Status**: [ ] Not Started

| File                          | Changes                                       |
| ----------------------------- | --------------------------------------------- |
| `README.md`                   | ClickHouse required, new field names          |
| `CLAUDE.md`                   | Update architecture, remove DuckDB references |
| `docs/MODULE_ARCHITECTURE.md` | Remove DuckDB modules                         |
| `docs/DATABASE_SCHEMA.md`     | Update to 26-column schema                    |

---

## Execution Order

```
1. Delete 5 DuckDB modules
   |
   v
2. Refactor processor.py (ClickHouse-only)
   |
   v
3. Rename model fields (database, storage_bytes)
   |
   v
4. Simplify OHLC schema (remove 4 normalized metric columns)
   |
   v
5. Update .mise.toml (clickhouse:ensure in validate)
   |
   v
6. Rewrite 26 broken tests
   |
   v
7. Update __init__.py exports
   |
   v
8. Remove duckdb from pyproject.toml dependencies
   |
   v
9. Update documentation
   |
   v
10. Run mise run validate (expect all pass)
   |
   v
11. Semantic release (v2.0.0 - breaking change)
```

---

## Critical Files

| File                                               | Action                       | Priority |
| -------------------------------------------------- | ---------------------------- | -------- |
| `src/exness_data_preprocess/processor.py`          | Major refactor               | P0       |
| `src/exness_data_preprocess/models.py`             | Rename fields                | P0       |
| `src/exness_data_preprocess/clickhouse_manager.py` | Remove 4 columns from schema | P1       |
| `.mise.toml`                                       | Add clickhouse:ensure        | P1       |
| `tests/test_functional_regression.py`              | Rewrite for ClickHouse       | P2       |
| `tests/conftest.py`                                | ClickHouse fixtures          | P2       |
| `pyproject.toml`                                   | Remove duckdb dependency     | P2       |

---

## Validation Checklist

- [ ] `mise run clickhouse:start` starts server
- [ ] `mise run validate` passes (includes ClickHouse E2E)
- [ ] All tests pass with ClickHouse backend
- [ ] No DuckDB imports remain (`grep -r "import duckdb" src/`)
- [ ] No `duckdb_path` references remain
- [ ] `duckdb` removed from pyproject.toml
- [ ] Documentation updated

---

## What We're NOT Doing (Deferred)

| Feature                                    | Status  | Reason                                                                |
| ------------------------------------------ | ------- | --------------------------------------------------------------------- |
| Materialized views (ohlc_2m, ohlc_5m)      | Dropped | 6 critical limitations. Existing parameterized views work.            |
| Normalized metrics (range*per*, body*per*) | Removed | Cause aggregation issues. Can add back later.                         |
| Backend abstraction layer                  | Skipped | Direct replacement is faster. DuckDB removal is absolute requirement. |
| Backward-compatible field names            | Skipped | Clean break to ClickHouse-idiomatic names.                            |
