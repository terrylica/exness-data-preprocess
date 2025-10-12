# Reproduction Guide: Zero-Spread Deviation Analysis

**Version**: 1.0.4
**Last Updated**: 2025-10-05

---

## Overview

This guide provides step-by-step instructions to reproduce all analyses in this research.

**Prerequisites**:
- Python 3.9+
- 281.5 MB disk space (for compressed data)
- ~2 GB RAM (for data processing)
- 30-60 minutes execution time (all phases)

---

## Step 1: Environment Setup

### Install Dependencies

```bash
# Using pip
pip install pandas>=2.0.0 numpy>=1.24.0

# Using uv (recommended)
uv pip install pandas>=2.0.0 numpy>=1.24.0
```

**Required packages**:
- `pandas>=2.0.0` (data manipulation)
- `numpy>=1.24.0` (numerical operations)
- `scipy>=1.10.0` (optional, for Phase 4-5 statistical tests)

### Verify Installation

```python
import pandas as pd
import numpy as np

print(f"pandas: {pd.__version__}")
print(f"numpy: {np.__version__}")
```

Expected output:
```
pandas: 2.x.x
numpy: 1.24.x
```

---

## Step 2: Data Download

### Automated Download (Recommended)

Use the provided download script:

```bash
# Script location (from user's global tools)
~/.claude/tools/exness-data/download_eurusd_multiperiod.sh /tmp

# This downloads:
# - 16 Standard variant files (Jan-Aug 2024+2025)
# - 16 Raw_Spread variant files (Jan-Aug 2024+2025)
# - Total: 32 ZIP files, 281.5 MB
```

Script downloads to `/tmp` by default. Modify path if needed.

### Manual Download

Download from https://ticks.ex2archive.com/:

**Standard variant** (16 files):
```bash
curl -O https://ticks.ex2archive.com/ticks/EURUSD/2024/01/Exness_EURUSD_2024_01.zip
curl -O https://ticks.ex2archive.com/ticks/EURUSD/2024/02/Exness_EURUSD_2024_02.zip
# ... (repeat for 2024-03 through 2024-08)
curl -O https://ticks.ex2archive.com/ticks/EURUSD/2025/01/Exness_EURUSD_2025_01.zip
# ... (repeat for 2025-02 through 2025-08)
```

**Raw_Spread variant** (16 files):
```bash
curl -O https://ticks.ex2archive.com/ticks/EURUSD_Raw_Spread/2024/01/Exness_EURUSD_Raw_Spread_2024_01.zip
# ... (repeat for all months)
```

### File Naming Convention

Files must follow this pattern for scripts to work:
```
Exness_EURUSD_{YYYY}_{MM}.zip
Exness_EURUSD_Raw_Spread_{YYYY}_{MM}.zip
```

---

## Step 3: Execute Analyses

### Phase 1: Data Validation

**Purpose**: Verify all 32 files load correctly and merge successfully

```bash
cd docs/research/eurusd-zero-spread-deviations
python3 scripts/multiperiod-validation/phase1_data_validation.py
```

**Expected output**:
```
================================================================================
PHASE 1: DATA LOADING & VALIDATION (16 MONTHS)
================================================================================
...
📊 Success Rate: 100.0% (16/16)
✅ Results saved: /tmp/multiperiod_data_validation.csv
```

**Output file**: `/tmp/multiperiod_data_validation.csv`

**Success criteria**:
- 100% file load success (16/16 months)
- ASOF merge rate ≥99%
- Zero-spread events detected in all months

### Phase 2: Mean Reversion Temporal Stability

**Purpose**: Test if 70.6% baseline holds across 16 months

```bash
python3 scripts/multiperiod-validation/phase2_mean_reversion.py
```

**Expected output**:
```
================================================================================
PHASE 2: MEAN REVERSION TEMPORAL STABILITY (16 MONTHS)
================================================================================
...
Temporal Stability: STABLE (σ=1.9%)
✅ Results saved: /tmp/multiperiod_mean_reversion_results.csv
✅ Report saved: /tmp/multiperiod_mean_reversion_report.md
```

**Output files**:
- `/tmp/multiperiod_mean_reversion_results.csv` (16 rows, 1 per month)
- `/tmp/multiperiod_mean_reversion_report.md` (summary report)

**Expected results**:
- Mean reversion @ 5s: 87.3% ± 1.9%
- Success rate: 100% (16/16 months)
- Temporal stability: STABLE (σ < 5%)

**Execution time**: ~8 minutes (30 seconds per month)

### Phase 3: Volatility Model R² Robustness

**Purpose**: Test if R²=0.185 holds across 16 months

```bash
python3 scripts/multiperiod-validation/phase3_volatility_model.py
```

**Expected output**:
```
================================================================================
PHASE 3: VOLATILITY MODEL R² ROBUSTNESS (16 MONTHS)
================================================================================
...
Temporal Stability: VARIABLE (σ=0.0964)
✅ Results saved: /tmp/multiperiod_volatility_model_results.csv
✅ Report saved: /tmp/multiperiod_volatility_model_report.md
```

**Output files**:
- `/tmp/multiperiod_volatility_model_results.csv` (16 rows)
- `/tmp/multiperiod_volatility_model_report.md` (summary report)

**Expected results**:
- Overall R²: 0.290 ± 0.096 (VARIABLE)
- 2024 R²: 0.371 ± 0.050
- 2025 R²: 0.209 ± 0.050
- **Discovery**: Major regime shift (77% R² drop)

**Execution time**: ~7 minutes (26 seconds per month)

### Phase 4-5: Pending

Flash crash prediction and regime detection validation scripts are pending implementation.

---

## Step 4: Baseline Sep 2024 Analysis

**Purpose**: Reproduce original Sep 2024 baseline (for comparison)

### Download Sep 2024 Data

```bash
curl -O https://ticks.ex2archive.com/ticks/EURUSD/2024/09/Exness_EURUSD_2024_09.zip
curl -O https://ticks.ex2archive.com/ticks/EURUSD_Raw_Spread/2024/09/Exness_EURUSD_Raw_Spread_2024_09.zip
```

### Execute Baseline Scripts

```bash
# Mean reversion
python3 scripts/baseline-sep2024/01_mean_reversion_analysis.py

# Volatility model
python3 scripts/baseline-sep2024/02_volatility_model_simple.py

# Flash crash prediction
python3 scripts/baseline-sep2024/03_liquidity_crisis_detection.py

# Regime detection
python3 scripts/baseline-sep2024/04_regime_detection_analysis.py
```

**Expected baseline results**:
- Mean reversion @ 5s: 70.6%
- Volatility R²: 0.185
- Flash crash lift: +13.2pp
- Regime clusters: 3 (k-means)

---

## Step 5: Verify Results

### Compare Against Documented Results

**Phase 2 (Mean Reversion)**:
```python
import pandas as pd

# Load your results
results = pd.read_csv('/tmp/multiperiod_mean_reversion_results.csv')

# Expected values
assert 0.85 < results['toward_5s'].mean() < 0.89, "Mean reversion outside expected range"
assert results['toward_5s'].std() < 0.03, "Temporal stability too variable"
print("✅ Phase 2 results validated")
```

**Phase 3 (Volatility Model)**:
```python
results = pd.read_csv('/tmp/multiperiod_volatility_model_results.csv')

# Year-over-year regime shift
r2_2024 = results[results['month'].str.startswith('2024')]['r_squared'].mean()
r2_2025 = results[results['month'].str.startswith('2025')]['r_squared'].mean()

assert 0.35 < r2_2024 < 0.40, "2024 R² outside expected range"
assert 0.19 < r2_2025 < 0.23, "2025 R² outside expected range"
print("✅ Phase 3 results validated")
```

---

## Troubleshooting

### Issue: "No zero-spread events found"

**Symptom**: Phase 2 reports 0% success rate, "No deviations in {month}"

**Cause**: Using Standard variant alone (no zero-spreads in Standard)

**Fix**: Ensure both Standard AND Raw_Spread variants are downloaded and accessible

### Issue: "FileNotFoundError"

**Symptom**: Script cannot find `/tmp/Exness_EURUSD_{year}_{month}.zip`

**Cause**: Data files not downloaded or wrong directory

**Fix**:
```bash
# Check files exist
ls -lh /tmp/Exness_EURUSD_*.zip

# Verify naming convention
# Files MUST be named: Exness_EURUSD_2024_01.zip (not 2024-01 or other format)
```

### Issue: "KeyError: 'Timestamp'"

**Symptom**: CSV parsing fails with column name error

**Cause**: CSV format changed (header row missing or different structure)

**Fix**: Update loader to match actual CSV format (see Phase 1 script)

### Issue: "MemoryError"

**Symptom**: Script crashes during data loading

**Cause**: Insufficient RAM (<2 GB available)

**Fix**:
- Reduce `SAMPLE_SIZE` constant (default 5000 → try 2500)
- Process fewer months at a time
- Close other applications

### Issue: Results differ from documented values

**Acceptable differences**:
- ±1% for mean reversion (random sampling variation)
- ±0.02 for R² (numerical precision)

**Unacceptable differences**:
- >5% for mean reversion → data loading issue
- >0.05 for R² → methodology mismatch

**Debugging**:
1. Verify random seed=42 (ensures reproducibility)
2. Check sample sizes match (5000 per month)
3. Confirm ASOF merge tolerance=1 second
4. Validate position ratio formula

---

## Performance Optimization

### Reduce Execution Time

**Sample size tuning**:
```python
# In scripts, change:
SAMPLE_SIZE = 5000  # Default
# To:
SAMPLE_SIZE = 2500  # 2× faster, slightly less precise
```

**Parallel execution** (if you have multiple cores):
```bash
# Run phases in parallel (separate terminals)
python3 scripts/multiperiod-validation/phase2_mean_reversion.py &
python3 scripts/multiperiod-validation/phase3_volatility_model.py &
wait
```

### Reduce Memory Usage

**Chunked processing** (for very large files):
```python
# Load in chunks (not implemented in current scripts)
for chunk in pd.read_csv(filepath, chunksize=100000):
    # Process chunk
    pass
```

---

## Expected Directory Structure After Execution

```
/tmp/
├── Exness_EURUSD_2024_01.zip ... 2025_08.zip (16 files)
├── Exness_EURUSD_Raw_Spread_2024_01.zip ... 2025_08.zip (16 files)
├── multiperiod_data_validation.csv
├── multiperiod_mean_reversion_results.csv
├── multiperiod_mean_reversion_report.md
├── multiperiod_volatility_model_results.csv
└── multiperiod_volatility_model_report.md
```

---

## Citation & References

**Data source**: Exness tick data - https://ticks.ex2archive.com/
**Download tool**: `~/.claude/tools/exness-data/download_eurusd_multiperiod.sh`
**Full documentation**: [../README.md](../README.md)
**Methodology**: [../01-methodology.md](../01-methodology.md)

---

## Support

For issues or questions:
1. Check [04-discoveries-and-plan-evolution.md](../04-discoveries-and-plan-evolution.md) for known issues
2. Verify data files downloaded correctly
3. Confirm environment setup (Python 3.9+, pandas 2.0+)
4. Review [01-methodology.md](../01-methodology.md) for formulas and assumptions
