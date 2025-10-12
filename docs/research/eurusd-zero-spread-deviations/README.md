# EURUSD Zero-Spread Deviation Analysis: Multi-Period Validation

**Research Period**: Sep 2024 baseline + 16-month validation (Jan-Aug 2024+2025)
**Analysis Framework**: Position deviation mean reversion, volatility prediction, regime detection
**Generated**: 2025-10-05

---

## Executive Summary

### Key Findings

**1. Mean Reversion Pattern is STABLE Across 16 Months**

Sep 2024 baseline underestimated the actual reversion rate. Multi-period validation shows:
- **Baseline (Sep 2024)**: 70.6% moved toward midpoint @ 5s
- **Multi-period (16 months)**: 87.3% ± 1.9% moved toward midpoint @ 5s
- **Temporal stability**: σ=1.9% (very stable)
- **Year-over-year trend**: 2025 (88.8%) > 2024 (85.8%) - improving

**2. Volatility Prediction Shows MAJOR REGIME SHIFT Between 2024 and 2025**

Multi-factor volatility model (deviation magnitude + persistence + spread width + recent volatility) exhibits:
- **2024 average**: R²=0.371 ± 0.050, recent_vol r=0.588
- **2025 average**: R²=0.209 ± 0.050, recent_vol r=0.432
- **Regime shift**: 77% R² DROP from 2024 to 2025
- **Sep 2024 baseline (R²=0.185)**: Anomalous transitional month

**Hypothesis**: 2024 high-volatility regime made deviations more predictive. 2025 market regime shift reduced predictive power. Sep 2024 was transitional between regimes.

### Methodology

Zero-spread deviations occur when execution price deviates from bid-ask midpoint at zero spread (bid==ask).

**Data sources**:
- Exness EURUSD Raw_Spread variant (zero-spread events: bid==ask)
- Exness EURUSD Standard variant (bid/ask quotes for reference)
- ASOF merge with 1-second tolerance

**Position ratio formula**:
```
position_ratio = (raw_mid - std_bid) / (std_ask - std_bid)
```

**Deviation threshold**: |position_ratio - 0.5| > 0.05

**Statistical frameworks**:
- Mean reversion: Future position tracking over [5, 10, 30, 60, 300, 600]s windows
- Volatility model: Multi-factor OLS regression (4 features → future volatility)
- Temporal validation: 16 months (Jan-Aug 2024+2025), 5K sample per month

### Results Summary

| Analysis | Baseline (Sep 2024) | Multi-Period (16 months) | Temporal Stability | SLO Status |
|----------|--------------------|--------------------------|--------------------|------------|
| **Mean Reversion @ 5s** | 70.6% toward | 87.3% ± 1.9% toward | STABLE (σ=1.9%) | ✅ PASS |
| **Volatility R² (2024)** | 0.185 | 0.371 ± 0.050 | VARIABLE (CV=33%) | ✅ PASS (availability) |
| **Volatility R² (2025)** | N/A | 0.209 ± 0.050 | VARIABLE (CV=24%) | ⚠️ REGIME SHIFT |
| **Recent Vol Correlation** | r=0.418 | r=0.510 (avg) | Dominant predictor | ✅ CONSISTENT |

### Trading Implications

**Mean Reversion Signal (Robust)**:
- 87.3% of deviations move toward midpoint within 5 seconds
- Stable across 16 months and both years (2024+2025)
- **Strategy**: Fade extreme deviations (position_ratio <0.2 or >0.8)
- **Risk**: 12.7% do NOT revert (require stop-loss)

**Volatility Prediction (Regime-Dependent)**:
- 2024: Strong predictive power (R²=0.371)
- 2025: Weak predictive power (R²=0.209)
- **Strategy**: Adjust position sizing based on market regime
- **Signal**: Recent volatility remains strongest predictor (r=0.510)

**Regime Detection**:
- Major shift occurred between 2024 and 2025
- Suggests structural market change (lower volatility, lower predictability)
- **Implication**: Backtest strategies across multiple regimes

---

## Document Navigation

1. **[Methodology](01-methodology.md)** - Data sources, formulas, SLOs, statistical frameworks
2. **[Baseline: Sep 2024](02-baseline-sep2024.md)** - Original single-month analysis
3. **[Multi-Period Validation](03-multiperiod-validation.md)** - 16-month temporal stability testing
4. **[Discoveries & Plan Evolution](04-discoveries-and-plan-evolution.md)** - Version-tracked findings during implementation
5. **[Trading Implications](05-trading-implications.md)** - Risk management strategies (pending Phase 4-5)

### Data & Scripts

- **[data/](data/)** - CSV results organized by analysis
  - [baseline-sep2024/](data/baseline-sep2024/) - Sep 2024 results (4 analyses)
  - [multiperiod-validation/](data/multiperiod-validation/) - 16-month validation results
  - [plan/](data/plan/) - Master implementation plan with version history

- **[scripts/](scripts/)** - Python analysis code
  - [baseline-sep2024/](scripts/baseline-sep2024/) - Sep 2024 analysis scripts
  - [multiperiod-validation/](scripts/multiperiod-validation/) - Multi-period validation scripts
  - [reproduction_guide.md](scripts/reproduction_guide.md) - How to reproduce analyses

- **[findings/](findings/)** - Generated reports
  - [baseline-sep2024-comprehensive-summary.md](findings/baseline-sep2024-comprehensive-summary.md)
  - [phase2-mean-reversion-report.md](findings/phase2-mean-reversion-report.md)
  - [phase3-volatility-model-report.md](findings/phase3-volatility-model-report.md)

---

## Research Status

- ✅ **Phase 1**: Data validation (32 files, 100% success)
- ✅ **Phase 2**: Mean reversion temporal stability (STABLE)
- ✅ **Phase 3**: Volatility model robustness (REGIME SHIFT discovered)
- ⏸️ **Phase 4**: Flash crash prediction validation (pending)
- ⏸️ **Phase 5**: Regime detection cluster analysis (pending)

---

## Citation

If referencing this research:

```
EURUSD Zero-Spread Deviation Multi-Period Validation
Data: Exness tick data (ex2archive.com), Jan-Aug 2024+2025
Framework: Position ratio deviation analysis with temporal validation
Key Finding: Mean reversion stable (87.3% ± 1.9%), volatility prediction regime-dependent
Generated: 2025-10-05
```

---

## Related Research

- **[EURUSD Spread Analysis](../eurusd-spread-analysis/)** - Modal-band-excluded variance estimation
- **Exness Data Guide**: `~/.claude/tools/exness-data/README.md`
- **Project Documentation**: `CLAUDE.md` (Forex Data Sources section)
