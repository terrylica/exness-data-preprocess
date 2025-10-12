# EURUSD Spread Variant Analysis: Modal-Band-Excluded Variance Estimation

**Research Period**: July-September 2025 (3 months)
**Analysis Framework**: Mode-truncated CV and hurdle model decomposition
**Generated**: 2025-10-04

---

## Executive Summary

### Key Finding

**Standard (EURUSD) achieves Signal Quality Score of 26.57, representing 32× superior microstructure signal quality compared to alternative variants.**

Using modal-band-excluded variance estimation, Standard exhibits:
- **22.5% non-modal observations** (881,837 ticks varying)
- **118.1% mode-truncated CV** (extreme spread variability)
- **Optimal signal-to-static ratio** for ML feature engineering

### Methodology

This analysis applies rigorous statistical frameworks to evaluate spread variance in EURUSD tick data:

1. **Mode-Truncated Analysis**: Variance estimation after excluding modal bin (Standard, Mini, Cent)
2. **Hurdle Model Decomposition**: Two-part analysis for zero-inflated distributions (Raw_Spread)

**Signal Quality Score Definition**:
```
SQ = P(non-modal) × CV_truncated

Where:
- P(non-modal) = proportion of observations outside modal bin
- CV_truncated = coefficient of variation after modal exclusion
```

### Results Summary

| Variant | Modal % | Non-Modal % | Mode-Truncated CV | **Signal Score** | Recommendation |
|---------|---------|-------------|-------------------|------------------|----------------|
| **Standard (EURUSD)** | 77.5% | **22.5%** | **118.1%** | **26.57** | ✅ **Use for ML** |
| Mini (EURUSDm) | 98.4% | 1.6% | 48.9% | 0.78 | ❌ Avoid |
| Cent (EURUSDc) | 98.4% | 1.6% | 48.9% | 0.78 | ❌ Avoid |
| Raw_Spread | 98.3% zeros | 1.4% varying | 58.6% | 0.84 | ❌ Avoid |

**Interpretation**:
> Standard's low modal concentration (77.5%) leaves 22.5% of observations varying with extreme CV (118%), providing rich microstructure information for regime-switching models and HFT signal detection.

---

## Document Navigation

### Core Analysis

1. **[01-methodology.md](01-methodology.md)** - Statistical Framework
   - Mode-truncated analysis theory
   - Hurdle model decomposition
   - Signal quality metrics
   - Mathematical formulations

2. **[02-mode-truncated-analysis.md](02-mode-truncated-analysis.md)** - Standard/Mini/Cent Results
   - Modal concentration analysis
   - Non-modal variance estimation
   - Comparative signal quality scores
   - Distribution characteristics

3. **[03-hurdle-model-analysis.md](03-hurdle-model-analysis.md)** - Raw_Spread Zero-Inflated Analysis
   - Hurdle component (zero vs non-zero)
   - Positive tail analysis
   - Mode-truncated CV of conditional distribution
   - Comparison vs Standard

4. **[04-temporal-patterns.md](04-temporal-patterns.md)** - Hourly/Weekly Patterns
   - Hourly spread patterns (24-hour UTC)
   - Weekly statistics (W27-W40)
   - Peak activity analysis
   - Temporal regime shifts

5. **[05-final-recommendations.md](05-final-recommendations.md)** - ML Engineering Guidance
   - Variant selection criteria
   - Use cases and justification
   - Feature engineering implications
   - Formal statistical reasoning

### Supporting Materials

**Data**:
- `data/histogram/` - Spread distribution histograms
- `data/mode-truncated-results/` - Mode-truncated analysis results
- `data/hurdle-model-results/` - Zero-inflated model results

**Visualizations**:
- `visualizations/mode-truncated/` - Signal quality comparisons
- `visualizations/hurdle-model/` - Hurdle decomposition plots
- `visualizations/temporal/` - Temporal pattern analysis

**Reproducibility**:
- `scripts/reproduction_guide.md` - Complete analysis workflow

---

## Quick Reference

### Statistical Terms

- **Mode-Truncated CV**: Coefficient of variation calculated on distribution excluding modal bin
- **Modal-Band-Excluded Variance**: Variance estimation after removing observations within modal bin
- **Hurdle Model**: Two-part model for zero-inflated data (Part 1: zero vs non-zero; Part 2: conditional distribution of positives)
- **Zero-Inflated Distribution**: Probability distribution with excess mass at zero
- **Positive Tail Analysis**: Statistical analysis of f(X | X > 0) for zero-inflated distributions
- **Signal Quality Score (SQ)**: Product of non-modal proportion and mode-truncated CV

### Recommendation

**For ML Feature Engineering**: Use **Standard (EURUSD)**

**Justification**:
- 32× higher signal quality than alternatives
- Sufficient non-modal observations (22.5%) for learning
- Extreme mode-truncated CV (118%) captures regime dynamics
- Supports regime-switching models, HFT strategies, market microstructure analysis

---

## Citation

If using this analysis for research or production:

```
EURUSD Spread Variant Analysis: Modal-Band-Excluded Variance Estimation
Period: July-September 2025
Framework: Mode-truncated CV with hurdle model decomposition
Key Finding: Standard (EURUSD) Signal Quality Score = 26.57
Generated: 2025-10-04
```

---

## Related Documentation

- [CURRENT_ARCHITECTURE_STATUS.yaml](../../CURRENT_ARCHITECTURE_STATUS.yaml) - Project architecture
- [docs/api/](../../api/) - API documentation
- [docs/guides/](../../guides/) - User guides
