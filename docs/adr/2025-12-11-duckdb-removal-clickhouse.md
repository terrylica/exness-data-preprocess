---
status: accepted
date: 2025-12-11
decision-maker: Terry Li
consulted:
  [
    Explore-Agent-1 (mise-tasks),
    Explore-Agent-2 (pipeline-arch),
    Explore-Agent-3 (clickhouse),
    Plan-Agent-1 (duckdb-removal),
    Plan-Agent-2 (sql-ohlc),
    Plan-Agent-3 (materialized-views),
    Audit-Agent-1 (duckdb-safety),
    Audit-Agent-2 (matview-design),
    Audit-Agent-3 (test-migration),
  ]
research-method: 9-agent-parallel-dctl
clarification-iterations: 3
perspectives: [LifecycleMigration, UpstreamIntegration]
---

# ADR: DuckDB Removal - ClickHouse-Only Backend

**Design Spec**: [Implementation Spec](/docs/design/2025-12-11-duckdb-removal-clickhouse/spec.md)

## Context and Problem Statement

The exness-data-preprocess package currently maintains dual storage backends: DuckDB for local development and ClickHouse for cloud deployment. This creates:

1. **Code duplication**: 5 DuckDB modules (~1,300 LOC) mirror 6 ClickHouse modules
2. **Test fragmentation**: 26/48 tests directly use DuckDB private APIs
3. **Model confusion**: Fields like `duckdb_path` and `duckdb_size_mb` are DuckDB-specific
4. **Maintenance burden**: Every feature requires implementation in both backends

The user mandated: **"100% remove DuckDB - ClickHouse only"**.

### Before/After

```
⏮️ Before: Dual Backend (v1.x)

┌──────────────┐     ┌────────────┐
│ processor.py │     │ ClickHouse │
│              │ ──> │ 6 modules  │
└──────────────┘     └────────────┘
  │
  │
  ∨
┌──────────────┐
│    DuckDB    │
│  5 modules   │
└──────────────┘
```

<details>
<summary>graph-easy source (Before)</summary>

```
graph { label: "⏮️ Before: Dual Backend (v1.x)"; flow: east; }
[processor.py] -> [DuckDB\n5 modules]
[processor.py] -> [ClickHouse\n6 modules]
```

</details>

```
⏭️ After: ClickHouse-Only (v2.0.0)

┌──────────────┐     ┌────────────┐
│ processor.py │     │ ClickHouse │
│              │ ──> │ 6 modules  │
└──────────────┘     └────────────┘
```

<details>
<summary>graph-easy source (After)</summary>

```
graph { label: "⏭️ After: ClickHouse-Only (v2.0.0)"; flow: east; }
[processor.py] -> [ClickHouse\n6 modules]
```

</details>

## Research Summary

| Agent Perspective              | Key Finding                                                                 | Confidence |
| ------------------------------ | --------------------------------------------------------------------------- | ---------- |
| Explore-Agent-1 (mise-tasks)   | 31+ tasks in .mise.toml, 7-task main validate pipeline                      | High       |
| Explore-Agent-2 (pipeline)     | Pandas DataFrame bottleneck, session detection rebuilt every time           | High       |
| Explore-Agent-3 (clickhouse)   | 6 ClickHouse modules already implemented, parameterized views working       | High       |
| Plan-Agent-1 (duckdb-removal)  | Direct replacement possible, 26 tests will break                            | High       |
| Plan-Agent-2 (sql-ohlc)        | Session detection needs DST-aware logic, keep Python hybrid approach        | High       |
| Plan-Agent-3 (matviews)        | Materialized views have 6 critical limitations                              | High       |
| Audit-Agent-1 (duckdb-safety)  | No abstraction layer, ExnessDataProcessor directly instantiates DuckDB      | High       |
| Audit-Agent-2 (matview-design) | **DROP materialized views** - normalized metrics can't aggregate, TZ breaks | High       |
| Audit-Agent-3 (test-migration) | 26 tests in test_functional_regression.py and test_processor_pydantic.py    | High       |

## Decision Log

| Decision Area      | Options Evaluated                            | Chosen                           | Rationale                                            |
| ------------------ | -------------------------------------------- | -------------------------------- | ---------------------------------------------------- |
| Storage Backend    | Keep both, DuckDB-only, ClickHouse-only      | ClickHouse-only                  | User mandate: "100% remove DuckDB"                   |
| Removal Approach   | Abstraction layer, Direct replacement        | Direct replacement               | Faster, cleaner break. Accept 26 broken tests.       |
| Materialized Views | Full matviews (1m,2m,5m), Parameterized only | Drop - parameterized only        | 6 critical limitations. Existing views already work. |
| Session Detection  | Pure SQL, Hybrid Python                      | Hybrid Python                    | DST-aware logic via exchange_calendars library       |
| Model Fields       | Keep names, Rename to ClickHouse-idiomatic   | Rename (database, storage_bytes) | Clean break for v2.0.0                               |
| Normalized Metrics | Keep 4 columns, Remove                       | Remove                           | Can't aggregate correctly. Add back later if needed. |

### Trade-offs Accepted

| Trade-off                      | Choice            | Accepted Cost                                         |
| ------------------------------ | ----------------- | ----------------------------------------------------- |
| Breaking change vs gradual     | Breaking (v2.0.0) | Existing users must update field names                |
| 26 broken tests vs abstraction | Rewrite tests     | Additional work, but cleaner codebase                 |
| Matviews vs parameterized      | Drop matviews     | No pre-computed aggregations, but on-demand is <15ms  |
| 30-column vs 26-column OHLC    | 26 columns        | Lose range*per\*\*, body*per\*\* (can add back later) |

## Decision Drivers

- User mandate: "100% remove DuckDB"
- ClickHouse already has working parameterized views in `clickhouse_query_engine.py`
- Materialized views have 6 critical limitations discovered during audit
- Clean break preferred over backward-compatibility shims

## Considered Options

- **Option A**: Keep dual backends (DuckDB + ClickHouse)
- **Option B**: Add abstraction layer, then deprecate DuckDB
- **Option C**: Direct DuckDB removal with ClickHouse-only backend <- Selected

## Decision Outcome

Chosen option: **Option C - Direct DuckDB removal**, because:

1. User explicitly mandated ClickHouse-only
2. Abstraction layer adds complexity without benefit (DuckDB going away)
3. Breaking change is acceptable for v2.0.0
4. 26 tests breaking is manageable scope

## Synthesis

**Convergent findings**: All agents agreed DuckDB modules can be deleted, ClickHouse modules are feature-complete.

**Divergent findings**:

- Plan-Agent-3 initially proposed materialized views
- Audit-Agent-2 discovered 6 critical limitations making matviews unsuitable

**Resolution**: User decided to drop materialized views entirely, keep existing parameterized views pattern.

## Consequences

### Positive

- Remove ~1,300 LOC of duplicated DuckDB code
- Single storage backend simplifies maintenance
- ClickHouse-idiomatic model fields (database, storage_bytes)
- Cleaner test suite after rewrite

### Negative

- v2.0.0 breaking change requires user migration
- 26 tests need rewriting
- No pre-computed OHLC aggregations (acceptable: <15ms on-demand)
- 4 normalized metric columns removed from schema

## Architecture

<!-- graph-easy source:
graph { label: "🏗️ ClickHouse-Only Architecture (v2.0.0)"; flow: south; }
[ExnessDataProcessor] { shape: rounded; border: bold; }
[ExnessDataProcessor] -> [ClickHouseManager]
[ExnessDataProcessor] -> [ClickHouseGapDetector]
[ExnessDataProcessor] -> [ClickHouseOHLCGenerator]
[ExnessDataProcessor] -> [ClickHouseQueryEngine]
[ClickHouseOHLCGenerator] -> [SessionDetector\n(Python)]
[SessionDetector\n(Python)] -> [exchange_calendars\n(DST-aware)]
-->

```
🏗️ ClickHouse-Only Architecture (v2.0.0)

                              ┌─────────────────────────┐
                              │  ClickHouseQueryEngine  │
                              └─────────────────────────┘
                                ∧
                                │
                                │
┌───────────────────────┐      ━━━━━━━━━━━━━━━━━━━━━━━━━      ┌───────────────────┐
│ ClickHouseGapDetector │ <── ┃   ExnessDataProcessor   ┃ ──> │ ClickHouseManager │
└───────────────────────┘      ━━━━━━━━━━━━━━━━━━━━━━━━━      └───────────────────┘
                                │
                                │
                                ∨
                              ┌─────────────────────────┐
                              │ ClickHouseOHLCGenerator │
                              └─────────────────────────┘
                                │
                                │
                                ∨
                              ┌─────────────────────────┐
                              │     SessionDetector     │
                              │        (Python)         │
                              └─────────────────────────┘
                                │
                                │
                                ∨
                              ┌─────────────────────────┐
                              │   exchange_calendars    │
                              │       (DST-aware)       │
                              └─────────────────────────┘
```

<details>
<summary>graph-easy source (Architecture)</summary>

```
graph { label: "🏗️ ClickHouse-Only Architecture (v2.0.0)"; flow: south; }
[ExnessDataProcessor] { shape: rounded; border: bold; }
[ExnessDataProcessor] -> [ClickHouseManager]
[ExnessDataProcessor] -> [ClickHouseGapDetector]
[ExnessDataProcessor] -> [ClickHouseOHLCGenerator]
[ExnessDataProcessor] -> [ClickHouseQueryEngine]
[ClickHouseOHLCGenerator] -> [SessionDetector\n(Python)]
[SessionDetector\n(Python)] -> [exchange_calendars\n(DST-aware)]
```

</details>

## References

- [ClickHouse Migration ADR](/docs/adr/2025-12-09-exness-clickhouse-migration.md)
- [ClickHouse Pydantic Config ADR](/docs/adr/2025-12-10-clickhouse-pydantic-config.md)
