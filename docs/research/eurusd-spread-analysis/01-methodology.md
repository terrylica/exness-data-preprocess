# Statistical Methodology: Modal-Band-Excluded Variance Estimation

**Framework**: Mode-truncated CV analysis with hurdle model decomposition for zero-inflated distributions

---

## 1. Mode-Truncated Analysis

### Definition

**Mode-truncated analysis** estimates variance and coefficient of variation on a distribution **after excluding the modal bin**.

### Rationale

1. **Modal concentration represents static behavior**: High frequency at a single value provides no information about spread dynamics
2. **Mode-truncated CV measures true variability**: Captures variance in the non-deterministic region
3. **Robust to modal clustering artifacts**: Eliminates artificial CV inflation from tight modal peaks

### Mathematical Formulation

Let X = spread distribution with observations {x₁, x₂, ..., xₙ}

**Step 1: Identify Mode**
```
m = mode(X) = arg max f(x)
```

**Step 2: Exclude Modal Bin**
```
X_truncated = {xᵢ ∈ X : xᵢ ≠ m}
```

**Step 3: Calculate Mode-Truncated Statistics**
```
μ_truncated = mean(X_truncated)
σ_truncated = std(X_truncated)
CV_truncated = (σ_truncated / μ_truncated) × 100%
```

**Step 4: Signal Quality Score**
```
SQ = P(non-modal) × CV_truncated

Where:
P(non-modal) = |X_truncated| / |X| = proportion of observations outside modal bin
```

### Interpretation

- **High P(non-modal)**: Large fraction of observations varying → more signal
- **High CV_truncated**: Wide variance in non-modal region → rich dynamics
- **High SQ**: Best balance of variance mass and spread variability

---

## 2. Hurdle Model Decomposition

### Definition

**Hurdle model** (also called two-part model) analyzes zero-inflated distributions in two stages:

1. **Part 1 - Hurdle Component**: Models probability of zero vs non-zero
2. **Part 2 - Positive Tail**: Analyzes conditional distribution f(X | X > 0)

### Application to Raw_Spread

Raw_Spread exhibits extreme zero-inflation (98.3% zeros), requiring hurdle framework:

**Part 1: Zero Probability**
```
P(spread = 0) = 98.3%
P(spread > 0) = 1.7%  (hurdle crossed)
```

**Part 2: Positive Tail Analysis**
```
Given spread > 0:
  - Identify mode of positive tail
  - Exclude mode
  - Calculate mode-truncated CV
```

**Part 3: Overall Signal Quality**
```
SQ = P(spread > 0 AND non-modal) × CV_truncated(positive tail)
```

### Mathematical Formulation

Let Z = {zᵢ ∈ X : zᵢ = 0} (zero mass)
Let P = {pᵢ ∈ X : pᵢ > 0} (positive tail)

**Hurdle Probability**:
```
π = P(X > 0) = |P| / (|Z| + |P|)
```

**Conditional Distribution**:
```
f(x | x > 0) = f(x) / P(X > 0)  for x > 0
```

**Mode-Truncated Analysis on Positive Tail**:
```
m_positive = mode(P)
P_truncated = {pᵢ ∈ P : pᵢ ≠ m_positive}

CV_truncated = (std(P_truncated) / mean(P_truncated)) × 100%
```

**Final Signal Quality**:
```
SQ_hurdle = (|P_truncated| / |X|) × CV_truncated
```

---

## 3. Signal Quality Metric

### Definition

**Signal Quality Score (SQ)** quantifies effective information content by combining:
1. Proportion of varying observations
2. Variance magnitude in non-deterministic region

### Formula

```
SQ = P(non-modal) × CV_truncated

Components:
- P(non-modal) ∈ [0, 1]: Fraction of observations that vary
- CV_truncated ≥ 0: Coefficient of variation after modal exclusion
```

### Interpretation Scale

| SQ Range | Signal Quality | Interpretation |
|----------|----------------|----------------|
| SQ > 20  | Excellent | High variance mass + extreme CV |
| 10 < SQ ≤ 20 | Good | Moderate variance with high CV |
| 5 < SQ ≤ 10 | Fair | Low variance or moderate CV |
| SQ ≤ 5 | Poor | Minimal varying observations |
| SQ < 1 | Unusable | Near-deterministic behavior |

### Use Cases

**ML Feature Engineering**:
- Higher SQ → richer microstructure information
- Supports regime-switching models
- Enables HFT signal detection

**Market Microstructure Analysis**:
- SQ captures effective degrees of freedom
- Identifies regimes with actionable spread dynamics

---

## 4. Comparative Framework

### Variant Selection Criteria

**For variants with minimal zeros** (Standard, Mini, Cent):
1. Apply mode-truncated analysis directly
2. Compare SQ scores
3. Select variant with highest SQ

**For zero-inflated variants** (Raw_Spread, Zero_Spread):
1. Apply hurdle model decomposition
2. Analyze positive tail with mode-truncation
3. Compare SQ_hurdle against non-zero variants

### Decision Rule

```
IF SQ_standard > 10 × SQ_alternative:
    SELECT Standard
ELSE IF SQ_alternative > SQ_standard:
    REQUIRE further domain validation
ELSE:
    SELECT variant with highest P(non-modal)
```

---

## 5. Statistical Assumptions

### Mode-Truncated Analysis

**Assumptions**:
1. **Unimodal or weak multimodal distribution**: Single dominant mode exists
2. **Modal bin captures static regime**: Mode represents tight spread clustering
3. **Non-modal region is informative**: Variance outside mode reflects market dynamics

**Validity Checks**:
- Mode coverage < 99% (ensures sufficient non-modal mass)
- CV_truncated > 10% (ensures meaningful variance)
- Non-modal observations > 1% of total

### Hurdle Model

**Assumptions**:
1. **Excess zeros are structural**: Zero-inflation reflects deterministic behavior (not sampling)
2. **Positive tail is informative**: Conditional distribution f(X|X>0) captures true dynamics
3. **Independence**: Zero vs non-zero decision independent of positive tail distribution

**Validity Checks**:
- Zero proportion > 90% (confirms zero-inflation)
- Positive tail n > 1000 observations (sufficient for robust CV)
- Mode of positive tail ≠ boundary value

---

## 6. Limitations

### Mode-Truncated Analysis

1. **Sensitive to bin width**: Modal bin definition affects results (use histogram bins)
2. **Assumes mode = static**: May underestimate signal if mode itself varies over time
3. **Single mode focus**: Multimodal distributions require segmentation

### Hurdle Model

1. **Two-step assumption**: Assumes separable zero generation mechanism
2. **Requires sufficient positive tail**: n > 1000 for robust CV estimation
3. **Boundary effects**: Mode near zero boundary may inflate CV

---

## References

**Mode-Truncated Variance**:
- Robust statistics, trimmed mean/variance literature
- Modal-band exclusion for clustered data

**Hurdle Models**:
- Cragg (1971): "Some Statistical Models for Limited Dependent Variables"
- Mullahy (1986): "Specification and testing of some modified count data models"
- Zero-inflated econometric models (Cameron & Trivedi)

**Application Domain**:
- Market microstructure analysis (bid-ask spread dynamics)
- High-frequency trading signal extraction
- Regime-switching detection in financial time series
