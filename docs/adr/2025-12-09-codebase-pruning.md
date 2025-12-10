---
status: accepted
date: 2025-12-09
decision-maker: Terry Li
consulted:
  [Code-Pruning-Agent, Dependency-Pruning-Agent, Documentation-Pruning-Agent]
research-method: multi-agent
clarification-iterations: 1
perspectives: [Maintainability, Technical-Debt, Developer-Experience]
---

# Codebase Pruning: Dependencies, Documentation, and Code Cleanup

**Design Spec**: [Implementation Spec](/docs/design/2025-12-09-codebase-pruning/spec.md)

## Context and Problem Statement

After the ClickHouse migration (v0.8.0), the codebase has accumulated:

1. **Unused dependencies**: httpx (never imported), polars (abandoned experiment), pyarrow (research-only)
2. **Orphaned documentation**: 18 planning documents from completed Oct 2025 phases
3. **Code duplication**: 60+ lines of repeated client lifecycle code across ClickHouse modules
4. **Deprecated API layer**: 304-line api.py marked for removal

This technical debt increases install size by 80+ MB, confuses navigation, and violates DRY principles.

## Decision Drivers

- **Install size**: 200 MB → 120 MB (40% reduction)
- **Codebase clarity**: Remove orphaned files that confuse AI assistants
- **DRY compliance**: Eliminate duplicate ClickHouse client lifecycle code
- **Breaking change acceptance**: User approved api.py removal

## Considered Options

1. **Quick wins only**: Dependencies + documentation archival
2. **Quick wins + code refactoring**: Above + ClickHouseClientMixin
3. **Full pruning** (SELECTED): All above + remove deprecated api.py

## Decision Outcome

**Chosen option**: Full pruning including api.py removal

### Consequences

**Good**:

- 80+ MB smaller install size
- 400+ lines of code removed
- Cleaner documentation structure
- DRY-compliant ClickHouse modules

**Bad**:

- api.py removal is breaking change for any external consumers
- Research scripts in docs/research/ will need manual pyarrow install

## Architecture

### Before/After Diagram

<!-- graph-easy source:
[ pyproject.toml ] -- httpx (unused) --> [ 1 MB waste ]

[ pyproject.toml ] -- polars (unused) --> [ 50 MB waste ]
[ pyproject.toml ] -- pyarrow (research) --> [ 30 MB waste ]
[ docs/plans/ ] -- 15 orphaned files --> [ 7,405 lines ]
[ clickhouse_*.py (4) ] -- duplicate lifecycle --> [ 60 lines ]
[ api.py ] -- deprecated --> [ 304 lines ]
-->

```
+------------------+     httpx (unused)      +-------------+
| pyproject.toml   | ----------------------> | 1 MB waste  |
+------------------+                         +-------------+
        |
        |            polars (unused)         +-------------+
        +------------------------------->    | 50 MB waste |
        |                                    +-------------+
        |
        |           pyarrow (research)       +-------------+
        +------------------------------->    | 30 MB waste |
                                             +-------------+

+------------------+   15 orphaned files     +-------------+
|   docs/plans/    | ----------------------> | 7,405 lines |
+------------------+                         +-------------+

+------------------+  duplicate lifecycle    +-------------+
|clickhouse_*.py(4)| ----------------------> |  60 lines   |
+------------------+                         +-------------+

+------------------+     deprecated          +-------------+
|     api.py       | ----------------------> | 304 lines   |
+------------------+                         +-------------+
```

### After Pruning

<!-- graph-easy source:
[ pyproject.toml ] -- clean deps --> [ 120 MB install ]

[ docs/archive/ ] -- preserved --> [ Historical context ]
[ clickhouse_base.py ] -- mixin --> [ DRY code ]
[ api.py ] -- removed --> [ Breaking change logged ]
-->

```
+------------------+     clean deps          +----------------+
| pyproject.toml   | ----------------------> | 120 MB install |
+------------------+                         +----------------+

+------------------+     preserved           +------------------+
|  docs/archive/   | ----------------------> | Historical ctxt  |
+------------------+                         +------------------+

+--------------------+      mixin            +----------+
| clickhouse_base.py | --------------------> | DRY code |
+--------------------+                       +----------+

+------------------+     removed             +-------------------+
|     api.py       | ----------------------> | Breaking chg log  |
+------------------+                         +-------------------+
```

## Implementation Details

### Phase A: Dependency Cleanup

- Remove: httpx, pyarrow, polars
- Move: tqdm to `[project.optional-dependencies] examples`
- Consolidate: dev dependencies to `[dependency-groups]`

### Phase B: Documentation Cleanup

- Update .gitignore: node_modules/, .lychee\*, .token-info.md
- Archive: 18 planning documents to docs/archive/
- Update: docs/README.md

### Phase C: Code Cleanup

- Create: `clickhouse_base.py` with `ClickHouseClientMixin`
- Refactor: 4 ClickHouse modules to use mixin
- Delete: `api.py` (304 lines)
- Update: `__init__.py` exports

## More Information

- Related: [ClickHouse Migration ADR](/docs/adr/2025-12-09-exness-clickhouse-migration.md)
- Source Plan: `~/.claude/plans/lively-splashing-steele.md`
