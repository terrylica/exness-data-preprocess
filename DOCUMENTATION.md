# 📚 Documentation Hub

**Welcome!** This page organizes all documentation from beginner to advanced, helping you find exactly what you need.

---

## 🎯 Quick Start (5 Minutes)

New to this project? Start here:

1. **[README.md](README.md)** - Installation, features, and quick start guide
2. **[Basic Usage Examples](examples/basic_usage.py)** - Download data, query OHLC/ticks, coverage checks
3. **[Contributing Guide](CONTRIBUTING.md)** - Want to contribute? Start here

**Next Steps**: Read [Data Sources](#-understanding-the-data) below to understand what data you're working with.

---

## 📖 Beginner Path (Your First Hour)

Follow this path if you're new to the project:

### 1. Getting Started
- **[README.md](README.md)** - Main documentation with installation and API reference
- **[Basic Usage Examples](examples/basic_usage.py)** - 6 practical code examples you can run immediately
- **[Contributing Guide](CONTRIBUTING.md)** - Development setup, code quality, testing

### 2. Understanding the Data
- **[Exness Data Sources](docs/EXNESS_DATA_SOURCES.md)** - Raw_Spread vs Standard variants, data quality characteristics
  - Learn about 97.81% zero-spreads in Raw_Spread (execution prices)
  - Understand tick density and storage estimates
  - See CSV format and download patterns

### 3. First Queries
- **[Database Schema](docs/DATABASE_SCHEMA.md)** - Phase7 30-column OHLC structure
  - 4 tables: raw_spread_ticks, standard_ticks, ohlc_1m, metadata
  - SQL query examples and performance benchmarks
  - 10 global exchange sessions with trading hours

**Checkpoint**: After this section, you should be able to download data and run basic queries.

---

## 🚀 Intermediate Path (Production Usage)

Ready for multi-instrument processing and advanced queries:

### 4. Advanced Workflows
- **[Batch Processing Examples](examples/batch_processing.py)** - Multi-instrument parallel processing
  - Sequential and parallel processing patterns
  - Error handling and retry logic
  - Progress monitoring with tqdm

### 5. Research Methodology
- **[Research Patterns](docs/RESEARCH_PATTERNS.md)** - pandas/Polars vs DuckDB tool selection
  - Research lifecycle: Explore → Validate → Graduate → Query
  - Hybrid materialization pattern
  - Performance benchmarks (ASOF joins: pandas 0.04s vs DuckDB 0.89s)

### 6. Schema Deep Dive
- **[Schema v1.6.0 Migration Guide](docs/plans/SCHEMA_v1.6.0_MIGRATION_GUIDE.md)** - Breaking changes from v1.5.0
  - 19 → 30 columns (added 10 exchange sessions + 1 major holiday flag)
  - Midnight detection bug fix (critical for session flags)
  - Migration steps and validation

**Checkpoint**: You can now process multiple instruments efficiently and choose the right tools for research.

---

## 🏗️ Advanced Path (Architecture & Development)

For contributors and researchers who need deep understanding:

### 7. System Architecture
- **[Module Architecture](docs/MODULE_ARCHITECTURE.md)** ⭐ *v1.3.1 - Verified Accurate*
  - Facade pattern with 6 module instances + 1 static utility
  - SLO-based design (Availability, Correctness, Observability, Maintainability)
  - Complete data flow with 3 Mermaid diagrams
  - See [Architecture Audit](docs/validation/ARCHITECTURE_AUDIT_2025-10-17.md) for verification

- **[Unified DuckDB Plan v2.0.0](docs/UNIFIED_DUCKDB_PLAN_v2.md)** - Storage architecture
  - Single-file per instrument (eurusd.duckdb)
  - Incremental updates with gap detection
  - PRIMARY KEY prevents duplicates

### 8. Trading Hours Implementation
- **[Trading Hours Research](docs/TRADING_HOURS_RESEARCH.md)** - Industry analysis (49KB comprehensive)
  - 5 quant finance libraries studied
  - 3 professional platforms analyzed
  - 4 time-series databases compared
  - Unanimous consensus for calendar abstraction

- **[Hybrid Session Detection Analysis](docs/research/HYBRID_SESSION_DETECTION_ANALYSIS.md)** - Implementation rationale
  - Why holidays are date-level but sessions are minute-level
  - DuckDB performance optimization
  - Bulk UPDATE strategies

### 9. Validation & Quality Assurance
- **[E2E Validation Results v1.6.0](docs/validation/E2E_VALIDATION_RESULTS_v1.6.0.md)** ⭐ *100% Accuracy*
  - 355,970 bars of real EURUSD data (12 months, 1.92 GB)
  - Tokyo lunch breaks: 0/59 lunch, 150/150 morning, 151/151 afternoon
  - Holidays, DST, weekend gaps, exchange overlaps all verified

- **[Weekend Gap Validation](docs/validation/WEEKEND_GAP_VALIDATION_SUMMARY.md)** - Timezone-aware weekend handling
  - 48-hour forex gap (Friday 22:00 UTC → Sunday 22:00 UTC)
  - New Zealand opens first (Monday 10:00 NZST = Sunday 21:00 UTC)

- **[Architecture Audit Report](docs/validation/ARCHITECTURE_AUDIT_2025-10-17.md)** - Documentation accuracy verification
  - 78% → 100% accuracy after comprehensive audit
  - All constructor signatures verified
  - HTTP library, type signatures, data flow corrected

**Checkpoint**: You understand the system design and can confidently extend the codebase.

---

## 📊 Research Projects (Deep Dives)

Published research with reproduction guides:

### Zero-Spread Deviation Analysis
- **[Project Overview](docs/research/eurusd-zero-spread-deviations/README.md)** - 16-month validation study
- **[Methodology](docs/research/eurusd-zero-spread-deviations/01-methodology.md)** - Research approach
- **[Baseline Analysis](docs/research/eurusd-zero-spread-deviations/02-baseline-sep2024.md)** - September 2024 baseline
- **[Multi-Period Validation](docs/research/eurusd-zero-spread-deviations/03-multiperiod-validation.md)** - Extended validation
- **[Discoveries](docs/research/eurusd-zero-spread-deviations/04-discoveries-and-plan-evolution.md)** - Plan evolution
- **[Reproduction Guide](docs/research/eurusd-zero-spread-deviations/scripts/reproduction_guide.md)** - How to reproduce results

### Spread Variant Analysis
- **[Project Overview](docs/research/eurusd-spread-analysis/README.md)** - Modal-band-excluded variance estimation
- **[Methodology](docs/research/eurusd-spread-analysis/01-methodology.md)** - Research design
- **[Mode-Truncated Analysis](docs/research/eurusd-spread-analysis/02-mode-truncated-analysis.md)** - Truncation approach
- **[Hurdle Model](docs/research/eurusd-spread-analysis/03-hurdle-model-analysis.md)** - Two-part model
- **[Temporal Patterns](docs/research/eurusd-spread-analysis/04-temporal-patterns.md)** - Time-based analysis
- **[Recommendations](docs/research/eurusd-spread-analysis/05-final-recommendations.md)** - Final guidance
- **[Reproduction Guide](docs/research/eurusd-spread-analysis/scripts/reproduction_guide.md)** - How to reproduce

### Compression Benchmarks
- **[Compression Study](docs/research/compression-benchmarks/README.md)** - Why Parquet + Zstd-22

---

## 📚 Reference Documentation

Quick lookups and specific information:

### API & Schema
- **[README.md](README.md)** - Complete API reference with examples
- **[Database Schema](docs/DATABASE_SCHEMA.md)** - 30-column Phase7 OHLC specification
- **[CLAUDE.md](CLAUDE.md)** - AI assistant quick reference (architecture summary)

### Version History
- **[CHANGELOG.md](CHANGELOG.md)** - Version history (Keep a Changelog format)
- **[RELEASE_NOTES.md](RELEASE_NOTES.md)** - Human-readable release notes
- **[AUTHORS.md](AUTHORS.md)** - Project contributors

### Testing
- **[Test Suite Documentation](tests/README.md)** - 48 tests, coverage reports
- **[Makefile](Makefile)** - Build commands (`make test`, `make module-stats`, etc.)

---

## 🔧 Development & Planning

Internal documentation for contributors:

### Current Plans
- **[Documentation Hub](docs/README.md)** - Hub-and-spoke architecture with progressive disclosure
- **[Implementation Plan](docs/implementation-plan.yaml)** - Machine-readable implementation plan with SLOs
- **[Planning Index](docs/planning-index.yaml)** - Index of all planning documents

### Migration & Refactoring
- **[Schema v1.6.0 Migration Guide](docs/plans/SCHEMA_v1.6.0_MIGRATION_GUIDE.md)** - v1.5.0 → v1.6.0 breaking changes
- **[Phase7 v1.6.0 Progress](docs/plans/PHASE7_v1.6.0_REFACTORING_PROGRESS.md)** - Refactoring progress tracking
- **[Refactoring Checklist](docs/plans/REFACTORING_CHECKLIST.md)** - Comprehensive checklist

### Quality Audits
- **[Workspace Survey](docs/validation/WORKSPACE_SURVEY_2025-10-17.md)** - Organization assessment (2025-10-17)
- **[Architecture Audit](docs/validation/ARCHITECTURE_AUDIT_2025-10-17.md)** - Documentation accuracy (2025-10-17)
- **[Functionality Validation](docs/plans/FUNCTIONALITY_VALIDATION_REPORT_2025-10-16.md)** - Feature testing (2025-10-16)

---

## 📁 Archive

Historical documentation (for reference only):

- **[Unified DuckDB Plan v1.0.0](docs/archive/UNIFIED_DUCKDB_PLAN_v1.0.0_LEGACY.md)** - Legacy architecture (superseded by v2.0.0)
- **[Pydantic Refactoring Plan](docs/archive/PYDANTIC_REFACTORING_PLAN_v0.2.0_COMPLETE.md)** - Completed v0.2.0
- **[E2E Testing Plan](tests/archive/E2E_TESTING_PLAN_v1.0.0.md)** - Archived testing approach

---

## 🗺️ Documentation Organization

This project uses a **hub-and-spoke model** with progressive disclosure:

```
DOCUMENTATION.md (You are here - Hub)
├── Beginner Path → README → Examples → Data Sources
├── Intermediate Path → Batch Processing → Research Patterns → Migration Guide
├── Advanced Path → Module Architecture → DuckDB Plan → Trading Hours Research
├── Research Projects → Zero-Spread Analysis → Spread Variant Analysis
└── Reference → API Docs → Schema → Testing
```

**Navigation Tips**:
- 🎯 = Start here if you're new
- ⭐ = Critical documentation (verified accurate)
- All links use relative URLs from project root
- Use browser search (Ctrl+F / Cmd+F) to find specific topics

---

## 🤔 Which Documentation Should I Read?

### "I just want to download forex data and analyze it"
→ [README.md](README.md) → [Basic Usage Examples](examples/basic_usage.py)

### "I need to process multiple currency pairs efficiently"
→ [Batch Processing Examples](examples/batch_processing.py)

### "I want to write SQL queries against tick data"
→ [Database Schema](docs/DATABASE_SCHEMA.md)

### "I'm doing quantitative research with temporal analysis"
→ [Research Patterns](docs/RESEARCH_PATTERNS.md) → [Database Schema](docs/DATABASE_SCHEMA.md)

### "I want to contribute code to this project"
→ [Module Architecture](docs/MODULE_ARCHITECTURE.md) → [Contributing Guide](CONTRIBUTING.md)

### "I need to understand trading hour detection"
→ [Trading Hours Research](docs/TRADING_HOURS_RESEARCH.md) → [E2E Validation](docs/validation/E2E_VALIDATION_RESULTS_v1.6.0.md)

---

## 📞 Getting Help

- **Issues**: [GitHub Issues](https://github.com/terrylica/exness-data-preprocess/issues)
- **Contributing**: See [CONTRIBUTING.md](CONTRIBUTING.md)
- **License**: [MIT License](LICENSE)

---

**Last Updated**: 2025-10-17
**Documentation Version**: v1.3.1
**Total Documentation Files**: 68 markdown files + 2 Python examples + 2 YAML specs
