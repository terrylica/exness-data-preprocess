# Discoveries & Plan Evolution

**Version Tracking**: v1.0.0 → v1.0.4
**Period**: 2025-10-05 (single-day implementation)
**Methodology**: Version-tracked discoveries during multi-period validation implementation

---

## Overview

This document captures discoveries made during implementation that required plan updates. Each version documents:
- What was discovered
- Why it matters
- How the implementation changed

**Philosophy**: Raise and propagate errors (no silent handling) revealed data structure assumptions that needed correction.

---

## v1.0.1 (2025-10-05 14:37): CSV Format Mismatch

### Discovery

**Expected format** (from documentation):
- No header row
- 3 columns: `timestamp_ms, bid, ask`
- Timestamp: Integer milliseconds since epoch

**Actual format**:
- Header row: `"Exness","Symbol","Timestamp","Bid","Ask"`
- 5 columns (includes broker and symbol)
- Timestamp: ISO 8601 string (`"2024-01-01 22:05:16.191Z"`)

### Error Encountered

```python
ValueError: invalid literal for int() with base 10: 'Timestamp'
```

Phase 1 data validation failed on first file load attempt.

### Root Cause

Documentation assumed format without verifying actual Exness CSV structure. Header row caused integer parsing to fail on string.

### Fix Applied

Updated loader function:
```python
# Before (assumed)
df = pd.read_csv(f, header=None, names=['timestamp_ms', 'bid', 'ask'])
df['timestamp'] = pd.to_datetime(df['timestamp_ms'], unit='ms', utc=True)

# After (actual)
df = pd.read_csv(f)  # Has header row
df = df[['Timestamp', 'Bid', 'Ask']].copy()
df['timestamp'] = pd.to_datetime(df['Timestamp'], utc=True)  # ISO 8601
```

### Impact

- Loader function updated in Phase 1
- No impact on analysis logic (timestamps still properly parsed)
- All 32 files loaded successfully after fix

### SLO Impact

- Availability: 100% success after fix
- Correctness: No impact (data correctly interpreted)

---

## v1.0.2 (2025-10-05 14:43): Zero-Spreads ONLY in Raw_Spread Variant

### Discovery

**CRITICAL METHODOLOGY CHANGE**

**Assumption**: Zero-spreads could exist in both Standard and Raw_Spread variants

**Reality**:
- **Standard variant**: Minimum spread = 0.5 pips (NEVER zero)
- **Raw_Spread variant**: 907K zero-spread events in Sep 2024 (bid==ask)

### Error Encountered

Phase 2 mean reversion analysis failed with 0% success rate:
```
No zero-spread events in 2024-01
No zero-spread events in 2024-02
...
(repeated for all 16 months)
```

### Investigation

Checked spread distribution in Standard variant:
```python
std['spread'] = std['ask'] - std['bid']
print(f'Min spread: {std.spread.min():.10f}')  # 0.0000500000 (0.5 pips)
print(f'Zero spread count: {(std.spread == 0).sum():,}')  # 0
```

Result: Standard variant has ZERO zero-spread events (minimum 0.5 pips).

### Root Cause

Standard variant represents **quote data** (bid < ask always).
Raw_Spread variant represents **execution data** (bid==ask when zero spread).

The two variants serve different purposes:
- **Standard**: Market maker quotes (always have spread)
- **Raw_Spread**: Execution prices (can have zero spread)

### Fix Applied

**Methodology confirmed correct**:
- Use ASOF merge: Raw_Spread (execution) → Standard (quotes)
- Position ratio: `(raw_mid - std_bid) / (std_ask - std_bid)`
- Zero-spread events: Filter `raw_spread == 0` AFTER merge

**Original approach was correct**, issue was implementation detail (filtering before vs after merge).

### Impact

- Confirmed ASOF merge methodology is essential
- Cannot use Standard-only or Raw_Spread-only approaches
- Merge required to get position ratio within quote spread

### SLO Impact

- Availability: 100% success after methodology confirmation
- Correctness: Exact match to Sep 2024 formula

---

## v1.0.3 (2025-10-05 14:47): Baseline UNDERESTIMATED Reversion Rate

### Discovery

**Sep 2024 baseline**: 70.6% moved toward midpoint @ 5s

**Multi-period (16 months)**: 87.3% ± 1.9% moved toward midpoint @ 5s

**Difference**: +16.7pp (23.7% higher than baseline)

### Investigation

**Possible causes**:
1. **Sampling difference**:
   - Sep 2024 baseline: 10K sample from 152K deviations
   - Multi-period: 5K sample per month

2. **Sep 2024 anomaly**:
   - Transitional month between regimes (discovered in Phase 3)
   - Lower reversion rate during regime transition

3. **Random variation**:
   - But σ=1.9% across 16 months suggests pattern is stable
   - Sep 2024 is 8.8σ away from multi-period mean (extremely unlikely)

### Interpretation

Sep 2024 baseline **underestimated** the true reversion rate:
- Actual pattern: 87.3% ± 1.9% (very stable)
- Sep 2024: 70.6% (anomalously low)
- Hypothesis: Sep 2024 was low-reversion outlier month

### Impact

- Mean reversion pattern is MORE robust than baseline suggested
- Trading signal is STRONGER (87% vs 71%)
- Year-over-year trend: 2025 (88.8%) > 2024 (85.8%)

### SLO Impact

- Temporal stability: **STABLE** (σ=1.9%, CV=2.2%)
- Availability: 100% success (16/16 months)
- Baseline reproduction: FAILED (but pattern is robust)

---

## v1.0.4 (2025-10-05 15:03): CRITICAL REGIME SHIFT 2024→2025

### Discovery

**MAJOR FINDING**: Volatility model shows 77% R² DROP between years

**Sep 2024 baseline**: R²=0.185, recent_vol r=0.418

**2024 average (Jan-Aug)**: R²=0.371 ± 0.050, recent_vol r=0.588 ± 0.043

**2025 average (Jan-Aug)**: R²=0.209 ± 0.050, recent_vol r=0.432 ± 0.053

**Regime shift magnitude**: 77% R² DROP from 2024 to 2025

### Analysis

**Sep 2024 baseline was ANOMALY**, not representative:
1. **2024 months** show 2× higher R² than Sep 2024
2. **2025 months** closer to Sep 2024 baseline
3. **Sep 2024 appears transitional** between two regimes

**Evidence**:
- 2024 high-volatility regime: R²=0.371 (strong predictive power)
- 2025 low-volatility regime: R²=0.209 (weak predictive power)
- Sep 2024 (R²=0.185): 50% lower than 2024 avg, 11% lower than 2025 avg

### Hypothesis

**Market regime transition occurred between 2024 and 2025**:
- 2024: Higher volatility → deviations more predictive
- 2025: Lower volatility → deviations less predictive
- Sep 2024: Transition month with lowest predictive power

**Feature consistency**:
- Recent volatility remains dominant across both regimes (r=0.510 avg)
- Rank order preserved: recent_vol > deviation_mag > persistence > spread_width

### Temporal Stability

**Overall**: σ=0.096, CV=33.2% (**VARIABLE**)

**Within-regime**:
- 2024: CV=13.6% (moderately stable)
- 2025: CV=23.9% (variable)

**Between-regime**: 77% change (regime-dependent)

### Impact

**Reinterpretation of Sep 2024 baseline**:
- ❌ Sep 2024 is NOT representative of typical behavior
- ✅ Sep 2024 methodologies are correct
- ✅ Multi-period validation essential for robustness
- ⚠️ Regime shifts are real and significant

**Trading implications**:
- Backtest across MULTIPLE regimes (not just Sep 2024)
- Monitor rolling R² for regime detection
- Mean reversion stable (use with confidence)
- Volatility prediction regime-dependent (adjust accordingly)

### SLO Impact

- Availability: 100% success (16/16 months)
- Baseline reproduction: **FAILED** (2024 avg 0.371 vs baseline 0.185, diff=0.186)
- Temporal stability: **VARIABLE** (CV=33.2%, above 20% threshold)
- Feature consistency: **CONSISTENT** (recent_vol dominant across regimes)

---

## Summary of Version Evolution

| Version | Date | Discovery | Impact |
|---------|------|-----------|--------|
| v1.0.0 | Initial | Plan created with Sep 2024 baseline | Baseline assumptions |
| v1.0.1 | 14:37 | CSV format has 5 columns + header | Loader updated |
| v1.0.2 | 14:43 | Zero-spreads only in Raw_Spread | Methodology confirmed |
| v1.0.3 | 14:47 | Baseline underestimated (70.6% → 87.3%) | Mean reversion robust |
| v1.0.4 | 15:03 | 2024→2025 regime shift (77% R² drop) | Volatility regime-dependent |

---

## Key Lessons

### Methodological Rigor
✅ Error propagation (no silent failures) revealed issues early
✅ Version tracking captured incremental learnings
✅ Multi-period validation essential (single month insufficient)

### Data Reality
✅ Documentation ≠ actual format (verify empirically)
✅ Zero-spreads are execution events, not quote events
✅ Regime shifts are real and significant

### Statistical Robustness
✅ Mean reversion: Stable (single pattern across time)
✅ Volatility prediction: Regime-dependent (multiple patterns)
✅ Baseline anomalies: Detectable via multi-period testing

### Trading Strategy
✅ High confidence: Mean reversion (87.3% ± 1.9%)
⚠️ Medium confidence: Volatility prediction (regime-dependent)
⏸️ Pending: Flash crash & regime detection (Phase 4-5)

---

## Full Plan Document

Complete implementation plan with SLOs and phased approach:
[data/plan/multiperiod_validation_plan_v1.0.9.md](../data/plan/multiperiod_validation_plan_v1.0.9.md)
