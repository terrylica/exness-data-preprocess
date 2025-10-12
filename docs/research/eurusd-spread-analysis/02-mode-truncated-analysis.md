# Mode-Truncated Analysis: Standard, Mini, Cent

**Analysis Type**: Modal-band-excluded variance estimation
**Variants**: Standard (EURUSD), Mini (EURUSDm), Cent (EURUSDc)
**Period**: July-September 2025
**Total Observations**: 11.1M ticks

---

## Executive Summary

**Key Finding**: Standard (EURUSD) achieves Signal Quality Score of 26.57, representing **34× superior** microstructure signal compared to Mini/Cent variants.

### Comparative Results

| Variant | Total Ticks | Modal % | Mode Value | Non-Modal % | Mode-Truncated CV | **Signal Score** |
|---------|-------------|---------|------------|-------------|-------------------|------------------|
| **Standard** | 3,911,194 | 77.5% | 0.56p | **22.5%** | **118.1%** | **26.57** ✅ |
| Mini | 3,594,391 | 98.4% | 0.89p | 1.6% | 48.9% | 0.78 |
| Cent | 3,594,391 | 98.4% | 0.89p | 1.6% | 48.9% | 0.78 |

---

## 1. Standard (EURUSD): Low Modal Concentration Regime

### Distribution Characteristics

**Modal Behavior**:
- Mode value: 0.56 pips (0.565p)
- Modal frequency: 3,029,357 ticks
- Modal coverage: **77.5%**

**Non-Modal Tail** (the "signal region"):
- Observations: 881,837 ticks
- Coverage: **22.5% of total**
- Mean (mode-truncated): 0.95 pips
- Std Dev (mode-truncated): 1.12 pips
- **CV (mode-truncated): 118.1%**

### Signal Quality Score

```
SQ = P(non-modal) × CV_truncated
   = 22.5% × 118.1%
   = 26.57
```

### Microstructure Interpretation

**Regime Dynamics**:
- **Dominant tight spread regime** at 0.56 pips (77.5% of time)
- **Frequent regime excursions**: 22.5% of observations show spread variability
- **Extreme CV (118%)**: Non-modal spreads exhibit high volatility

**Market Behavior**:
- Base spread: 0.56 pips (normal market conditions)
- Spread excursions: 0.95 ± 1.12 pips (volatile periods)
- Range: 0.56p → 13.4p (max observed)

**ML Implications**:
- ✅ High signal-to-static ratio (22.5% varying)
- ✅ Extreme variance captures regime shifts
- ✅ Ideal for regime-switching models
- ✅ Supports HFT signal detection

### Distribution Statistics (Mode-Truncated)

| Percentile | Value (pips) | Interpretation |
|------------|--------------|----------------|
| P1 | 0.69 | Base spread floor |
| P10 | 0.69 | 90% above this |
| P25 | 0.69 | Q1 (tight clustering) |
| **P50** | **0.69** | Median of non-modal |
| P75 | 0.69 | Q3 |
| P90 | 0.69 | 10% exceed |
| P95 | 3.68 | Extreme events start |
| **P99** | **6.68** | Top 1% outliers |
| P99.9 | 13.4 | Maximum spread |

**IQR (P25-P75)**: 0.0 pips (tight non-modal clustering at 0.69p)
**Range**: 12.74 pips (0.69p → 13.43p)

---

## 2. Mini/Cent (EURUSDm/c): Ultra-High Modal Concentration

### Distribution Characteristics

**Modal Behavior**:
- Mode value: 0.89 pips (0.892p)
- Modal frequency: 3,536,645 ticks
- Modal coverage: **98.4%** (near-deterministic)

**Non-Modal Tail** (minimal signal region):
- Observations: 57,746 ticks
- Coverage: **1.6% of total**
- Mean (mode-truncated): 6.57 pips
- Std Dev (mode-truncated): 3.21 pips
- **CV (mode-truncated): 48.9%**

### Signal Quality Score

```
SQ = P(non-modal) × CV_truncated
   = 1.6% × 48.9%
   = 0.78
```

### Microstructure Interpretation

**Regime Dynamics**:
- **Ultra-static spread behavior**: 98.4% unchanging at 0.89 pips
- **Minimal regime variation**: Only 1.6% of observations vary
- **Moderate CV (48.9%)**: Lower variance in sparse non-modal region

**Market Behavior**:
- Base spread: 0.89 pips (dominant regime)
- Rare excursions: 6.57 ± 3.21 pips (1.6% of time)
- Range: 1.08p → 19.1p (when spread varies)

**ML Implications**:
- ❌ Poor signal-to-static ratio (1.6% varying)
- ❌ Insufficient variance for regime detection
- ❌ Unsuitable for microstructure modeling
- ❌ Near-deterministic behavior

### Distribution Statistics (Mode-Truncated)

| Percentile | Value (pips) | Interpretation |
|------------|--------------|----------------|
| P1 | 2.00 | Minimum non-modal spread |
| P10 | 2.18 | 90% above this |
| P25 | 5.31 | Q1 |
| **P50** | **5.49** | Median of sparse tail |
| P75 | 8.07 | Q3 |
| P90 | 10.83 | 10% exceed |
| P95 | 13.22 | Extreme events |
| **P99** | **16.53** | Top 1% outliers |

**IQR (P25-P75)**: 2.76 pips (wider spread in sparse tail)
**Range**: 18.03 pips (2.0p → 19.1p)

### Statistical Identity: Mini vs Cent

| Metric | Mini | Cent | Difference |
|--------|------|------|------------|
| Total ticks | 3,594,391 | 3,594,391 | 0 |
| Mode value | 0.892p | 0.892p | 0.000p |
| Modal % | 98.4% | 98.4% | 0.0% |
| Non-modal mean | 6.566p | 6.566p | 0.000p |
| Non-modal CV | 48.9% | 48.9% | 0.0% |
| **SQ** | **0.78** | **0.78** | **0.00** |

**Verdict**: ✅ Statistically identical distributions (same liquidity source, account type naming difference only)

---

## 3. Comparative Analysis

### Modal Concentration vs Signal Quality

**Inverse Relationship Observed**:

| Variant | Modal % | Non-Modal % | SQ | Rank |
|---------|---------|-------------|----|----|
| Standard | 77.5% | **22.5%** ↑ | **26.57** | 1 |
| Mini/Cent | 98.4% | 1.6% ↓ | 0.78 | 2-3 |

**Key Insight**: Lower modal concentration → higher signal quality
- Standard: 77.5% modal → **22.5% varies** → SQ 26.57
- Mini/Cent: 98.4% modal → only 1.6% varies → SQ 0.78

### Mode-Truncated CV Comparison

| Variant | CV_truncated | Interpretation |
|---------|--------------|----------------|
| **Standard** | **118.1%** | Extreme variance in non-modal region |
| Mini/Cent | 48.9% | Moderate variance in sparse tail |

**Key Insight**: Standard's non-modal CV is **2.4× higher**, indicating richer spread dynamics.

### Signal Quality Score Ratio

```
SQ_standard / SQ_mini = 26.57 / 0.78 = 34×

Standard provides 34× more effective microstructure information
```

---

## 4. Regime Switching Behavior

### Standard (EURUSD)

**Two-Regime Model**:
1. **Base Regime** (77.5%): Tight spread at 0.56 pips
2. **Excursion Regime** (22.5%): Variable spread, mean 0.95p, σ=1.12p

**Transition Characteristics**:
- Frequent transitions (22.5% in excursion regime)
- High variance during excursions (CV 118%)
- Rich information for regime detection algorithms

### Mini/Cent (EURUSDm/c)

**Near-Deterministic Model**:
1. **Dominant Regime** (98.4%): Static spread at 0.89 pips
2. **Rare Excursion Regime** (1.6%): High spread, mean 6.57p, σ=3.21p

**Transition Characteristics**:
- Rare transitions (1.6% in excursion regime)
- Insufficient variance for robust regime detection
- Unsuitable for ML feature engineering

---

## 5. Variance Decomposition

### Standard

**Total Variance Breakdown**:
- Modal contribution: 0% (no variance at mode)
- Non-modal contribution: 100% (all variance from 22.5% tail)

**Effective Variance**:
```
σ²_effective = P(non-modal) × σ²_truncated
             = 0.225 × (1.12)²
             = 0.282 pips²
```

### Mini/Cent

**Total Variance Breakdown**:
- Modal contribution: 0% (no variance at mode)
- Non-modal contribution: 100% (all variance from 1.6% tail)

**Effective Variance**:
```
σ²_effective = P(non-modal) × σ²_truncated
             = 0.016 × (3.21)²
             = 0.165 pips²
```

**Paradox**: Mini/Cent has lower effective variance despite higher σ_truncated due to minimal non-modal mass (1.6% vs 22.5%).

---

## 6. Recommendations

### Choose Standard (EURUSD) ✅

**Justification**:
- **34× higher Signal Quality Score** (26.57 vs 0.78)
- **22.5% non-modal observations** provide sufficient variance for ML
- **Extreme CV (118%)** captures rich regime-switching dynamics
- **Proven regime transitions** support microstructure modeling

**Use Cases**:
- ML-based regime detection
- HFT signal extraction
- Market microstructure analysis
- Spread forecasting models

### Avoid Mini/Cent ❌

**Limitations**:
- **98.4% modal concentration** leaves minimal signal (1.6%)
- **Near-deterministic behavior** unsuitable for variance-based models
- **Insufficient regime transitions** for robust ML training
- **Poor signal-to-static ratio** limits feature discrimination

**Alternative Use Case**:
- Static spread modeling (if deterministic behavior is desired)
- Transaction cost analysis (mode as base cost)

---

## Data Files

**Mode-Truncated Results**: [../data/mode-truncated-results/non_mode_analysis_results.csv](../data/mode-truncated-results/non_mode_analysis_results.csv)

**Histogram Data**:
- [../data/histogram/standard_histogram.csv](../data/histogram/standard_histogram.csv)
- [../data/histogram/mini_histogram.csv](../data/histogram/mini_histogram.csv)
- [../data/histogram/cent_histogram.csv](../data/histogram/cent_histogram.csv)

**Visualizations**:
- [../visualizations/mode-truncated/signal_quality_comparison.png](../visualizations/mode-truncated/signal_quality_comparison.png)
- [../visualizations/mode-truncated/variance_decomposition.png](../visualizations/mode-truncated/variance_decomposition.png)
- [../visualizations/mode-truncated/distribution_overlay.png](../visualizations/mode-truncated/distribution_overlay.png)
