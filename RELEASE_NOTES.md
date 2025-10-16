## 0.3.1 - 2025-10-16

### Architecture Improvements

Refactored processor.py from monolithic 885-line file into 7 focused modules (53% reduction to 412 lines) using facade pattern with separation of concerns.

**Modules Created**:
- `downloader.py` (82 lines): HTTP download operations
- `tick_loader.py` (67 lines): CSV parsing
- `database_manager.py` (208 lines): Database operations
- `session_detector.py` (121 lines): Holiday and session detection
- `gap_detector.py` (157 lines): Incremental update logic
- `ohlc_generator.py` (199 lines): Phase7 OHLC generation
- `query_engine.py` (290 lines): Query operations

**Design Principles**:
- Facade pattern: processor.py delegates to specialized modules
- SLO-based: All modules define Availability, Correctness, Observability, Maintainability
- Off-the-shelf libraries: httpx, pandas, DuckDB, exchange_calendars (no custom implementations)
- Zero regressions: All 48 tests pass, backward compatible

**For Users**:
No API changes - all existing code continues to work. Internal refactoring improves maintainability and sets foundation for future enhancements.

---
**Full Changelog**: https://github.com/terrylica/exness-data-preprocess/compare/v0.3.0...v0.3.1
