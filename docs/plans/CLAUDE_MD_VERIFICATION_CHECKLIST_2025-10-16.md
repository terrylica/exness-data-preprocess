# CLAUDE.md Reorganization - Verification Checklist

**Date**: 2025-10-16
**Purpose**: Verify content exists elsewhere BEFORE removing from CLAUDE.md
**Principle**: Single source of truth - only remove if documented elsewhere with same detail level

---

## Verification Methodology

For each section in CLAUDE.md:

1. **Identify content** - What information is in this section?
2. **Search for alternatives** - Where else might this content exist?
3. **Verify detail level** - Does alternative have SAME level of detail?
4. **Decision**:
   - ✅ **REMOVE**: Content exists elsewhere with same detail → Replace with link
   - ⏳ **CREATE THEN REMOVE**: Content doesn't exist → Create new file, then link
   - ❌ **KEEP**: Content is essential for AI assistant → Keep in CLAUDE.md

---

## Section 1: Header (Lines 1-9)

### Content
```markdown
# CLAUDE.md
This file provides guidance to Claude Code...
**Architecture**: Professional forex tick data preprocessing...
**Full Documentation**: README.md
```

### Verification
- ❌ **Essential metadata** - Keep as-is
- Purpose statement needed for AI assistant context

### Decision
- ✅ **KEEP** - Essential header

---

## Section 2: Development Commands (Lines 11-65)

### Content
- Setup commands (uv sync, pip install)
- Testing commands (pytest, coverage)
- Code quality commands (ruff, mypy)
- Building and publishing commands (uv build, doppler)

### Verification
- Check README.md for these commands
- Check CONTRIBUTING.md for development workflow

### Search Plan
```bash
grep -n "uv sync" README.md CONTRIBUTING.md
grep -n "pytest" README.md CONTRIBUTING.md
grep -n "ruff format" README.md CONTRIBUTING.md
```

### Decision
- ⏳ **PENDING VERIFICATION**

---

## Section 3: Module Structure (Lines 71-157)

### Content
**Detailed module descriptions including**:
- Absolute file paths (e.g., `/Users/terryli/eon/exness-data-preprocess/src/exness_data_preprocess/processor.py`)
- Line number references (e.g., "Lines 76-110: __init__()")
- Specific SLOs (e.g., "Availability (raise on failure), Correctness (URL patterns)")
- Class names (e.g., `ExnessDownloader`, `TickLoader`, `DatabaseManager`)
- Method signatures (e.g., `download_zip(year, month, pair, variant)`)

**Example (downloader.py)**:
```markdown
2. **`downloader.py`** - HTTP download operations
   - **Responsibility**: Download Exness ZIP files from ticks.ex2archive.com
   - **SLOs**: Availability (raise on failure), Correctness (URL patterns),
     Observability (logging), Maintainability (httpx library)
   - **Class**: `ExnessDownloader`
   - **Methods**: `download_zip(year, month, pair, variant)`
```

### Verification Required
1. **Check docs/README.md** - Module architecture section
2. **Search for SLO details** - Does ANY file contain specific SLO descriptions?
3. **Search for class names** - Are class names documented elsewhere?
4. **Search for method signatures** - Are method signatures documented elsewhere?

### Search Plan
```bash
# Check if docs/README.md has module details
grep -A 5 "downloader.py" docs/README.md

# Check if any file has SLO descriptions
grep -r "Availability (raise on failure)" docs/

# Check if class names are documented
grep -r "ExnessDownloader" docs/ README.md

# Check if method signatures are documented
grep -r "download_zip(year, month, pair, variant)" docs/ README.md
```

### Decision
- ⏳ **PENDING VERIFICATION** - This is the CRITICAL section that was removed incorrectly last time

---

## Section 4: Key Design Patterns (Lines 159-200)

### Content
- Facade Pattern description
- Unified Single-File Architecture description
- Phase7 30-Column OHLC Schema overview
- Self-Documentation overview
- Data Flow diagram

### Verification Required
1. **Check docs/README.md** - Architecture patterns
2. **Check docs/UNIFIED_DUCKDB_PLAN_v2.md** - Architecture details

### Search Plan
```bash
grep -n "Facade Pattern" docs/README.md docs/UNIFIED_DUCKDB_PLAN_v2.md
grep -n "Unified Single-File" docs/README.md docs/UNIFIED_DUCKDB_PLAN_v2.md
grep -n "Data Flow" docs/README.md
```

### Decision
- ⏳ **PENDING VERIFICATION**

---

## Section 5: Database Schema (Lines 202-224)

### Content
- Table structure (raw_spread_ticks, standard_ticks, ohlc_1m, metadata)
- Column descriptions
- Primary keys
- Data characteristics

### Verification Required
1. **Check docs/DATABASE_SCHEMA.md** - Should contain complete schema

### Search Plan
```bash
grep -n "raw_spread_ticks" docs/DATABASE_SCHEMA.md
grep -n "standard_ticks" docs/DATABASE_SCHEMA.md
grep -n "ohlc_1m" docs/DATABASE_SCHEMA.md
grep -n "metadata" docs/DATABASE_SCHEMA.md
```

### Decision
- ⏳ **PENDING VERIFICATION** - High confidence this exists in DATABASE_SCHEMA.md

---

## Section 6: Quick Links (Lines 227-243)

### Content
- Documentation hub links
- Code examples links
- Development links

### Analysis
- This is the HUB section per hub-and-spoke pattern
- Should be MOVED to top (after header, before Development Commands)
- Content is essential (navigation)

### Decision
- ✅ **KEEP AND RELOCATE** - Move to line 11 (immediately after header)

---

## Section 7: Essential Architecture Decisions (Lines 246-340)

### Content

**7a. Unified Single-File DuckDB Storage (Lines 248-282)**:
- Implementation details
- Validation results (18.6M ticks, 19.6M ticks, 413K bars, 2.08 GB)
- Architecture benefits
- Links to plans

**7b. Phase7 30-Column OHLC Schema (Lines 284-310)**:
- Schema features
- Implementation file references
- Specification links

**7c. DuckDB Self-Documentation (Lines 312-339)**:
- COMMENT ON implementation
- Benefits
- Query examples
- Implementation references

### Verification Required
1. **Check docs/UNIFIED_DUCKDB_PLAN_v2.md** - Should have architecture details
2. **Check docs/DATABASE_SCHEMA.md** - Should have schema details
3. **Check docs/README.md** - Should have implementation status

### Search Plan
```bash
# Check for validation results
grep -n "18.6M ticks" docs/UNIFIED_DUCKDB_PLAN_v2.md docs/README.md

# Check for Phase7 features
grep -n "Phase7 30-column" docs/DATABASE_SCHEMA.md docs/README.md

# Check for self-documentation details
grep -n "COMMENT ON" docs/DATABASE_SCHEMA.md
```

### Decision
- ⏳ **PENDING VERIFICATION**

---

## Section 8: Exness Data Sources (Lines 343-356)

### Content
- Data source URL
- Variants used (Raw_Spread, Standard)
- Key characteristics
- URL patterns

### Verification Required
1. **Check docs/EXNESS_DATA_SOURCES.md** - Should have complete guide

### Search Plan
```bash
grep -n "ticks.ex2archive.com" docs/EXNESS_DATA_SOURCES.md
grep -n "Raw_Spread" docs/EXNESS_DATA_SOURCES.md
grep -n "Standard variant" docs/EXNESS_DATA_SOURCES.md
```

### Decision
- ⏳ **PENDING VERIFICATION** - High confidence this exists

---

## Section 9: Research Areas (Lines 360-381)

### Content
- Zero-Spread Deviation Analysis
- Compression Benchmarks
- Links to research docs

### Verification Required
1. **Check docs/research/** - Should have all research findings

### Search Plan
```bash
ls -la docs/research/
grep -n "Zero-Spread Deviation" docs/README.md docs/research/*/README.md
grep -n "Compression Benchmarks" docs/README.md docs/research/*/README.md
```

### Decision
- ⏳ **PENDING VERIFICATION**

---

## Section 10: Current Implementation Status (Lines 385-413)

### Content
- v2.0.0 Architecture status (✅ checkmarks)
- Usage examples links
- Pending tasks

### Verification Required
1. **Check docs/README.md** - Should have implementation status
2. **Check docs/UNIFIED_DUCKDB_PLAN_v2.md** - Should have status tracking

### Search Plan
```bash
grep -n "v2.0.0 Architecture" docs/README.md docs/UNIFIED_DUCKDB_PLAN_v2.md
grep -n "Completed 2025-10-12" docs/README.md docs/UNIFIED_DUCKDB_PLAN_v2.md
grep -n "Implementation Status" docs/README.md
```

### Decision
- ⏳ **PENDING VERIFICATION**

---

## Section 11: File Locations (Lines 417-443)

### Content
- Project root path
- Data storage structure
- Database schema structure
- Test artifacts location

### Verification Required
1. **Check README.md** - Should have installation/usage paths
2. **Check docs/README.md** - Should have project structure

### Search Plan
```bash
grep -n "~/eon/exness-data" README.md
grep -n "eurusd.duckdb" README.md
grep -n "Data Storage" README.md docs/README.md
```

### Decision
- ⏳ **PENDING VERIFICATION**

---

## Section 12: Migration from v1.0.0 (Lines 447-462)

### Content
- v1.0.0 (Legacy) structure
- v2.0.0 (Current) structure
- Migration steps

### Verification Required
1. **Check README.md** - Should have migration guide
2. **Check docs/archive/** - Should have legacy documentation

### Search Plan
```bash
grep -n "Migration" README.md docs/README.md
grep -n "v1.0.0" README.md docs/README.md
grep -n "process_month" README.md
```

### Decision
- ⏳ **PENDING VERIFICATION**

---

## Section 13: References (Lines 466-472)

### Content
- External links (Exness, DuckDB, Parquet, Zstd)

### Analysis
- External links are essential and won't exist in other project docs
- Should keep

### Decision
- ✅ **KEEP** - External references

---

## Next Steps

1. **Run all verification searches** - Execute grep commands above
2. **Document findings** - For each section, record:
   - ✅ Content exists elsewhere (safe to remove/link)
   - ❌ Content does NOT exist elsewhere (must keep or create)
   - ⚠️ Partial match (need to enhance existing doc first)
3. **Create reorganization plan** - Based on verification results
4. **Get user approval** - Present plan before making changes
5. **Implement changes** - Only after verification and approval

---

## Anti-Patterns to Avoid (Lessons Learned)

❌ **Don't**:
- Assume content exists elsewhere without verifying
- Remove detailed SLO information without checking
- Remove class names and method signatures without verifying
- Use absolute file paths (violates portability)
- Include line numbers (volatile, changes with code)

✅ **Do**:
- Verify BEFORE removing (grep, read files)
- Check detail level matches (not just topic exists)
- Create new docs if content doesn't exist elsewhere
- Link to introspection commands (e.g., `make module-stats`)
- Ask user if uncertain about what's "essential"

---

**Status**: Verification checklist created, searches pending
**Next**: Execute verification searches for each section
