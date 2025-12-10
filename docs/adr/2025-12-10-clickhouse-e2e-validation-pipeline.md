---
status: accepted
date: 2025-12-10
decision-maker: Terry Li
consulted:
  [
    Explore-Agent-Pagination,
    Explore-Agent-OHLC,
    Plan-Agent-Pagination,
    Plan-Agent-Tests,
  ]
research-method: single-agent
clarification-iterations: 3
perspectives: [ProviderToOtherComponents, BoundaryInterface, OperationalService]
---

# ADR: ClickHouse E2E Validation Pipeline

**Design Spec**: [Implementation Spec](/docs/design/2025-12-10-clickhouse-e2e-validation-pipeline/spec.md)

## Context and Problem Statement

The `exness-data-preprocess` package is being prepared as a **data supplier** for PyPI consumers. ClickHouse serves as the cloud cache backend for tick and OHLC data. However, critical validation gaps exist:

1. **No pagination API** - Multi-year queries risk OOM without LIMIT/OFFSET
2. **No ClickHouse tests** - 6 modules (~800 lines) are untested with real data
3. **No batch/streaming API** - No memory-efficient full history iteration
4. **No E2E validation** - Existing mise pipeline doesn't include ClickHouse

The package already has a comprehensive mise E2E validation pipeline (`validate:imports`, `validate:lint`, `validate:test`, etc.) but ClickHouse operations are not validated.

### Before/After

**Before**: ClickHouse modules exist but are not included in validation pipeline:

```
⏮️ Before: No ClickHouse Validation

        ┌⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯┐
        ⋮     ClickHouse     ⋮
        ⋮     (untested)     ⋮
        └⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯┘
        ╭────────────────────╮
        │  validate (main)   │
        ╰────────────────────╯
          │
          ∨
        ┌────────────────────┐
        │  validate:imports  │
        └────────────────────┘
          │
          ∨
        ┌────────────────────┐
        │   validate:lint    │
        └────────────────────┘
          │
          ∨
        ┌────────────────────┐
        │ validate:typecheck │
        └────────────────────┘
          │
          ∨
        ┌────────────────────┐
        │   validate:test    │
        └────────────────────┘
          │
          ∨
        ┌────────────────────┐
        │   validate:build   │
        └────────────────────┘
          │
          ∨
        ┌────────────────────┐
        │  validate:install  │
        └────────────────────┘
```

<details>
<summary>graph-easy source</summary>

```
graph { label: "⏮️ Before: No ClickHouse Validation"; flow: south; }
[ validate (main) ] { shape: rounded; }
[ validate:imports ]
[ validate:lint ]
[ validate:typecheck ]
[ validate:test ]
[ validate:build ]
[ validate:install ]
[ ClickHouse\n(untested) ] { border: dotted; }

[ validate (main) ] -> [ validate:imports ]
[ validate:imports ] -> [ validate:lint ]
[ validate:lint ] -> [ validate:typecheck ]
[ validate:typecheck ] -> [ validate:test ]
[ validate:test ] -> [ validate:build ]
[ validate:build ] -> [ validate:install ]
```

</details>

**After**: ClickHouse validation integrated into main pipeline:

```
 ⏭️ After: Integrated ClickHouse Validation

           ╭─────────────────────╮
           │   validate (main)   │
           ╰─────────────────────╯
             │
             ∨
           ┌─────────────────────┐
           │  validate:imports   │
           └─────────────────────┘
             │
             ∨
           ┌─────────────────────┐
           │    validate:lint    │
           └─────────────────────┘
             │
             ∨
           ┌─────────────────────┐
           │ validate:typecheck  │
           └─────────────────────┘
             │
             ∨
           ┌─────────────────────┐
           │    validate:test    │
           └─────────────────────┘
             │
             ∨
           ┌─────────────────────┐
           │   validate:build    │
           └─────────────────────┘
             │
             ∨
           ┌─────────────────────┐
           │  validate:install   │
           └─────────────────────┘
             │
             ∨
           ┌─────────────────────┐
           │   validate:mixin    │
           └─────────────────────┘
             │
             ∨
           ┏━━━━━━━━━━━━━━━━━━━━━┓
           ┃ validate:clickhouse ┃
           ┗━━━━━━━━━━━━━━━━━━━━━┛
```

<details>
<summary>graph-easy source</summary>

```
graph { label: "⏭️ After: Integrated ClickHouse Validation"; flow: south; }
[ validate (main) ] { shape: rounded; }
[ validate:imports ]
[ validate:lint ]
[ validate:typecheck ]
[ validate:test ]
[ validate:build ]
[ validate:install ]
[ validate:mixin ]
[ validate:clickhouse ] { border: bold; }

[ validate (main) ] -> [ validate:imports ]
[ validate:imports ] -> [ validate:lint ]
[ validate:lint ] -> [ validate:typecheck ]
[ validate:typecheck ] -> [ validate:test ]
[ validate:test ] -> [ validate:build ]
[ validate:build ] -> [ validate:install ]
[ validate:install ] -> [ validate:mixin ]
[ validate:mixin ] -> [ validate:clickhouse ]
```

</details>

## Research Summary

| Agent Perspective        | Key Finding                                                       | Confidence |
| ------------------------ | ----------------------------------------------------------------- | ---------- |
| Explore-Agent-Pagination | CRITICAL: No LIMIT/OFFSET on query_ticks, only partial on CH      | High       |
| Explore-Agent-OHLC       | OHLC reconstruction is production-ready                           | High       |
| Plan-Agent-Pagination    | Cursor-based pagination more efficient than OFFSET for large data | High       |
| Plan-Agent-Tests         | mise E2E validation pattern already established, extend it        | High       |

## Decision Log

| Decision Area      | Options Evaluated                | Chosen                | Rationale                                     |
| ------------------ | -------------------------------- | --------------------- | --------------------------------------------- |
| Test Framework     | pytest vs mise E2E tasks         | mise E2E tasks        | Extend existing pattern, real data validation |
| Data Strategy      | Mocks vs Real Exness data        | Real Exness data      | User requirement: "no mocks, no fake data"    |
| ClickHouse Install | Docker vs mise-native            | mise-native           | Already installed via mise (v25.11.2.24)      |
| Pagination API     | LIMIT/OFFSET vs Cursor vs Both   | Both + Batch iterator | Different use cases need different approaches |
| Local/Cloud Switch | Config files vs Environment vars | Environment vars      | Already supported in clickhouse_client.py     |

### Trade-offs Accepted

| Trade-off               | Choice        | Accepted Cost                                      |
| ----------------------- | ------------- | -------------------------------------------------- |
| Real data vs Fast tests | Real data     | Slower tests, requires ClickHouse running          |
| mise tasks vs pytest    | mise tasks    | Less pytest coverage, more integration validation  |
| Native vs Docker        | Native (mise) | Requires mise ClickHouse installed on dev machines |

## Decision Drivers

- Package will be published to PyPI as a data supplier
- Consumers need pagination for multi-year tick data queries
- All validation must use real Exness data (user requirement)
- Must easily switch between local and cloud ClickHouse
- Extend existing mise E2E validation pattern (not replace it)

## Considered Options

- **Option A**: Add pytest test files for ClickHouse modules
- **Option B**: Extend mise E2E validation with ClickHouse tasks
- **Option C**: Combined pytest + mise validation <- Selected

## Decision Outcome

Chosen option: **Option B** (Extend mise E2E validation), because:

1. User explicitly requested expanding the existing mise E2E pipeline
2. Real data validation is the primary requirement (pytest mocks not acceptable)
3. mise tasks are already the established pattern in this codebase
4. Keeps all validation in one place (`mise run validate`)

## Synthesis

**Convergent findings**: All agents agreed pagination is critical and real data is required.

**Divergent findings**: Initial design proposed pytest, user requested mise E2E expansion.

**Resolution**: Adopted mise E2E validation pattern per user feedback in 3 clarification iterations.

## Consequences

### Positive

- Unified validation: `mise run validate` covers everything including ClickHouse
- Real data validation catches issues mocks would miss
- Native mise ClickHouse is lighter than Docker
- Pagination API prevents OOM in production

### Negative

- Tests require ClickHouse to be running locally
- Validation takes longer with real data
- Developers need mise ClickHouse installed

## Architecture

The `validate:clickhouse` task orchestrates sub-tasks that validate schema, data operations, pagination, and OHLC generation using real Exness tick data:

```
🏗️ ClickHouse E2E Validation Architecture

     ╔════════════════════════════════╗
  ┌─ ║        Real Exness Data        ║
  │  ╚════════════════════════════════╝
  │    │
  │    │
  │    ∨
  │  ┌────────────────────────────────┐
  │  │    validate:clickhouse-data    │ <┐
  │  └────────────────────────────────┘  │
  │    │                                 │
  │    │                                 │
  │    ∨                                 │
  │  ┌────────────────────────────────┐  │
  │  │ validate:clickhouse-pagination │  │
  │  └────────────────────────────────┘  │
  │    │                                 │
  │    │                                 │
  │    ∨                                 │
  │  ┌────────────────────────────────┐  │
  └> │    validate:clickhouse-ohlc    │  │
     └────────────────────────────────┘  │
     ╭────────────────────────────────╮  │
     │        clickhouse:start        │  │
     ╰────────────────────────────────╯  │
       │                                 │
       │                                 │
       ∨                                 │
     ┌────────────────────────────────┐  │
     │       clickhouse:status        │  │
     └────────────────────────────────┘  │
       │                                 │
       │                                 │
       ∨                                 │
     ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓  │
     ┃      validate:clickhouse       ┃  │
     ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛  │
       │                                 │
       │                                 │
       ∨                                 │
     ┌────────────────────────────────┐  │
     │   validate:clickhouse-schema   │ ─┘
     └────────────────────────────────┘
```

<details>
<summary>graph-easy source</summary>

```
graph { label: "🏗️ ClickHouse E2E Validation Architecture"; flow: south; }
[ clickhouse:start ] { shape: rounded; }
[ clickhouse:status ]
[ validate:clickhouse ] { border: bold; }
[ validate:clickhouse-schema ]
[ validate:clickhouse-data ]
[ validate:clickhouse-pagination ]
[ validate:clickhouse-ohlc ]
[ Real Exness Data ] { border: double; }

[ clickhouse:start ] -> [ clickhouse:status ]
[ clickhouse:status ] -> [ validate:clickhouse ]
[ validate:clickhouse ] -> [ validate:clickhouse-schema ]
[ validate:clickhouse-schema ] -> [ validate:clickhouse-data ]
[ validate:clickhouse-data ] -> [ validate:clickhouse-pagination ]
[ validate:clickhouse-pagination ] -> [ validate:clickhouse-ohlc ]
[ Real Exness Data ] -> [ validate:clickhouse-data ]
[ Real Exness Data ] -> [ validate:clickhouse-ohlc ]
```

</details>

## References

- [Codebase Pruning ADR](/docs/adr/2025-12-09-codebase-pruning.md) - Prior cleanup work
- [ClickHouse Migration ADR](/docs/adr/2025-12-09-exness-clickhouse-migration.md) - ClickHouse backend design
