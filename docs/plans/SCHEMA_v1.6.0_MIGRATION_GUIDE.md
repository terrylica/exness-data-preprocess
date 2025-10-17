# Schema v1.6.0 Migration Guide

**Date**: 2025-10-17
**Schema Version**: v1.5.0 → v1.6.0
**Package Version**: 0.3.1 → 0.4.0
**Type**: Breaking Change (Requires Database Regeneration)

---

## Summary

Schema v1.6.0 fixes a semantic mismatch in exchange session columns. Previously, `is_*_session` columns only checked if a DATE was a trading day, but the column names implied they checked if the TIME was during trading HOURS.

**Example of the Problem**:
- v1.5.0: `is_nyse_session = 1` at 3 AM on Monday (NYSE doesn't open until 9:30 AM!)
- v1.6.0: `is_nyse_session = 0` at 3 AM, `1` only during 9:30 AM - 4:00 PM ET

---

## What Changed

### Core Implementation

1. **exchanges.py** - Added trading hours to ExchangeConfig dataclass:
   - `open_hour`, `open_minute` - Trading start time (24-hour format)
   - `close_hour`, `close_minute` - Trading close time (24-hour format)

2. **session_detector.py** - Updated detection logic:
   - **Before**: Only checked `calendar.is_session(date)` (trading day check)
   - **After**: Checks BOTH trading day AND time within trading hours:
     ```python
     # Check if trading day (excludes weekends + holidays)
     if not calendar.is_session(ts.date()):
         return 0

     # Convert to exchange timezone and check trading hours
     local_time = ts.tz_convert(exchange_config.timezone)
     return int(open_minutes <= current_minutes < close_minutes)
     ```

3. **schema.py** - Bumped version to v1.6.0, updated column comments to reflect hour-based detection

### Documentation Updates

All references updated from v1.5.0 to v1.6.0 across:
- README.md (4 references)
- CLAUDE.md
- docs/DATABASE_SCHEMA.md
- docs/README.md
- docs/UNIFIED_DUCKDB_PLAN_v2.md (5 references)
- examples/basic_usage.py (3 references)
- examples/batch_processing.py (1 reference)

### Source Code Updates

All v1.5.0 references updated in 8 modules:
- query_engine.py (1 reference)
- database_manager.py (3 references)
- exchanges.py (4 references)
- __init__.py (1 reference)
- processor.py (6 references)
- api.py (1 reference)
- ohlc_generator.py (6 references)
- schema.py (1 reference, plus version history)

---

## Impact

**Breaking Change**: Existing databases with v1.5.0 schema are INCOMPATIBLE with v1.6.0.

**Why**: The `is_*_session` column values will change significantly:
- v1.5.0: `1` for all timestamps on trading days (00:00-23:59)
- v1.6.0: `1` only during exchange trading hours (e.g., NYSE 9:30-16:00 ET)

**Data Loss**: Any analysis, backtests, or strategies relying on the old session columns will produce different results after migration.

---

## Migration Steps

### Step 1: Backup Existing Data (Optional)

If you want to preserve v1.5.0 databases for comparison:

```bash
# Backup existing databases
cp ~/eon/exness-data/eurusd.duckdb ~/eon/exness-data/eurusd_v1.5.0_backup.duckdb
```

### Step 2: Update Package

```bash
# Using pip
pip install --upgrade exness-data-preprocess

# Using uv
uv pip install --upgrade exness-data-preprocess

# Verify version
python -c "import exness_data_preprocess; print(exness_data_preprocess.__version__)"
# Should output: 0.4.0
```

### Step 3: Regenerate Databases

**Option A: Delete and Re-download (Recommended)**

```bash
# Delete existing database
rm ~/eon/exness-data/eurusd.duckdb

# Re-download with v1.6.0 schema
python -c "
import exness_data_preprocess as edp
processor = edp.ExnessDataProcessor()
result = processor.update_data('EURUSD', start_date='2022-01-01', delete_zip=True)
print(f'Regenerated: {result[\"months_added\"]} months')
"
```

**Option B: In-Place Regeneration (Advanced)**

If you want to preserve tick data and only regenerate OHLC:

```python
import exness_data_preprocess as edp

processor = edp.ExnessDataProcessor()

# This will regenerate OHLC with v1.6.0 schema using existing tick data
result = processor.update_data("EURUSD", start_date="2022-01-01")
print(f"Regenerated OHLC with {result['ohlc_bars']:,} bars")
```

### Step 4: Verify Schema Version

```python
import duckdb

conn = duckdb.connect("~/eon/exness-data/eurusd.duckdb", read_only=True)

# Check table comment for version
comment = conn.execute("""
    SELECT obj_description('ohlc_1m'::regclass)
""").fetchone()[0]
print(comment)

# Should contain "Phase7 v1.6.0"
conn.close()
```

### Step 5: Validate Session Columns

```python
import exness_data_preprocess as edp

processor = edp.ExnessDataProcessor()

# Query OHLC for a trading day
df = processor.query_ohlc("EURUSD", timeframe="1m", start_date="2024-01-02", end_date="2024-01-02")

# Check NYSE session flags
nyse_sessions = df[df["is_nyse_session"] == 1]
print(f"NYSE session hours: {nyse_sessions['ny_hour'].min()}-{nyse_sessions['ny_hour'].max()}")
# Should output: 9-15 (9:30 AM - 3:59 PM ET)

# Before v1.6.0, this would show 0-23 (entire day)
```

---

## Testing

All 48 tests pass with v1.6.0:

```bash
uv run pytest
# ✓ 48 passed
```

**Key Test Validations**:
1. Session detection correctly checks trading hours
2. Timezone-naive timestamps are handled properly
3. Exchange session flags are 0 outside trading hours
4. Holiday detection remains accurate
5. No regressions in OHLC generation

---

## Backward Compatibility

**API Compatibility**: ✅ PRESERVED
All public API methods remain unchanged:
- `processor.update_data()`
- `processor.query_ohlc()`
- `processor.query_ticks()`
- `processor.get_data_coverage()`

**Data Compatibility**: ❌ BROKEN
Session column semantics changed, requiring database regeneration.

---

## Rollback (If Needed)

If you need to rollback to v1.5.0:

```bash
# 1. Uninstall v1.6.0
pip uninstall exness-data-preprocess

# 2. Install v1.5.0
pip install exness-data-preprocess==0.3.1

# 3. Restore backup
cp ~/eon/exness-data/eurusd_v1.5.0_backup.duckdb ~/eon/exness-data/eurusd.duckdb
```

---

## FAQ

### Q: Do I need to regenerate ALL databases?

**A**: Only if you use the `is_*_session` columns in your analysis. If you only use OHLC prices and don't rely on session flags, the impact is minimal (but regeneration is still recommended for consistency).

### Q: How long does regeneration take?

**A**: ~15-30 minutes per instrument for 3 years of data (depending on network speed). The process is fully automatic.

### Q: Will this affect my existing backtests?

**A**: Yes, if your backtests filter by session flags (e.g., "only trade during NYSE hours"). You'll need to re-run backtests with the corrected data.

### Q: Why not just rename the columns to `is_*_trading_day`?

**A**: We considered this, but:
1. Column names would be misleading ("day" implies date, not hour)
2. Users expect session flags to mean "during trading hours"
3. Fixing the values matches industry convention

### Q: Can I use both v1.5.0 and v1.6.0 in parallel?

**A**: Yes, store databases in separate directories:
```python
processor_v15 = edp.ExnessDataProcessor(base_dir="~/eon/exness-data-v1.5.0")
processor_v16 = edp.ExnessDataProcessor(base_dir="~/eon/exness-data-v1.6.0")
```

---

## References

- **Audit Document**: `docs/plans/EXCHANGE_SESSION_AUDIT_2025-10-17.md`
- **Schema Documentation**: `docs/DATABASE_SCHEMA.md`
- **Architecture**: `docs/UNIFIED_DUCKDB_PLAN_v2.md`
- **Issue**: Option A implementation from audit document

---

## Changelog

**v1.6.0 (2025-10-17)**:
- **BREAKING**: Fixed session columns to check trading HOURS not just trading DAYS
- Added trading hours to ExchangeConfig (open_hour, open_minute, close_hour, close_minute)
- Updated session_detector.py to perform timezone conversion and hour range checks
- Bumped package version to 0.4.0 (SemVer breaking change)
- All 48 tests passing
- Documentation updated across 10 files
- Source code updated across 8 modules

**v1.5.0 (2025-10-15)**:
- Added 10 global exchange session flags
- Replaced hardcoded NYSE/LSE with dynamic exchange registry
- 30-column Phase7 OHLC schema
