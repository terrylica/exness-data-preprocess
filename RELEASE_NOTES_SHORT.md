## 0.4.0 - 2025-10-18

### ✨ New Features

- V1.6.0 - fix session columns to check trading hours BREAKING CHANGE: Exchange session columns now check trading HOURS not just trading DAYS. This requires database regeneration. Package version bumped to 0.4.0. Changes: - Add trading hours to ExchangeConfig (open_hour, open_minute, close_hour, close_minute) - Update session_detector.py to check both trading day + time within hours - Fix timezone handling for naive timestamps (tz_localize) - Update 33 v1.5.0 references across 10 files - Bump package version 0.3.1 → 0.4.0 - Update schema version 1.5.0 → 1.6.0 - All 48 tests passing - Add comprehensive migration guide Details: - Core: exchanges.py, session_detector.py, schema.py - Modules: query_engine.py, database_manager.py, processor.py, api.py, ohlc_generator.py, **init**.py - Docs: README.md, CLAUDE.md, DATABASE_SCHEMA.md, docs/README.md, UNIFIED_DUCKDB_PLAN_v2.md - Examples: basic_usage.py, batch_processing.py - Migration: docs/plans/SCHEMA_v1.6.0_MIGRATION_GUIDE.md (by @terrylica)

- Implement lunch break support using exchange_calendars Replace manual trading hour checks with exchange_calendars.is_open_on_minute() to automatically handle lunch breaks for Asian exchanges. ## Changes ### Core Implementation (session_detector.py) - Replace manual hour/minute comparison with calendar.is_open_on_minute() - Simplifies code from 16 lines to 6 lines - Automatically handles lunch breaks, holidays, and trading hour changes ### Lunch Breaks Now Supported - Tokyo (XTKS): 11:30-12:30 JST - Hong Kong (XHKG): 12:00-13:00 HKT - Singapore (XSES): 12:00-13:00 SGT ### Benefits - Single source of truth for exchange hours (upstream library) - Auto-updates for trading hour changes (e.g., Tokyo extended to 15:30 on Nov 5, 2024) - Simpler, more maintainable code - Zero regressions (all 48 tests pass) ## End-to-End Validation Generated fresh test database (15 months, 450K+ OHLC bars) and verified: - Tokyo lunch (11:30-12:30 JST): 0/61 incorrectly flagged ✅ - Hong Kong lunch (12:00-13:00 HKT): 0/61 incorrectly flagged ✅ - Singapore lunch (12:00-13:00 SGT): 0/61 incorrectly flagged ✅ - Direct database verification: 0 session flags during lunch periods ✅ ## Documentation - Updated DATABASE_SCHEMA.md with lunch break details - Added comprehensive validation results to migration guide - Documented audit findings and resolution ## Breaking Change Databases generated with v1.6.0 before this fix need regeneration to respect lunch breaks. See docs/plans/SCHEMA_v1.6.0_MIGRATION_GUIDE.md. Closes: Asian exchange lunch break detection issue Ref: SCHEMA_v1.6.0_AUDIT_FINDINGS.md (by @terrylica)

### 🐛 Bug Fixes & Improvements

- Resolve 7 critical functionality issues (CLI, versions, schema) Critical Fixes: - Fix **version** in **init**.py (0.1.0 → 0.3.1) - Fix schema version in **init**.py (13-column v1.2.0 → 30-column v1.5.0) - Fix schema version in examples/basic_usage.py (3 occurrences) - Fix schema version in examples/batch_processing.py (1 occurrence) - Create api.py module (267 lines) for CLI backward compatibility - Remove 4 references to non-existent add_schema_comments.py from CLAUDE.md - Update api.py description in CLAUDE.md (legacy → compatibility layer with SLOs) API Module Design: - SLOs: Availability (raise on errors), Correctness (delegate to processor), Observability (logging), Maintainability (thin wrappers) - Functions: process_month(), process_date_range(), query_ohlc(), analyze_ticks(), get_storage_stats() - Architecture: Facade pattern wrapping ExnessDataProcessor - v1.0.0 monthly-file API → v2.0.0 unified single-file API mapping Validation Results: - CLI: Full functionality restored (process, query, analyze, stats commands working) - Tests: 48 passed in 100.88s (zero regressions) - Time to fix: 35 minutes (vs 40-150 estimated) Files Modified: - src/exness_data_preprocess/**init**.py (2 changes) - examples/basic_usage.py (3 changes) - examples/batch_processing.py (1 change) - src/exness_data_preprocess/api.py (NEW, 267 lines) - CLAUDE.md (4 changes) - docs/plans/FUNCTIONALITY_VALIDATION_REPORT_2025-10-15.md (implementation results) Closes all 7 issues from FUNCTIONALITY_VALIDATION_REPORT_2025-10-15.md (by @terrylica)

- Implement minute-level session detection (was checking midnight only) ## Critical Bug Fix **Problem**: Session flags were checked at MIDNIGHT timestamps then applied to all minutes of that day. For Tokyo (9:00-15:00 JST), midnight is NEVER during trading hours, so all session flags were incorrectly 0. **Root Cause** (ohlc_generator.py:151-184): - Line 152-153: Queried DISTINCT DATES (not timestamps) - Line 158: Created midnight timestamps from dates - Line 183: Applied midnight flag to ALL minutes via DATE match **Solution**: 1. Query ALL timestamps from ohlc_1m (not just unique dates) 2. Check session flags for EACH minute individually 3. Update database with exact timestamp match (not DATE match) ## Validation Results ### Tokyo Stock Exchange (XTKS) ✅ Lunch break (11:30-12:29 JST): 0/60 flagged (correct) ✅ Morning session (9:00-11:29 JST): 150/150 flagged (correct) ✅ Afternoon session (12:30-15:00 JST): 150/151 flagged (correct) ### Tokyo Extended Hours (Nov 5, 2024 transition) ✅ Before Nov 5: Closes 14:59 JST (15:00 close time) ✅ After Nov 5: Closes 15:29 JST (15:30 close time) ✅ Extended hours (15:00-15:30): 30/31 minutes flagged ### Test Suite ✅ All 48 tests pass ✅ Zero regressions ## Impact **Breaking Change**: Existing v1.6.0 databases need regeneration. - Previous: Session flags all 0 for Tokyo, Hong Kong, Singapore - Fixed: Session flags now correctly respect trading hours AND lunch breaks ## Implementation Details - **Before**: Date-level detection at midnight (broken for v1.6.0) - **After**: Minute-level detection using exchange_calendars.is_open_on_minute() - **Performance**: Acceptable (30-60s for 450K rows based on research) - **Lunch breaks**: Automatically handled by exchange_calendars - **Trading hour changes**: Automatically handled (e.g., Tokyo Nov 5, 2024) ## Research Backing 5 parallel research agents unanimously recommended this approach: - Option A: Minute-level Python detection ✅ (implemented) - Option B: SQL-based detection ❌ (181+ lines, no holiday support) - Option C: Hybrid approach ✅ (what we're doing) References: - /tmp/test_lunch_simple.py (validation script) - /tmp/test_tokyo_extended_hours.py (extended hours validation) - /tmp/test_tokyo_lunch_boundaries.py (boundary verification) (by @terrylica)

### 📝 Other Changes

- Revert "docs(CLAUDE.md): reorganize as hub-and-spoke with progressive disclosure" This reverts commit 6d0aa9a61c5d6a60bb3238aa7b8a018adf3f2796. (by @terrylica)

---

**Full Changelog**: https://github.com/Eon-Labs/rangebar/compare/v0.3.1...v0.4.0

---

📖 **Full Changelog**: [CHANGELOG.md](https://github.com/terrylica/exness-data-preprocess/blob/v0.5.0/CHANGELOG.md)

### Release Info

- **Package Version**: 0.5.0
- **Implementation Version**: v1.7.0 (Performance Optimizations)
- **Release Date**: 2025-10-18

### Key Achievements

- Incremental OHLC: 7.3x speedup
- Vectorized session detection: 2.2x speedup
- Combined Phase 1+2: ~16x total speedup
- SQL gap detection with complete coverage
- All 48 tests passing ✅
- Spike-test-first validation ✅
