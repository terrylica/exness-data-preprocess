---
status: accepted
date: 2025-12-09
decision-maker: Terry Li
consulted:
  [
    ZSTD-vs-LZ4-Codec-Agent,
    Delta-Gorilla-Corruption-Agent,
    Dictionary-vs-JOIN-Agent,
    AI-Schema-Documentation-Agent,
    ClickHouse-Architect-Skill-Agent,
  ]
research-method: 9-agent-parallel-dctl
clarification-iterations: 4
perspectives:
  [Performance, Simplicity, AICodeGeneration, DataModeling, FutureScalability]
---

# ADR: Exness Data Preprocess DuckDB to ClickHouse Migration

**Design Spec**: [Implementation Spec](/docs/design/2025-12-09-exness-clickhouse-migration/spec.md)

## Context and Problem Statement

The exness-data-preprocess project currently uses embedded DuckDB for storing forex tick data and OHLC bars. While DuckDB works well for single-file analytics, the project needs to migrate to ClickHouse to:

1. **Unify infrastructure** with other ClickHouse-based projects (deribit data, MLflow tracking)
2. **Support future scale** (100+ instruments, multi-terabyte datasets)
3. **Enable real-time dashboards** with sub-second query latency
4. **Leverage ClickHouse-native features** (ReplacingMergeTree, parameterized views, compression codecs)

The migration must preserve all existing functionality while adopting ClickHouse-native patterns validated through independent research.

### Before/After

```
   ┌────────────┐            ┌────────────┐
   │   DuckDB   │  migrate   │ ClickHouse │
   │ (embedded) │ ─────────> │  (local)   │
   └────────────┘            └────────────┘
```

<details>
<summary>graph-easy source</summary>

```
graph { flow: east; }
[duckdb] { label: "DuckDB\n(embedded)"; }
[clickhouse] { label: "ClickHouse\n(local)"; }
[duckdb] -- migrate --> [clickhouse]
```

</details>

## Research Summary

Five independent research agents validated the ClickHouse Architect skill's recommendations:

| Agent Perspective          | Key Finding                                                                       | Confidence |
| -------------------------- | --------------------------------------------------------------------------------- | ---------- |
| ZSTD-vs-LZ4-Codec          | DoubleDelta + LZ4 is 1.76x faster for timestamps; ZSTD provides no benefit        | High       |
| Delta-Gorilla-Corruption   | Bug fixed in v23.2 (PR #45615); combination is redundant, not dangerous           | High       |
| Dictionary-vs-JOIN         | Dictionaries only benefit >364 rows; standard tables + JOINs better for <100 rows | High       |
| AI-Schema-Documentation    | COMMENT statements provide 20-27% AI accuracy improvement (AtScale 2025 study)    | High       |
| ClickHouse-Architect-Skill | Skill already updated with PR #45615 fix documentation                            | Medium     |

## Decision Log

| Decision Area        | Options Evaluated             | Chosen              | Rationale                                                                       |
| -------------------- | ----------------------------- | ------------------- | ------------------------------------------------------------------------------- |
| Timestamp codec      | ZSTD, LZ4                     | LZ4                 | 1.76x faster decompression; ZSTD provides no additional benefit for DoubleDelta |
| Lookup tables        | Dictionaries, Standard tables | Standard tables     | <364 rows threshold; v24.4 optimizer handles small JOINs efficiently            |
| Float codec          | LZ4, ZSTD                     | ZSTD                | ZSTD(1) optimal for Gorilla-encoded floats                                      |
| Schema documentation | None, Comments                | COMMENT statements  | 20-27% AI accuracy improvement                                                  |
| Data access pattern  | Repository, Views             | Parameterized Views | ClickHouse-native OLAP pattern                                                  |

### Trade-offs Accepted

| Trade-off                   | Choice                            | Accepted Cost                                               |
| --------------------------- | --------------------------------- | ----------------------------------------------------------- |
| Simplicity vs Complexity    | Standard tables over Dictionaries | Marginally slower JOINs (unmeasurable for 10-20 rows)       |
| LZ4 vs ZSTD for timestamps  | LZ4                               | Slightly worse compression ratio (unnoticeable in practice) |
| Full rewrite vs incremental | Full rewrite in 3 batches         | Higher initial effort, cleaner final architecture           |

## Decision Drivers

- **Research validation**: All recommendations independently verified before adoption
- **ClickHouse v25.11.2 compatibility**: Ensure patterns work with installed version
- **AI code generation**: Schema must be understandable by AI coding agents
- **Operational simplicity**: Standard SQL patterns over specialized ClickHouse features where equivalent
- **Future scalability**: Design for 100+ instruments even if starting with 2

## Considered Options

- **Option A**: Direct port (keep DuckDB patterns, just change connection)
- **Option B**: ClickHouse Architect skill recommendations (Dictionaries, ZSTD everywhere)
- **Option C**: Research-validated hybrid (standard tables, LZ4 for timestamps, ZSTD for floats) <- Selected

## Decision Outcome

Chosen option: **Option C (Research-validated hybrid)**, because independent agent research proved that:

1. **Dictionaries are overkill** for <364 row lookup tables
2. **DoubleDelta + LZ4** outperforms DoubleDelta + ZSTD by 1.76x
3. **COMMENT statements** provide measurable AI accuracy improvements
4. The Delta+Gorilla corruption warning is **outdated** (fixed 3 years ago)

## Synthesis

**Convergent findings**: All agents agreed on:

- ReplacingMergeTree for deduplication
- LowCardinality(String) for instrument column
- PARTITION BY toYYYYMM() for monthly partitions
- Never use FINAL (100x slower)

**Divergent findings**: ClickHouse Architect skill vs independent research:

- Skill recommended Dictionaries; research showed they're overkill for small tables
- Skill recommended ZSTD everywhere; research showed LZ4 better for DoubleDelta
- Skill had outdated corruption warning; research confirmed it's fixed in v23.2+

**Resolution**: User selected research-validated recommendations over skill defaults where they diverged.

## Consequences

### Positive

- Unified infrastructure with other ClickHouse projects
- 70% storage reduction with LowCardinality instrument column
- 15-50x compression with optimized codec selection
- AI-friendly schema with comprehensive COMMENT statements
- Simpler architecture without unnecessary Dictionaries

### Negative

- Full rewrite required (7 modules)
- Testing overhead (validate each batch)
- Documentation updates needed
- Temporary loss of backward compatibility during migration

## Architecture

```
                                                 ┌──────────────────────────────┐
                                                 │       Application Code       │
                                                 └──────────────────────────────┘
                                                   │
                                                   │
                                                   ∨
┌──────────────────────────────────────┐         ┌──────────────────────────────┐         ┌────────────────────────────────────┐
│ raw_spread_ticks(ReplacingMergeTree) │ <────── │     Parameterized Views      │ ──────> │ standard_ticks(ReplacingMergeTree) │
└──────────────────────────────────────┘         └──────────────────────────────┘         └────────────────────────────────────┘
                                                   │
                                                   │
                                                   ∨
┌──────────────────────────────────────┐  JOIN   ┌──────────────────────────────┐
│         holidays(MergeTree)          │ <────── │ ohlc_1m(ReplacingMergeTree)  │
└──────────────────────────────────────┘         └──────────────────────────────┘
                                                   │
                                                   │ JOIN
                                                   ∨
                                                 ┌──────────────────────────────┐
                                                 │ exchange_sessions(MergeTree) │
                                                 └──────────────────────────────┘
```

<details>
<summary>graph-easy source</summary>

```
graph { flow: south; }
[ Application Code ]
[ Parameterized Views ]
[ raw_spread_ticks ] { label: "raw_spread_ticks(ReplacingMergeTree)"; }
[ standard_ticks ] { label: "standard_ticks(ReplacingMergeTree)"; }
[ ohlc_1m ] { label: "ohlc_1m(ReplacingMergeTree)"; }
[ exchange_sessions ] { label: "exchange_sessions(MergeTree)"; }
[ holidays ] { label: "holidays(MergeTree)"; }

[ Application Code ] -> [ Parameterized Views ]
[ Parameterized Views ] -> [ raw_spread_ticks ]
[ Parameterized Views ] -> [ standard_ticks ]
[ Parameterized Views ] -> [ ohlc_1m ]
[ ohlc_1m ] -- JOIN --> [ exchange_sessions ]
[ ohlc_1m ] -- JOIN --> [ holidays ]
```

</details>

## References

- [Migration Plan](/docs/design/2025-12-09-exness-clickhouse-migration/spec.md)
- ClickHouse Architect Skill (cc-skills plugin)
- [PR #45615: Delta+Gorilla fix](https://github.com/ClickHouse/ClickHouse/pull/45615)
- [PR #45652: Safety guardrail](https://github.com/ClickHouse/ClickHouse/pull/45652)
