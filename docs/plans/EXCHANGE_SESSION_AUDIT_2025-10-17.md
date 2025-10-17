# Exchange Session Column Audit & Proposal

**Date**: 2025-10-17
**Type**: Critical Bug Fix + Architecture Decision
**Status**: ⚠️ Issue Confirmed - Awaiting User Decision

---

## Executive Summary

**Issue Identified**: Exchange session columns (`is_*_session`) misrepresent their values. They only check if a minute falls on a **trading day** (not weekend/holiday), but do NOT check if it's during actual **trading hours**.

**Impact**: For forex tick data analysis, this makes the columns misleading. A minute at 3 AM on a Monday will show `is_nyse_session=1` even though NYSE is closed (opens at 9:30 AM ET).

**Severity**: High - Column naming implies intraday session detection, but implementation only provides trading day flags.

---

## Current Implementation Analysis

### What the Columns Do Now

**File**: `src/exness_data_preprocess/session_detector.py:119`

```python
dates_df[col_name] = dates_df["ts"].apply(lambda d, cal=calendar: int(cal.is_session(d)))
```

**Behavior**: `exchange_calendars.is_session(date)` returns `True` if the **date** is a trading day (not weekend, not holiday).

**Example** (Monday, Jan 8, 2024):

| UTC Time | ET Time | is_nyse_session | What It Means |
|----------|---------|-----------------|---------------|
| 08:00    | 03:00 AM | 1 | ✗ NYSE closed (opens 9:30 AM) |
| 14:00    | 09:00 AM | 1 | ✗ NYSE closed (opens 9:30 AM) |
| 15:00    | 10:00 AM | 1 | ✓ NYSE open |
| 19:00    | 02:00 PM | 1 | ✓ NYSE open |
| 21:00    | 04:00 PM | 1 | ✗ NYSE closed (closes 4:00 PM) |
| 23:00    | 06:00 PM | 1 | ✗ NYSE closed |

**Problem**: Column is `1` for ALL minutes on a trading day, regardless of actual trading hours.

### Test Verification

**Test Script**: `/tmp/test_session_logic.py`

**Results**:
```
2024-01-08 08:00:00  03:00 AM ET     1               0               ✗ MISMATCH
2024-01-08 14:00:00  09:00 AM ET     1               0               ✗ MISMATCH
2024-01-08 15:00:00  10:00 AM ET     1               1               ✓
2024-01-08 19:00:00  02:00 PM ET     1               1               ✓
2024-01-08 21:00:00  04:00 PM ET     1               0               ✗ MISMATCH
2024-01-08 23:00:00  06:00 PM ET     1               0               ✗ MISMATCH
```

4 out of 6 test cases fail - column values are incorrect for times outside trading hours.

---

## Inconsistency with Existing Columns

### Existing Session Columns (Correct Implementation)

**File**: `src/exness_data_preprocess/ohlc_generator.py:123-133`

Already have **hour-based session detection** for NYSE and LSE:

```sql
CASE
    WHEN EXTRACT(HOUR FROM (DATE_TRUNC('minute', r.Timestamp) AT TIME ZONE 'America/New_York')) BETWEEN 9 AND 16 THEN 'NY_Session'
    WHEN EXTRACT(HOUR FROM (DATE_TRUNC('minute', r.Timestamp) AT TIME ZONE 'America/New_York')) BETWEEN 17 AND 20 THEN 'NY_After_Hours'
    ELSE 'NY_Closed'
END as ny_session,

CASE
    WHEN EXTRACT(HOUR FROM (DATE_TRUNC('minute', r.Timestamp) AT TIME ZONE 'Europe/London')) BETWEEN 8 AND 16 THEN 'London_Session'
    ELSE 'London_Closed'
END as london_session
```

**These work correctly** - they check actual trading hours!

### Column Comparison

| Column Name | Current Behavior | Use Case |
|-------------|------------------|----------|
| `ny_session` | ✓ Checks trading HOURS (9-16h ET) | Intraday analysis |
| `london_session` | ✓ Checks trading HOURS (8-16h GMT) | Intraday analysis |
| `is_nyse_session` | ✗ Only checks trading DAY | **Misleading** |
| `is_lse_session` | ✗ Only checks trading DAY | **Misleading** |
| `is_xswx_session` | ✗ Only checks trading DAY | **Misleading** |
| ... (8 more) | ✗ Only checks trading DAY | **Misleading** |

---

## Root Cause

### Semantic Confusion

The column name `is_*_session` implies:
- "Is this minute during the exchange's trading session?"

But the implementation only checks:
- "Does this minute fall on a day when the exchange is open?"

### Why This Happened

1. `exchange_calendars` library's `is_session()` method operates at **day granularity**, not minute granularity
2. Column was named `is_*_session` following the library's method name
3. No validation that the column values match the expected use case

---

## Impact Assessment

### For Forex Tick Data Analysis

**Use Case 1**: Identify ticks during NYSE trading hours
```sql
-- Current (WRONG):
SELECT * FROM ohlc_1m
WHERE is_nyse_session = 1;  -- Returns ALL minutes on trading days

-- What users expect:
SELECT * FROM ohlc_1m
WHERE ny_session = 'NY_Session';  -- Returns only 9:30 AM - 4:00 PM ET
```

**Use Case 2**: Detect overlap of NYSE and LSE sessions
```sql
-- Current (WRONG):
SELECT * FROM ohlc_1m
WHERE is_nyse_session = 1 AND is_lse_session = 1;  -- Returns ANY time on days both are open

-- What users expect:
SELECT * FROM ohlc_1m
WHERE ny_session = 'NY_Session' AND london_session = 'London_Session';  -- Returns 9:30 AM - 11:00 AM ET (4-hour overlap)
```

**Impact**: Queries using `is_*_session` columns will include ticks from outside trading hours, leading to **incorrect analysis results**.

---

## Proposed Solutions

### Option A: Fix Column Values (Breaking Change)

**Change**: Update `session_detector.py` to check actual trading hours, not just trading days.

**Implementation**:

```python
# exchanges.py - Add trading hours to ExchangeConfig
@dataclass(frozen=True)
class ExchangeConfig:
    code: str
    name: str
    currency: str
    timezone: str
    country: str
    open_hour: int  # NEW: Trading start hour (local time)
    open_minute: int  # NEW: Trading start minute
    close_hour: int  # NEW: Trading close hour (local time)
    close_minute: int = 0  # NEW: Trading close minute

EXCHANGES = {
    "nyse": ExchangeConfig(
        code="XNYS",
        name="New York Stock Exchange",
        currency="USD",
        timezone="America/New_York",
        country="United States",
        open_hour=9,
        open_minute=30,
        close_hour=16,
        close_minute=0,
    ),
    "lse": ExchangeConfig(
        code="XLON",
        name="London Stock Exchange",
        currency="GBP",
        timezone="Europe/London",
        country="United Kingdom",
        open_hour=8,
        open_minute=0,
        close_hour=16,
        close_minute=30,
    ),
    # ... add trading hours for all 10 exchanges
}

# session_detector.py - Update detection logic
for exchange_name, exchange_config in EXCHANGES.items():
    col_name = f"is_{exchange_name}_session"

    def is_trading_hour(ts, exchange_config=exchange_config, calendar=self.calendars[exchange_name]):
        # Check if trading day
        if not calendar.is_session(ts.date()):
            return 0

        # Convert to exchange timezone
        local_time = ts.tz_convert(exchange_config.timezone)
        hour = local_time.hour
        minute = local_time.minute

        # Check if within trading hours
        open_minutes = exchange_config.open_hour * 60 + exchange_config.open_minute
        close_minutes = exchange_config.close_hour * 60 + exchange_config.close_minute
        current_minutes = hour * 60 + minute

        return int(open_minutes <= current_minutes < close_minutes)

    dates_df[col_name] = dates_df["ts"].apply(is_trading_hour)
```

**Pros**:
- ✓ Columns accurately reflect trading hours
- ✓ Consistent with `ny_session` / `london_session` semantics
- ✓ Enables correct intraday analysis
- ✓ Single source of truth for trading hours (exchanges.py)

**Cons**:
- ✗ Breaking change (requires database regeneration)
- ✗ Need to research and add trading hours for all 10 exchanges
- ✗ Slightly more complex logic (timezone conversion + hour checks)

---

### Option B: Rename Columns (Breaking Change)

**Change**: Rename columns to accurately reflect what they check.

**Rename**:
- `is_nyse_session` → `is_nyse_trading_day`
- `is_lse_session` → `is_lse_trading_day`
- ... (all 10 exchanges)

**Update Documentation**:
- Schema comments: "1 if exchange trading day (not weekend, not holiday), 0 otherwise"
- Remove mention of "session" to avoid confusion

**Pros**:
- ✓ Accurate naming matches implementation
- ✓ No logic changes needed
- ✓ Clear distinction from `ny_session` / `london_session`

**Cons**:
- ✗ Breaking change (column renames)
- ✗ Less useful for intraday analysis
- ✗ Users need `ny_session` / `london_session` for actual session detection

---

### Option C: Add New Columns (Non-Breaking)

**Change**: Keep existing columns, add new hour-based session columns.

**Add**:
- `is_nyse_trading_day` (current `is_nyse_session` behavior)
- `is_nyse_trading_hour` (new, checks actual trading hours)
- ... (all 10 exchanges)

**Deprecate**: Mark `is_*_session` as deprecated in documentation.

**Pros**:
- ✓ Non-breaking (existing queries still work)
- ✓ Provides both day-level and hour-level flags
- ✓ Clear naming distinction

**Cons**:
- ✗ Schema grows to 50 columns (30 → 50)
- ✗ Potential confusion with 3 types of columns (day/hour/legacy)
- ✗ Maintenance burden (2 sets of columns to update)

---

### Option D: Remove Columns (Breaking Change)

**Change**: Remove `is_*_session` columns entirely, rely on existing `ny_session` / `london_session`.

**Rationale**:
- Already have correct session detection for NYSE and LSE
- Other 8 exchanges not widely used for forex tick analysis
- Simpler schema (30 → 20 columns)

**For users needing other exchanges**:
- Use `ny_hour` + manual hour checks in SQL
- Or extend `ny_session` pattern to other exchanges

**Pros**:
- ✓ Removes misleading columns
- ✓ Simpler schema
- ✓ Reduces maintenance burden

**Cons**:
- ✗ Breaking change
- ✗ Loses convenience of pre-computed flags
- ✗ May need to add back later if users request

---

## Recommendation

**Recommended Option**: **Option A** (Fix Column Values)

**Rationale**:
1. **Correctness**: Column values should match their semantic meaning
2. **Consistency**: Aligns with existing `ny_session` / `london_session` behavior
3. **Future-proof**: Enables proper intraday analysis across all 10 exchanges
4. **Single Source of Truth**: Trading hours defined once in `exchanges.py`, propagate everywhere

**Breaking Change Justification**:
- Current columns are **broken** - they don't do what users expect
- Better to fix now (v1.5.0 → v1.6.0) than carry incorrect data forward
- Clear migration path: regenerate databases with `processor.update_data()`

---

## Implementation Plan (Option A)

### Phase 1: Update Exchange Registry

**File**: `src/exness_data_preprocess/exchanges.py`

**Changes**:
1. Add trading hours fields to `ExchangeConfig`
2. Research and add trading hours for all 10 exchanges
3. Document trading hours sources (exchange websites, `exchange_calendars` docs)

**Deliverable**: Updated `EXCHANGES` dict with trading hours

---

### Phase 2: Update Session Detector

**File**: `src/exness_data_preprocess/session_detector.py`

**Changes**:
1. Update `detect_sessions_and_holidays()` to check trading hours
2. Add timezone conversion logic
3. Add hour/minute range checks
4. Update docstrings and comments

**Deliverable**: Corrected session detection logic

---

### Phase 3: Update Schema & Documentation

**Files**:
- `src/exness_data_preprocess/schema.py`
- `docs/DATABASE_SCHEMA.md`
- `CLAUDE.md`

**Changes**:
1. Update column comments to reflect hour-based detection
2. Update schema version to v1.6.0
3. Update documentation examples
4. Add migration notes

**Deliverable**: Updated documentation

---

### Phase 4: Testing & Validation

**Tests**:
1. Unit test for `SessionDetector.detect_sessions_and_holidays()`
   - Test trading hours for all 10 exchanges
   - Test DST transitions (NYSE: EST/EDT, LSE: GMT/BST)
   - Test edge cases (market open minute, market close minute)
2. Integration test with real EURUSD data
   - Verify `is_nyse_session` matches `ny_session='NY_Session'`
   - Verify `is_lse_session` matches `london_session='London_Session'`
   - Verify other 8 exchanges return 0 outside trading hours

**Deliverable**: Passing test suite

---

### Phase 5: Database Regeneration

**Process**:
1. Run `processor.update_data(pair)` to regenerate OHLC with corrected session flags
2. Verify column values with spot checks
3. Update version tracking

**Deliverable**: Databases regenerated with v1.6.0 schema

---

## Alternative: User Decision Required

If fixing columns is not desired, need to decide:

**Question 1**: Should columns check trading HOURS or trading DAYS?
- If HOURS: Proceed with Option A
- If DAYS: Proceed with Option B (rename to `is_*_trading_day`)

**Question 2**: Are 10 exchange session columns necessary?
- If YES: Keep all 10, fix them
- If NO: Consider Option D (remove, keep only NYSE/LSE via `ny_session`/`london_session`)

**Question 3**: Is breaking change acceptable?
- If YES: Proceed with Option A, B, or D
- If NO: Proceed with Option C (add new columns, deprecate old)

---

## Trading Hours Reference (for Option A)

### NYSE (XNYS)
- **Hours**: 9:30 AM - 4:00 PM ET
- **Source**: NYSE official website
- **DST**: EST (winter) / EDT (summer)

### LSE (XLON)
- **Hours**: 8:00 AM - 4:30 PM GMT
- **Source**: LSE official website
- **DST**: GMT (winter) / BST (summer)

### SIX Swiss (XSWX)
- **Hours**: 9:00 AM - 5:30 PM CET
- **Source**: SIX Swiss Exchange

### Frankfurt (XFRA)
- **Hours**: 9:00 AM - 5:30 PM CET
- **Source**: Deutsche Börse

### Toronto (XTSE)
- **Hours**: 9:30 AM - 4:00 PM ET
- **Source**: TSX official website

### New Zealand (XNZE)
- **Hours**: 10:00 AM - 4:45 PM NZST
- **Source**: NZX official website

### Tokyo (XTKS)
- **Hours**: 9:00 AM - 3:00 PM JST (with 11:30 AM - 12:30 PM lunch break)
- **Source**: JPX official website
- **Note**: Has lunch break (need special handling)

### Australia (XASX)
- **Hours**: 10:00 AM - 4:00 PM AEST
- **Source**: ASX official website

### Hong Kong (XHKG)
- **Hours**: 9:30 AM - 4:00 PM HKT (with 12:00 PM - 1:00 PM lunch break)
- **Source**: HKEX official website
- **Note**: Has lunch break

### Singapore (XSES)
- **Hours**: 9:00 AM - 5:00 PM SGT
- **Source**: SGX official website

**Note**: Tokyo and Hong Kong have lunch breaks where trading is suspended. Need to handle this in logic.

---

## Next Steps

1. **User Decision**: Choose Option A, B, C, or D
2. **If Option A**: Research and verify all 10 exchange trading hours
3. **Implementation**: Follow phased plan above
4. **Testing**: Comprehensive validation before database regeneration
5. **Documentation**: Update all docs to reflect changes
6. **Migration**: Regenerate databases, notify users of breaking change

---

**Status**: ⚠️ Awaiting user decision on preferred option

**Test Script**: `/tmp/test_session_logic.py` (demonstrates current vs expected behavior)

**References**:
- `/Users/terryli/eon/exness-data-preprocess/src/exness_data_preprocess/session_detector.py:119`
- `/Users/terryli/eon/exness-data-preprocess/src/exness_data_preprocess/schema.py:304-311`
- `/Users/terryli/eon/exness-data-preprocess/src/exness_data_preprocess/ohlc_generator.py:123-133`
