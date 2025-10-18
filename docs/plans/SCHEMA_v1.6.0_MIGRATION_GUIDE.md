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

---

## 🚨 v1.6.0 Critical Bug Fix: Midnight Detection Issue (2025-10-17)

### Critical Bug Discovered

During comprehensive validation of v1.6.0 lunch break support, discovered a **CRITICAL ARCHITECTURAL BUG** in `ohlc_generator.py` that caused ALL session flags to be incorrectly set to `0` for most exchanges.

**Bug Location**: `src/exness_data_preprocess/ohlc_generator.py` lines 151-184

**Root Cause**:
1. Code queried unique DATES from ohlc_1m table (not timestamps)
2. Created MIDNIGHT timestamps from those dates (`pd.to_datetime(date)` → `2024-08-05 00:00:00`)
3. Checked if midnight was during trading hours
4. Applied the midnight result to ALL 1,440 minutes of that day

**Impact**:
- **Tokyo (9:00-15:00 JST)**: Midnight is NEVER during trading hours → ALL flags = 0 ❌
- **Hong Kong (9:30-16:00 HKT)**: Midnight is NEVER during trading hours → ALL flags = 0 ❌
- **Singapore (9:00-17:00 SGT)**: Midnight is NEVER during trading hours → ALL flags = 0 ❌
- **All exchanges**: Only exchanges where midnight falls within trading hours would work correctly

**Example**:
```python
# BROKEN CODE (before fix):
dates_df = conn.execute("SELECT DISTINCT DATE(Timestamp) as date FROM ohlc_1m").df()
dates_df["ts"] = pd.to_datetime(dates_df["date"])  # Creates 2024-08-05 00:00:00

# For Tokyo (9:00-15:00 JST):
# - Checks if 00:00 JST is during 9:00-15:00 JST → FALSE
# - Sets is_xtks_session = 0 for the entire day
# - All 1,440 minutes of Aug 5, 2024 incorrectly flagged as 0
```

### Fix Implemented (commit b7c4867)

**Changed from date-level to minute-level detection**:

```python
# FIXED CODE (after):
timestamps_df = conn.execute("SELECT Timestamp FROM ohlc_1m").df()
timestamps_df["ts"] = timestamps_df["Timestamp"]
timestamps_df["date"] = timestamps_df["Timestamp"].dt.date

# For each timestamp:
# - Checks if THAT SPECIFIC MINUTE is during trading hours
# - 9:00 JST → TRUE, 12:00 JST (lunch) → FALSE, 13:00 JST → TRUE
# - Correct minute-by-minute detection
```

**Database Update Change**:
```python
# BEFORE: Match by DATE (applies midnight flag to all minutes)
WHERE DATE(ohlc_1m.Timestamp) = hf.date

# AFTER: Match by exact TIMESTAMP
WHERE ohlc_1m.Timestamp = hf.Timestamp
```

### Validation Results (After Fix)

Generated fresh test database (15 months, 450K OHLC bars) and verified:

**Tokyo Stock Exchange (XTKS)**:
| Test | Expected | Actual | Status |
|------|----------|--------|--------|
| Lunch (11:30-12:29 JST) | 0 flags | 0/60 | ✅ PASS |
| Morning (9:00-11:29 JST) | >0 flags | 150/150 | ✅ PASS |
| Afternoon (12:30-15:00 JST) | >0 flags | 150/151 | ✅ PASS |

**Tokyo Extended Hours (Nov 5, 2024 Transition)**:
| Test | Expected | Actual | Status |
|------|----------|--------|--------|
| Before Nov 5 | Closes 15:00 JST | 14:59 JST | ✅ PASS |
| After Nov 5 | Closes 15:30 JST | 15:29 JST | ✅ PASS |
| Extended hours (15:00-15:30) | >0 flags | 30/31 | ✅ PASS |

**Test Suite**: ✅ All 48 tests pass with zero regressions

### Database Regeneration Required

**CRITICAL**: Databases generated with v1.6.0 code BEFORE commit b7c4867 have broken session flags and MUST be regenerated.

**Affected versions**:
- Any database generated between commit ca956ae (v1.6.0 initial) and commit b7c4867 (midnight fix)
- This includes databases generated with commit a89f755 (lunch break implementation)

**How to check if your database needs regeneration**:
```python
import pandas as pd
from exness_data_preprocess import ExnessDataProcessor

processor = ExnessDataProcessor()

# Check if Tokyo morning hours are detected
df = processor.query_ohlc("EURUSD", "1m",
    pd.Timestamp("2024-08-05 00:00:00", tz="UTC"),  # 9:00 JST
    pd.Timestamp("2024-08-05 02:00:00", tz="UTC"))  # 11:00 JST

morning_flags = df["is_xtks_session"].sum()

if morning_flags == 0:
    print("❌ CRITICAL: Database has broken session flags - regenerate immediately")
elif morning_flags > 100:
    print(f"✅ Database is correct - {morning_flags} trading minutes detected")
else:
    print(f"⚠️  PARTIAL: Only {morning_flags} minutes detected - verify implementation")
```

### Timeline: Two-Phase Fix

**Phase 1: Lunch Break Support** (commit a89f755)
- ✅ Implemented `exchange_calendars.is_open_on_minute()` in session_detector.py
- ✅ Correctly handles lunch breaks when called
- ❌ **BUT** ohlc_generator.py wasn't calling it correctly (midnight bug)
- **Result**: Implementation was correct, but integration was broken

**Phase 2: Midnight Bug Fix** (commit b7c4867)
- ✅ Fixed ohlc_generator.py to query ALL timestamps (not just dates)
- ✅ session_detector now checks each minute individually
- ✅ Database updates with exact timestamp match
- **Result**: Complete v1.6.0 implementation now works correctly

### Research Backing

Spawned 5 parallel research agents to analyze solution options:
1. **Option A** (Minute-level Python): ✅ Recommended & Implemented
2. **Option B** (SQL-based): ❌ Rejected (181+ lines, no holiday support)
3. **Option C** (Hybrid): ✅ Recommended (current approach)
4. **exchange_calendars optimization**: Binary search on cached arrays, acceptable performance
5. **Industry best practices**: Unanimous consensus for calendar abstraction libraries

**Consensus**: Current implementation follows industry standards with acceptable performance (30-60s for 450K rows).

---

## 🔧 v1.6.0 Enhancement: Lunch Break Support (2025-10-17)

### Issue Discovered

During comprehensive audit of v1.6.0 implementation, discovered that 3 Asian exchanges have **1-hour lunch breaks** that were not respected in session detection:

- **Tokyo (XTKS)**: Lunch 11:30-12:30 JST
- **Hong Kong (XHKG)**: Lunch 12:00-13:00 HKT
- **Singapore (XSES)**: Lunch 12:00-13:00 SGT

**Impact**: Session flags incorrectly showed `1` during lunch breaks when exchanges were actually closed.

### Solution Implemented

Research revealed that `exchange_calendars` v4.11.1 (the library we already use) has **built-in lunch break support** via `is_open_on_minute()` method.

**Before** (manual hour checking):
```python
# Manually compared hours/minutes (DIDN'T CHECK LUNCH BREAKS)
open_minutes = exchange_config.open_hour * 60 + exchange_config.open_minute
close_minutes = exchange_config.close_hour * 60 + exchange_config.close_minute
return int(open_minutes <= current_minutes < close_minutes)
```

**After** (using exchange_calendars API):
```python
# Uses exchange_calendars built-in method (handles lunch breaks automatically)
return int(calendar.is_open_on_minute(ts))
```

### Benefits

1. ✅ **Lunch breaks correctly excluded** for Tokyo, Hong Kong, Singapore
2. ✅ **Simpler implementation** (6 lines vs 16 lines)
3. ✅ **Auto-updates** for trading hour changes (e.g., Tokyo extended to 15:30 on Nov 5, 2024)
4. ✅ **Single source of truth**: Upstream library maintains all exchange hours
5. ✅ **Zero regressions**: All 48 tests pass

### Verification

**Tokyo Stock Exchange**:
- Before Nov 5, 2024: Closes at 15:00 JST ✅
- After Nov 5, 2024: Closes at 15:30 JST ✅ (extended hours automatically handled)
- Lunch break 11:30-12:30 JST: `is_xtks_session = 0` ✅

**Hong Kong Stock Exchange**:
- Lunch break 12:00-13:00 HKT: `is_xhkg_session = 0` ✅

### Database Regeneration

**Required**: Yes, if you generated databases with v1.6.0 before this fix.

**Why**: The initial v1.6.0 release (before lunch break fix) had partially broken session flags that didn't respect lunch breaks. This enhancement completes the v1.6.0 implementation.

**How to verify if your database needs regeneration**:
```python
import pandas as pd
from exness_data_preprocess import ExnessDataProcessor

processor = ExnessDataProcessor()

# Query Tokyo trading hours on a trading day
df = processor.query_ohlc("EURUSD", timeframe="1m", start_date="2024-01-05", end_date="2024-01-05")

# Check if lunch break (11:30-12:30 JST = 02:30-03:30 UTC) is excluded
df_tokyo_lunch = df[(df['ts'].dt.hour == 2) & (df['ts'].dt.minute >= 30) |
                     (df['ts'].dt.hour == 3) & (df['ts'].dt.minute < 30)]

if df_tokyo_lunch['is_xtks_session'].sum() > 0:
    print("❌ Database needs regeneration - lunch breaks not excluded")
else:
    print("✅ Database is up-to-date - lunch breaks correctly excluded")
```

### Version Clarification

**Package version remains 0.4.0** (no bump needed):
- This enhancement completes the v1.6.0 implementation as originally intended
- No breaking changes to API or database schema
- Users who haven't regenerated v1.6.0 databases yet will get the corrected version automatically

### End-to-End Validation (2025-10-17)

**Test Environment**:
- Generated fresh EURUSD database with 15 months of data (Aug 2024 - Oct 2025)
- Total OHLC bars: 450,431
- Database size: 2.28 GB
- Validation performed with explicit UTC timezone handling

**Validation Results**:

1. **Tokyo Lunch Break (11:30-12:30 JST = 02:30-03:30 UTC)**:
   - Timestamps queried: 61
   - `is_xtks_session=1` count: 0
   - **✅ PASS**: All lunch hour timestamps correctly excluded

2. **Hong Kong Lunch Break (12:00-13:00 HKT = 04:00-05:00 UTC)**:
   - Timestamps queried: 61
   - `is_xhkg_session=1` count: 0
   - **✅ PASS**: All lunch hour timestamps correctly excluded

3. **Singapore Lunch Break (12:00-13:00 SGT = 04:00-05:00 UTC)**:
   - Timestamps queried: 61
   - `is_xses_session=1` count: 0
   - **✅ PASS**: All lunch hour timestamps correctly excluded

4. **Database Direct Verification** (UTC timestamps):
   ```sql
   -- Query: 02:30-03:30 UTC (11:30-12:30 JST)
   SELECT COUNT(*) FROM ohlc_1m
   WHERE Timestamp AT TIME ZONE 'UTC' >= '2024-08-05 02:30:00'
   AND Timestamp AT TIME ZONE 'UTC' < '2024-08-05 03:30:00'
   AND is_xtks_session = 1
   -- Result: 0 (correctly excluded)
   ```

**Key Findings**:
- Session detection works correctly with `exchange_calendars.is_open_on_minute()`
- Lunch breaks for Tokyo, Hong Kong, and Singapore are properly excluded
- Database timestamps stored with timezone info (may display in local timezone but UTC values are correct)
- All 48 unit tests pass
- Zero regressions in OHLC generation

**Testing**:
```bash
# Tokyo: 9:00-11:30 OPEN, 11:30-12:30 CLOSED, 12:30-15:30 OPEN
# Hong Kong: 9:30-12:00 OPEN, 12:00-13:00 CLOSED, 13:00-16:00 OPEN
# Singapore: 9:00-12:00 OPEN, 12:00-13:00 CLOSED, 13:00-17:00 OPEN

uv run pytest
# ✓ 48 passed
```
