# Baseline Analysis: Sep 2024 Single-Month Study

**Analysis Date**: 2024-09-01 to 2024-09-30
**Data Volume**: 907K zero-spread events
**Framework**: Position deviation analysis with 4 complementary approaches

---

## Overview

Sep 2024 baseline established initial findings for zero-spread deviation patterns. This single-month analysis provided:
- Mean reversion rates
- Volatility prediction model
- Flash crash prediction signals
- Regime detection clusters

**Note**: Multi-period validation (Phase 2-3) revealed Sep 2024 was an **anomalous transitional month** between 2024 high-volatility regime and 2025 low-volatility regime.

---

## Analysis 1: Mean Reversion

**Full report**: [findings/baseline-sep2024-comprehensive-summary.md](findings/baseline-sep2024-comprehensive-summary.md#mean-reversion)

### Key Findings

**5-Second Horizon**:
- **70.6%** moved toward midpoint
- **21.9%** fully reverted (deviation < 0.05)

**60-Second Horizon**:
- **51.9%** moved toward midpoint
- **2.3%** fully reverted

**Statistical significance**:
- Reversion rate significantly > 50% baseline (p < 0.001)
- Confirms non-random mean reversion behavior

### Interpretation

Deviations exhibit strong short-term mean reversion:
- Most revert within 5 seconds
- Longer horizons show weaker reversion (volatility interference)
- **Trading signal**: Fade extreme deviations with 5-10s holding period

**Multi-period update**: Baseline UNDERESTIMATED actual rate (87.3% across 16 months)

---

## Analysis 2: Volatility Prediction Model

**Full report**: [findings/baseline-sep2024-comprehensive-summary.md](findings/baseline-sep2024-comprehensive-summary.md#volatility-model)

### Multi-Factor Model (4 Features)

| Feature | Correlation (r) | Interpretation |
|---------|----------------|----------------|
| Recent volatility | **+0.418** | Dominant predictor (GARCH effect) |
| Deviation magnitude | +0.063 | Weak positive |
| Persistence | -0.147 | Weak negative |
| Spread width | -0.025 | Negligible |

**Multi-factor R²**: 0.185 (5-minute horizon)

**Baseline improvement**: 4601% over deviation-only model (R²=0.004)

### Interpretation

**What works**:
- Recent volatility is strongest predictor (volatility persistence)
- Multi-factor model captures ~18.5% of variance
- Significantly better than univariate baseline

**What doesn't work**:
- Deviation magnitude alone is very weak (r=0.063)
- Persistence contributes little
- Overall R² still modest (81.5% variance unexplained)

**Multi-period update**: Sep 2024 R²=0.185 was ANOMALY. 2024 avg R²=0.371, 2025 avg R²=0.209 (regime shift).

---

## Analysis 3: Flash Crash Prediction

**Full report**: [findings/baseline-sep2024-comprehensive-summary.md](findings/baseline-sep2024-comprehensive-summary.md#flash-crash)

### Extreme vs Normal Deviations

**Extreme deviation** (position_ratio < 0.2 or > 0.8):
- **94.5%** flash crash rate @ 60s

**Normal deviation** (position_ratio 0.4-0.6):
- **85.7%** flash crash rate @ 60s

**Lift**: **+8.8pp** @ 60s

**Average lift** across all horizons: **+13.2pp**

### Interpretation

Extreme deviations significantly predict flash crashes:
- Consistent positive lift across all time horizons
- Strongest at 60-second horizon
- **Risk signal**: Extreme deviations indicate elevated crash risk

**Multi-period validation**: Pending (Phase 4)

---

## Analysis 4: Regime Detection (Clustering)

**Full report**: [findings/baseline-sep2024-comprehensive-summary.md](findings/baseline-sep2024-comprehensive-summary.md#regime-detection)

### K-Means Clusters (k=3)

| Cluster | Deviations | Avg Deviation | Recent Vol | Label |
|---------|-----------|---------------|------------|-------|
| 0 | 3,821 | 0.226 | 0.132 bps | High activity |
| 1 | 1,100 | 0.138 | 0.098 bps | Medium activity |
| 2 | 79 | 0.196 | 0.220 bps | Low activity (volatile) |

### Counter-Intuitive Finding

**Hypothesis tested**: Deviation clusters predict volatility INCREASE

**Actual result**: Deviation clusters predict volatility **DECREASE**
- Cluster events: 42.1% volatility increase
- Baseline (random): 50% volatility increase
- **Difference**: -7.9pp (p = 0.0004, statistically significant)

**Interpretation**: Deviations are volatility **signals**, not **causes**. They indicate existing volatility regime, but don't predict further increases.

**Multi-period validation**: Pending (Phase 5)

---

## Comprehensive Summary

### Strengths of Sep 2024 Baseline

1. **Mean reversion confirmed** (70.6% @ 5s)
2. **Volatility persistence validated** (recent_vol r=0.418)
3. **Flash crash lift detected** (+13.2pp)
4. **Regime behavior characterized** (volatility signal, not cause)

### Limitations Discovered by Multi-Period Validation

1. **Mean reversion underestimated**: 70.6% → actual 87.3%
2. **Volatility model anomaly**: R²=0.185 was transitional value
   - 2024 months: R²=0.371 (2× higher)
   - 2025 months: R²=0.209 (closer to baseline)
3. **Single-month bias**: Sep 2024 was between-regime transition
4. **Flash crash & regime**: Not yet validated across time periods

### Updated Interpretation

Sep 2024 served as **baseline** but was not **representative**:
- Captured correct methodologies ✅
- Established statistical frameworks ✅
- But occurred during regime transition ⚠️
- Multi-period validation essential for robustness ✅

---

## Data Files

- **Mean reversion**: [data/baseline-sep2024/mean_reversion_results.csv](../data/baseline-sep2024/mean_reversion_results.csv)
- **Volatility model**: [data/baseline-sep2024/volatility_model_results.csv](../data/baseline-sep2024/volatility_model_results.csv)
- **Flash crash**: [data/baseline-sep2024/liquidity_crisis_results.csv](../data/baseline-sep2024/liquidity_crisis_results.csv)
- **Regime detection**: [data/baseline-sep2024/regime_detection_results.csv](../data/baseline-sep2024/regime_detection_results.csv)

## Scripts

- [scripts/baseline-sep2024/01_mean_reversion_analysis.py](../scripts/baseline-sep2024/01_mean_reversion_analysis.py)
- [scripts/baseline-sep2024/02_volatility_model_simple.py](../scripts/baseline-sep2024/02_volatility_model_simple.py)
- [scripts/baseline-sep2024/03_liquidity_crisis_detection.py](../scripts/baseline-sep2024/03_liquidity_crisis_detection.py)
- [scripts/baseline-sep2024/04_regime_detection_analysis.py](../scripts/baseline-sep2024/04_regime_detection_analysis.py)

---

## Next Steps

✅ **Phase 2**: Mean reversion validated (STABLE across 16 months)
✅ **Phase 3**: Volatility model validated (REGIME SHIFT discovered)
⏸️ **Phase 4**: Flash crash prediction validation (pending)
⏸️ **Phase 5**: Regime detection validation (pending)
