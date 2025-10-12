# Hurdle Model Analysis: Raw_Spread Zero-Inflated Distribution

**Analysis Type**: Two-part hurdle model with modal-band-excluded positive tail estimation
**Variant**: Raw_Spread (EURUSD_Raw_Spread)
**Period**: July 2025 (1 month sample)
**Total Observations**: 1,308,306 ticks

---

## Executive Summary

**Key Finding**: Raw_Spread exhibits extreme zero-inflation (98.3%), resulting in Signal Quality Score of 0.84—**32× inferior** to Standard (EURUSD).

### Hurdle Model Decomposition

| Component | Result | Interpretation |
|-----------|--------|----------------|
| **Part 1: Hurdle** | | |
| P(spread = 0) | 98.3% | Extreme zero-inflation |
| P(spread > 0) | 1.7% | Hurdle crossed rarely |
| **Part 2: Positive Tail** | | |
| Positive tail observations | 22,278 ticks | 1.7% of total |
| Mode (of positives) | 2.17p | 15.6% of positive tail |
| Modal % (of total) | 0.27% | Tiny modal mass |
| **Part 3: Final Signal** | | |
| Non-modal varying ticks | 18,808 | **1.4% of total** |
| Mode-truncated CV | 58.6% | Moderate variability |
| **Signal Quality Score** | **0.84** | Very low |

---

## 1. Hurdle Component: Zero vs Non-Zero

### Zero-Inflation Analysis

**Zero Mass**:
- Zero spreads: 1,286,028 ticks
- Zero proportion: **98.3%**
- Interpretation: Deterministic zero-spread regime

**Positive Mass**:
- Non-zero spreads: 22,278 ticks
- Positive proportion: **1.7%**
- Interpretation: Rare spread excursions

### Hurdle Probability

```
π = P(spread > 0) = 22,278 / 1,308,306 = 1.7%

Implication: 98.3% of observations are deterministic zeros
```

### Microstructure Interpretation

**Artificial Zero Construction**:
- 98.3% zero-spread likely post-processed/synthetic
- Does not reflect true market microstructure
- Masks actual bid-ask spread dynamics

**Rare Positive Spreads**:
- 1.7% hurdle crossing suggests exceptional events only
- Positive tail does not represent normal market conditions
- Unsuitable for typical spread modeling

---

## 2. Positive Tail Analysis (Conditional Distribution)

### Conditional Distribution: f(spread | spread > 0)

**Given spread > 0** (n = 22,278 observations):

**Modal Behavior**:
- Mode value: 2.17 pips
- Modal frequency: 3,470 ticks
- Modal % (of positive tail): 15.6%
- Modal % (of total): 0.27%

**Non-Modal Tail**:
- Observations: 18,808 ticks
- Coverage (of positive tail): 84.4%
- Coverage (of total): **1.4%**
- Mean (mode-truncated): 3.12 pips
- Std Dev (mode-truncated): 1.83 pips
- **CV (mode-truncated): 58.6%**

### Mode-Truncated CV (Positive Tail)

```
CV_truncated = (σ / μ) × 100%
             = (1.83 / 3.12) × 100%
             = 58.6%
```

**Interpretation**: Moderate variance in conditional distribution, but...

---

## 3. Signal Quality Score (Hurdle Model)

### Calculation

```
SQ_hurdle = P(spread > 0 AND non-modal) × CV_truncated
          = 1.4% × 58.6%
          = 0.84
```

### Breakdown

| Component | Value | Contribution |
|-----------|-------|--------------|
| Zero-inflation loss | -98.3% | Removes deterministic mass |
| Positive tail | 1.7% | Survives hurdle |
| Modal loss (of positives) | -15.6% | Removes positive mode |
| **Final varying mass** | **1.4%** | Effective signal region |
| Mode-truncated CV | 58.6% | Moderate variance |
| **Signal Quality** | **0.84** | Very poor |

---

## 4. Comparison vs Standard (EURUSD)

### Head-to-Head Comparison

| Metric | Standard | Raw_Spread | Winner | Ratio |
|--------|----------|------------|--------|-------|
| **Deterministic %** | 0% zeros | **98.3% zeros** | Standard | - |
| **Varying mass %** | 22.5% | **1.4%** | **Standard** | **16×** |
| **Mode-truncated CV** | 118.1% | 58.6% | **Standard** | **2×** |
| **Signal Quality Score** | **26.57** | **0.84** | **Standard** | **32×** |

### Key Insights

**Standard Advantages**:
1. **Zero-free distribution**: No artificial zero-inflation
2. **16× more varying observations**: 22.5% vs 1.4%
3. **2× higher mode-truncated CV**: 118% vs 59%
4. **32× higher Signal Quality**: 26.57 vs 0.84

**Raw_Spread Limitations**:
1. **Extreme zero-inflation**: 98.3% deterministic zeros
2. **Minimal varying mass**: Only 1.4% provides signal
3. **Artificial construction**: Zeros likely post-processed
4. **Unsuitable for ML**: Insufficient variance for learning

---

## 5. Distribution Statistics

### Full Distribution (Including Zeros)

| Percentile | Value (pips) | Interpretation |
|------------|--------------|----------------|
| P1 - P98 | 0.00 | Zero-inflated mass |
| P98.3 | 0.00 | Hurdle threshold |
| P99 | 0.60 | First positive spreads |
| P99.5 | 3.00 | Positive tail begins |
| P99.9 | 7.70 | Extreme spreads |
| Max | 9.10 | Maximum observed |

### Positive Tail Only (Conditional on spread > 0)

| Percentile | Value (pips) | Interpretation |
|------------|--------------|----------------|
| P1 | 0.60 | Minimum positive spread |
| P10 | 0.60 | 90% above (conditional) |
| P25 | 0.60 | Q1 |
| **P50** | **3.00** | Median of positives |
| P75 | 5.70 | Q3 |
| P90 | 5.70 | 10% exceed |
| **P99** | **7.70** | Top 1% outliers |

**IQR (P25-P75)**: 2.20 pips (wider spread in sparse positive tail)
**Range**: 8.50 pips (0.60p → 9.10p)

---

## 6. Statistical Validity

### Hurdle Model Assumptions

**Assumption 1: Structural Zero-Inflation** ✅
- 98.3% zeros exceed typical market behavior
- Confirms structural (deterministic) zero mechanism

**Assumption 2: Positive Tail Informativeness** ⚠️
- Only 22,278 observations in positive tail
- Borderline sufficient for robust CV (n > 1000 threshold met)
- Mode-truncation further reduces to 18,808 obs

**Assumption 3: Independence** ✅
- Zero vs non-zero appears structurally independent
- Positive tail distribution distinct from zero mass

### Validity Checks

| Check | Threshold | Raw_Spread | Status |
|-------|-----------|------------|--------|
| Zero inflation | > 90% | 98.3% | ✅ Confirmed |
| Positive tail n | > 1000 | 22,278 | ✅ Sufficient |
| Mode-truncated n | > 1000 | 18,808 | ✅ Sufficient |
| Mode ≠ boundary | Mode > 0 | 2.17p | ✅ Valid |

---

## 7. Microstructure Implications

### Zero-Spread Regime (98.3%)

**Characteristics**:
- Deterministic zero spread
- No bid-ask variability
- Likely synthetic/post-processed

**Market Interpretation**:
- Not representative of true market microstructure
- Artificial liquidity (zero transaction cost)
- Unsuitable for realistic spread modeling

### Positive Spread Regime (1.7%)

**Characteristics**:
- Mean: 3.12 pips (mode-truncated)
- Std: 1.83 pips
- CV: 58.6%
- Range: 0.60p → 9.10p

**Market Interpretation**:
- Exceptional events only
- Higher spreads than Standard (mean 0.95p)
- Sparse observations limit modeling utility

---

## 8. Recommendations

### Avoid Raw_Spread for ML ❌

**Critical Limitations**:
1. **98.3% zero-inflation** masks true spread dynamics
2. **Only 1.4% varying observations** insufficient for ML training
3. **Artificial zero construction** not representative of market
4. **32× lower Signal Quality** than Standard

**Unsuitable Use Cases**:
- ❌ ML feature engineering
- ❌ Regime detection
- ❌ Spread forecasting
- ❌ Market microstructure analysis

### Alternative: Use Standard (EURUSD) ✅

**Standard Advantages**:
- ✅ No zero-inflation (authentic spreads)
- ✅ 22.5% varying observations (16× more signal)
- ✅ 118% mode-truncated CV (2× higher variance)
- ✅ 32× higher Signal Quality Score

---

## 9. Theoretical Context

### Zero-Inflated Models in Finance

**Typical Applications**:
- Trade frequency (zeros = no trades)
- Dividend payments (zeros = no dividend)
- Default events (zeros = no default)

**Raw_Spread Anomaly**:
- Zeros represent "zero spread" (deterministic pricing)
- Unlike typical count data with structural zeros
- Likely artificial construction, not natural zero-inflation

### Hurdle Model Alternatives

**If using Raw_Spread is unavoidable**:
1. **Model zeros separately**: Binary classification (zero vs non-zero)
2. **Conditional modeling**: Analyze positive tail independently
3. **Synthetic data augmentation**: Generate realistic spreads for zero regime

**Better Alternative**: Use Standard variant with authentic spread dynamics

---

## Data Files

**Hurdle Model Results**: [../data/hurdle-model-results/rawspread_vs_standard_results.csv](../data/hurdle-model-results/rawspread_vs_standard_results.csv)

**Visualizations**:
- [../visualizations/hurdle-model/hurdle_decomposition.png](../visualizations/hurdle-model/hurdle_decomposition.png)

---

## Conclusion

Raw_Spread's extreme zero-inflation (98.3%) renders it unsuitable for microstructure analysis. Hurdle model decomposition reveals:
- Only 1.4% varying observations (after excluding zeros and mode)
- Mode-truncated CV of 58.6% (lower than Standard's 118%)
- **Signal Quality Score of 0.84 (32× inferior to Standard)**

**Formal Recommendation**: **Reject Raw_Spread; use Standard (EURUSD) for all ML and microstructure applications.**
