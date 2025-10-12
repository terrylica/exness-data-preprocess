# Final Recommendations: ML Feature Engineering

**Based on**: Modal-band-excluded variance estimation and hurdle model analysis
**Decision Framework**: Signal Quality Score maximization
**Target Application**: ML-based microstructure modeling and HFT signal extraction

---

## Executive Recommendation

### ✅ USE: Standard (EURUSD)

**Signal Quality Score: 26.57** (highest among all variants)

**Formal Reasoning**:
> In mode-truncated analysis, Standard (EURUSD) exhibits the highest proportion of non-deterministic observations (22.5%) with extreme coefficient of variation (118.1%). This yields a signal quality score 31.6× superior to Raw_Spread and 34× superior to Mini/Cent variants, providing optimal microstructure information for ML feature engineering.

---

## 1. Variant Selection Decision Matrix

| Variant | Modal % | Non-Modal % | CV_truncated | Signal Score | **Recommendation** |
|---------|---------|-------------|--------------|--------------|-------------------|
| **Standard** | 77.5% | **22.5%** | **118.1%** | **26.57** | ✅ **PRIMARY CHOICE** |
| Mini | 98.4% | 1.6% | 48.9% | 0.78 | ❌ Reject |
| Cent | 98.4% | 1.6% | 48.9% | 0.78 | ❌ Reject |
| Raw_Spread | 98.3% zeros | 1.4% varying | 58.6% | 0.84 | ❌ Reject |

---

## 2. Standard (EURUSD): Technical Justification

### Microstructure Characteristics

**Modal Regime** (77.5% of observations):
- Base spread: 0.56 pips
- Represents normal market conditions
- Tight bid-ask (low transaction cost regime)

**Non-Modal Regime** (22.5% of observations):
- Mean spread: 0.95 pips
- Std dev: 1.12 pips
- **CV: 118.1%** (extreme variability)
- Range: 0.69p → 13.4p

**Regime Transitions**:
- Frequent switching (22.5% excursion rate)
- High variance during excursions
- Rich information for regime detection

### ML Engineering Advantages

1. **Sufficient Variance Mass** (22.5%)
   - 881,837 varying observations
   - Adequate training data for variance-based models
   - Supports robust statistical learning

2. **Extreme Mode-Truncated CV** (118%)
   - Captures regime-switching dynamics
   - Enables discrimination between spread states
   - High feature information content

3. **Realistic Spread Behavior**
   - No artificial zero-inflation
   - Authentic market microstructure
   - Generalizable to real trading conditions

4. **Signal-to-Static Ratio**
   - 22.5% signal / 77.5% static = 0.29
   - Higher than Mini/Cent (1.6/98.4 = 0.016)
   - 18× better information density

### Recommended Use Cases

✅ **Optimal Applications**:
- **Regime-switching models**: HMM, MS-GARCH for spread forecasting
- **HFT signal extraction**: Spread anomaly detection
- **Market microstructure analysis**: Order flow imbalance, liquidity modeling
- **ML feature engineering**: Spread variance as predictive feature
- **Transaction cost modeling**: Dynamic spread forecasting

✅ **Feature Engineering Strategies**:
- Rolling mode-truncated CV (window-based regime detection)
- Spread excursion indicators (binary: in-mode vs out-of-mode)
- Non-modal spread percentiles (P75, P90, P99 as risk metrics)
- Regime transition probabilities (Markov switching)

---

## 3. Why Reject Mini/Cent

### Technical Limitations

**Ultra-High Modal Concentration** (98.4%):
- Only 1.6% of observations vary (57,746 ticks)
- Insufficient variance mass for ML training
- Near-deterministic behavior

**Low Mode-Truncated CV** (48.9%):
- 2.4× lower than Standard (118%)
- Minimal spread dynamics
- Poor feature discrimination

**Signal Quality Score** (0.78):
- 34× inferior to Standard
- Unusable for variance-based modeling

### Microstructure Issues

**Sparse Regime Transitions**:
- 98.4% in single regime (0.89p mode)
- 1.6% excursion rate (too rare)
- Insufficient regime information

**Ineffective for ML**:
- Training on 98.4% static data = poor generalization
- 1.6% varying data = overfitting risk
- Regime detection models degrade to constant prediction

### Alternative Use Cases (Non-ML)

⚠️ **Limited Applications**:
- Static transaction cost estimation (use mode as base cost)
- Deterministic spread modeling (if variance is undesired)
- Account-type comparison (Mini vs Cent identical, naming difference only)

---

## 4. Why Reject Raw_Spread

### Extreme Zero-Inflation (98.3%)

**Hurdle Model Decomposition**:
- 98.3% deterministic zeros
- 1.7% positive tail
- Final varying mass: **1.4%** (after mode exclusion)

**Signal Quality Score** (0.84):
- 32× inferior to Standard
- Unusable for ML feature extraction

### Artificial Construction

**Zero-Spread Regime**:
- 98.3% zero spreads not realistic for FX market
- Likely synthetic/post-processed data
- Does not reflect true bid-ask dynamics

**Positive Tail**:
- Sparse observations (22,278 ticks)
- Mean 3.12p (higher than Standard)
- Represents exceptional events, not normal conditions

### Microstructure Implications

**Unsuitable for**:
- ❌ Realistic spread modeling
- ❌ Transaction cost analysis
- ❌ Liquidity research
- ❌ ML feature engineering

**Why it fails**:
- Zeros mask true microstructure
- Positive tail too sparse for robust estimation
- Mode-truncated CV (58.6%) lower than Standard despite appearance

---

## 5. Implementation Guidelines

### Feature Engineering with Standard (EURUSD)

#### 1. Binary Regime Indicator
```python
# Define regime based on mode-truncation
mode_value = 0.56  # From analysis
df['regime'] = (df['spread'] != mode_value).astype(int)
# 0 = in-mode (static), 1 = excursion (varying)
```

#### 2. Mode-Truncated Rolling CV
```python
# Calculate rolling CV excluding mode
window = 100  # ticks
df['rolling_cv_truncated'] = df['spread'].rolling(window).apply(
    lambda x: (x[x != mode_value].std() / x[x != mode_value].mean()) * 100
    if len(x[x != mode_value]) > 0 else 0
)
```

#### 3. Excursion Percentile Features
```python
# Non-modal spread percentiles
non_modal = df[df['spread'] != mode_value]['spread']
df['p90_excursion'] = non_modal.rolling(window).quantile(0.90)
df['p99_excursion'] = non_modal.rolling(window).quantile(0.99)
```

#### 4. Regime Transition Probability
```python
# Markov transition matrix
from sklearn.preprocessing import LabelEncoder
regime_transitions = pd.crosstab(
    df['regime'].shift(1),
    df['regime'],
    normalize='index'
)
# P(excursion | in-mode) = transition probability
```

### Model Selection by Use Case

| Use Case | Recommended Model | Feature Set |
|----------|-------------------|-------------|
| **Spread Forecasting** | MS-GARCH, HMM | Rolling CV, regime indicator |
| **HFT Signal Detection** | Isolation Forest, LSTM | Excursion percentiles, CV anomalies |
| **Liquidity Modeling** | Random Forest | Mode%, non-modal variance, transitions |
| **Transaction Cost Optimization** | XGBoost | Mode value, P90/P99 excursions, regime prob |

---

## 6. Validation Criteria

### Model Performance Metrics

**For Regime Detection Models**:
- Precision/Recall on excursion regime (target: >80%)
- F1-score on binary regime classification
- AUC-ROC for regime probability prediction

**For Spread Forecasting**:
- RMSE on non-modal spreads (exclude mode from test set)
- MAE weighted by regime (higher weight on excursions)
- Directional accuracy (spread widening/tightening)

### Signal Quality Monitoring

**Production Metrics**:
- Monitor rolling mode-truncated CV (should match 118% historical)
- Track non-modal % (should maintain ~22.5%)
- Alert if modal concentration exceeds 85% (regime shift)

---

## 7. Alternative Scenarios

### If Standard is Unavailable

**Fallback Decision Tree**:

```
IF Standard unavailable:
    IF application = static spread modeling:
        USE Mini or Cent (mode as base cost)
    ELIF application = ML/variance-based:
        REJECT all variants
        REQUEST alternative data source
    ELSE:
        EVALUATE Standart_Plus (not analyzed, may have better signal)
```

### If Zero-Inflation is Required

**Synthetic Data Generation**:
If zero-spread modeling needed (e.g., maker-taker fee analysis):
1. Start with Standard (authentic dynamics)
2. Apply conditional zero-injection (P(zero) = target%)
3. Preserve non-zero distribution from Standard
4. Validate mode-truncated CV matches Standard

---

## 8. Summary Table

### Quick Reference

| Criterion | Standard | Mini/Cent | Raw_Spread |
|-----------|----------|-----------|------------|
| **Modal %** | 77.5% | 98.4% | 98.3% zeros |
| **Non-Modal %** | **22.5%** ✅ | 1.6% | 1.4% |
| **CV_truncated** | **118%** ✅ | 49% | 59% |
| **Signal Score** | **26.57** ✅ | 0.78 | 0.84 |
| **ML Suitable** | ✅ Yes | ❌ No | ❌ No |
| **Regime Detection** | ✅ Yes | ❌ No | ❌ No |
| **HFT Signals** | ✅ Yes | ❌ No | ❌ No |
| **Realistic Spreads** | ✅ Yes | ⚠️ Static | ❌ Artificial |

---

## 9. Final Decision

### For All ML/Microstructure Applications

**✅ USE: Standard (EURUSD)**

**Rationale**:
1. **Highest Signal Quality** (26.57, 32× superior to alternatives)
2. **Sufficient Non-Modal Mass** (22.5%, 16× more than Mini/Cent)
3. **Extreme Variance** (118% CV, optimal for regime detection)
4. **Authentic Dynamics** (no zero-inflation, realistic spreads)
5. **Proven Regime Transitions** (22.5% excursion rate)

**Implementation**:
- Use mode-truncated features (exclude 0.56p mode)
- Engineer rolling CV, excursion percentiles, regime indicators
- Validate with precision/recall on excursion detection
- Monitor production signal quality (CV ~118%, non-modal ~22.5%)

---

## Related Documents

- [01-methodology.md](01-methodology.md) - Statistical framework
- [02-mode-truncated-analysis.md](02-mode-truncated-analysis.md) - Detailed Standard analysis
- [03-hurdle-model-analysis.md](03-hurdle-model-analysis.md) - Raw_Spread rejection reasoning
- [04-temporal-patterns.md](04-temporal-patterns.md) - Hourly/weekly patterns
- [README.md](README.md) - Executive summary
