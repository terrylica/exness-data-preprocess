# Methodology: Zero-Spread Deviation Analysis

**Version**: 1.0.4
**Last Updated**: 2025-10-05

---

## Overview

Zero-spread deviations occur when execution price deviates from the bid-ask midpoint at moments when bid==ask (zero spread). These events reveal microstructure inefficiencies and provide signals for:
- Mean reversion trading
- Volatility regime detection
- Flash crash prediction
- Market quality assessment

---

## Data Sources

### Exness Tick Data (ex2archive.com)

**Provider**: Exness (institutional ECN/STP broker)
**Source**: https://ticks.ex2archive.com/
**Precision**: Millisecond timestamps
**Coverage**: 2020-2025+, continuous tick-by-tick data

### Variants Used

#### 1. Raw_Spread Variant
**Purpose**: Zero-spread event detection
**Characteristics**:
- Bid and Ask columns represent execution prices
- Zero-spread events: bid==ask (exact equality)
- ~907K zero-spread events in Sep 2024 (EURUSD)

**File format**:
```csv
Exness,Symbol,Timestamp,Bid,Ask
Exness,EURUSD,2024-01-01 22:05:16.191Z,1.10450,1.10450
```

#### 2. Standard Variant
**Purpose**: Reference bid/ask quotes
**Characteristics**:
- Traditional quote data (always bid < ask)
- Minimum spread: 0.5 pips (NEVER zero)
- Used for position ratio calculation

**ASOF Merge**: Raw_Spread execution → nearest Standard quote (1-second tolerance)

---

## Position Ratio Formula

**Definition**:
```python
position_ratio = (raw_mid - std_bid) / (std_ask - std_bid)
```

Where:
- `raw_mid = (raw_bid + raw_ask) / 2` (execution midpoint)
- `std_bid` = Standard variant bid (from ASOF merge)
- `std_ask` = Standard variant ask (from ASOF merge)

**Interpretation**:
- `position_ratio = 0.5` → execution at midpoint (no deviation)
- `position_ratio < 0.5` → execution closer to bid (bid-biased)
- `position_ratio > 0.5` → execution closer to ask (ask-biased)
- `position_ratio < 0.2` or `> 0.8` → extreme deviation

**Deviation threshold**: `|position_ratio - 0.5| > 0.05`

---

## Statistical Frameworks

### 1. Mean Reversion Analysis

**Objective**: Test if deviations return to midpoint over time

**Methodology**:
1. Identify deviations: `|position_ratio - 0.5| > 0.05`
2. Sample 5K deviations per month (random seed=42 for reproducibility)
3. Track future position ratio at horizons: [5, 10, 30, 60, 300, 600] seconds
4. Calculate metrics:
   - **Toward midpoint**: `final_deviation < initial_deviation`
   - **Full reversion**: `final_deviation < 0.05`

**Sample size**: 5,000 deviations per month (for computational efficiency)

**Sep 2024 baseline**: 70.6% moved toward midpoint @ 5s

### 2. Volatility Model (Multi-Factor OLS)

**Objective**: Predict future volatility from deviation features

**Features (4 total)**:
1. **Deviation magnitude**: `abs(position_ratio - 0.5)`
2. **Persistence**: Duration of consecutive deviations (same type within 60s)
3. **Spread width**: Standard variant spread at deviation time (basis points)
4. **Recent volatility**: Volatility over past 300s (GARCH-like)

**Target**: Forward volatility over 5-minute horizon

**Model**: Linear regression (OLS) with standardized features

**Baseline (Sep 2024)**:
- R² = 0.185
- Recent volatility correlation: r=0.418 (dominant predictor)

**Validation**: Multi-period testing across 16 months

### 3. Flash Crash Prediction

**Objective**: Test if extreme deviations predict flash crashes

**Definition**:
- **Extreme deviation**: position_ratio < 0.2 or > 0.8
- **Flash crash**: Bid-ask spread spike >3× normal within next 60s

**Methodology**:
1. Sample 1K extreme + 1K normal deviations
2. Calculate flash crash rate at horizons: [5, 15, 30, 60]s
3. Compute lift: `extreme_rate - normal_rate`

**Baseline (Sep 2024)**: +13.2pp average lift across horizons

### 4. Regime Detection (K-Means Clustering)

**Objective**: Identify deviation patterns and volatility regimes

**Features**: Deviation magnitude, persistence, recent volatility
**Clustering**: K-means with k=3 (high/medium/low activity)

**Baseline (Sep 2024)**: Counter-intuitive finding - deviation clusters predict volatility DECREASE (42.1% increase vs 50% baseline, p=0.0004)

---

## Service Level Objectives (SLOs)

### Availability
- Data loading success rate: ≥99% (max 1 failed file per 32)
- Analysis completion rate: 100% (all phases must complete or fail explicitly)
- **Actual (Phase 1-3)**: 100% success (16/16 months)

### Correctness
- Position ratio calculation: Exact match to Sep 2024 baseline methodology
- Statistical test p-values: Reproducible within ±0.001 variance
- Temporal comparison: Month-by-month results internally consistent
- **Actual**: Mean reversion methodology exact match, volatility model reproduced ±0.01

### Security
- No data leakage: Results saved only to `/tmp/` (ephemeral storage) during analysis
- No credential exposure: Public data source, no auth required
- **Actual**: All analyses use public data, no credentials

### Observability
- Progress logging: Per-month status updates to stdout
- Error propagation: Exception raised with full context (file, month, error type)
- Result validation: Statistical sanity checks after each analysis
- **Actual**: INFO-level logging for all months, exceptions with context

### Maintainability
- Code reuse: ≥80% from existing Sep 2024 scripts
- Function modularity: Single responsibility per function
- Documentation: Inline comments for statistical formulas only
- **Actual**: ~90% code reuse, modular functions, formula comments only

---

## Error Handling

**Philosophy**: Raise and propagate all errors - no fallbacks, defaults, retries, or silent handling

**Exception hierarchy**:
```python
class MultiPeriodValidationError(Exception):
    """Base exception for multi-period validation"""
    pass

class DataLoadError(MultiPeriodValidationError):
    """Failed to load data file"""
    def __init__(self, filepath, cause):
        self.filepath = filepath
        self.cause = cause
        super().__init__(f"Failed to load {filepath}: {cause}")

class ValidationError(MultiPeriodValidationError):
    """Validation check failed"""
    def __init__(self, check_name, expected, actual):
        self.check_name = check_name
        self.expected = expected
        self.actual = actual
        super().__init__(f"{check_name} validation failed: expected {expected}, got {actual}")

class LinAlgError(MultiPeriodValidationError):
    """Linear algebra operation failed (e.g., singular matrix)"""
    pass
```

**Usage**:
```python
# Data loading
try:
    df = load_exness_data(filepath)
except Exception as e:
    raise DataLoadError(filepath, str(e)) from e

# Validation
if r_squared < 0:
    raise ValidationError("R-squared", ">= 0", r_squared)

# Regression
try:
    beta = np.linalg.inv(X.T @ X) @ X.T @ y
except np.linalg.LinAlgError as e:
    raise LinAlgError(f"Singular matrix: {e}")
```

---

## Temporal Validation Strategy

### Multi-Period Testing (16 Months)

**Coverage**: Jan-Aug 2024 + Jan-Aug 2025
**Files**: 32 total (16 months × 2 variants)
**Data volume**: 281.5 MB compressed

**Objectives**:
1. Validate Sep 2024 baseline across time periods
2. Detect regime shifts (year-over-year comparison)
3. Assess temporal stability (coefficient of variation)
4. Identify structural breaks

**Sampling**:
- 5K deviations per month (random seed=42)
- Consistent across all analyses for comparability

**Success criteria**:
- Baseline reproduction: Sep 2024 metrics within tolerance
- Temporal stability: CV < 20% for mean reversion
- Availability: ≥95% month success rate

---

## Reproducibility

### Environment
```bash
# Python 3.9+
pandas>=2.0.0
numpy>=1.24.0
scipy>=1.10.0  # For statistical tests (Phase 4-5)
```

### Data Download
```bash
# See ~/.claude/tools/exness-data/download_eurusd_multiperiod.sh
curl -O https://ticks.ex2archive.com/ticks/EURUSD/{YYYY}/{MM}/Exness_EURUSD_{YYYY}_{MM}.zip
curl -O https://ticks.ex2archive.com/ticks/EURUSD_Raw_Spread/{YYYY}/{MM}/Exness_EURUSD_Raw_Spread_{YYYY}_{MM}.zip
```

### Execution Order
```bash
# Phase 1: Data validation
python3 scripts/multiperiod-validation/phase1_data_validation.py

# Phase 2: Mean reversion
python3 scripts/multiperiod-validation/phase2_mean_reversion.py

# Phase 3: Volatility model
python3 scripts/multiperiod-validation/phase3_volatility_model.py

# Phase 4-5: Pending
```

### Random Seed
**Fixed seed = 42** for all sampling operations ensures reproducibility

---

## Limitations

1. **Geographic coverage**: EURUSD only (not tested on other pairs)
2. **Temporal coverage**: Jan-Aug 2024+2025 (excludes Sep-Dec)
3. **Sampling**: 5K per month (not full population analysis)
4. **Linear models**: OLS regression (no non-linear/interaction terms)
5. **Regime detection**: Sep 2024 baseline may be anomalous (transitional month)

---

## References

- **Data source**: https://ticks.ex2archive.com/
- **Related research**: [EURUSD Spread Analysis](../eurusd-spread-analysis/)
- **Implementation plan**: [data/plan/multiperiod_validation_plan_v1.0.9.md](data/plan/multiperiod_validation_plan_v1.0.9.md)
