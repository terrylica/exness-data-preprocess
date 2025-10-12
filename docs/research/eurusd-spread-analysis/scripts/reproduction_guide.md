# Analysis Reproduction Guide

**Framework**: Modal-band-excluded variance estimation with hurdle model decomposition
**Generated**: 2025-10-04
**Source Data**: Exness ex2archive tick data (July-September 2025)

---

## Environment Setup

### 1. Python Environment

**Using uv (recommended)**:
```bash
# Install dependencies
uv pip install pandas numpy matplotlib seaborn scipy

# Or using --with flag for one-off execution
uv run --with pandas --with numpy --with matplotlib --with seaborn python analysis.py
```

**Using pip**:
```bash
pip install pandas numpy matplotlib seaborn scipy
```

**Versions Tested**:
- Python: 3.13.6
- pandas: 2.3.2
- numpy: 2.3.3
- matplotlib: 3.10.6
- seaborn: 0.13.2
- scipy: 1.16.2

---

## Data Sources

### 1. EURUSD Variants from Exness ex2archive

**URL Pattern**:
```
https://ticks.ex2archive.com/ticks/{SYMBOL}/{YYYY}/{MM}/Exness_{SYMBOL}_{YYYY}_{MM}.zip
```

**Variants Analyzed**:

1. **Standard** (EURUSD):
   ```bash
   wget https://ticks.ex2archive.com/ticks/EURUSD/2025/07/Exness_EURUSD_2025_07.zip
   wget https://ticks.ex2archive.com/ticks/EURUSD/2025/08/Exness_EURUSD_2025_08.zip
   wget https://ticks.ex2archive.com/ticks/EURUSD/2025/09/Exness_EURUSD_2025_09.zip
   ```

2. **Mini** (EURUSDm):
   ```bash
   wget https://ticks.ex2archive.com/ticks/EURUSDm/2025/07/Exness_EURUSDm_2025_07.zip
   wget https://ticks.ex2archive.com/ticks/EURUSDm/2025/08/Exness_EURUSDm_2025_08.zip
   wget https://ticks.ex2archive.com/ticks/EURUSDm/2025/09/Exness_EURUSDm_2025_09.zip
   ```

3. **Cent** (EURUSDc):
   ```bash
   wget https://ticks.ex2archive.com/ticks/EURUSDc/2025/07/Exness_EURUSDc_2025_07.zip
   wget https://ticks.ex2archive.com/ticks/EURUSDc/2025/08/Exness_EURUSDc_2025_08.zip
   wget https://ticks.ex2archive.com/ticks/EURUSDc/2025/09/Exness_EURUSDc_2025_09.zip
   ```

4. **Raw_Spread** (zero-inflated):
   ```bash
   wget https://ticks.ex2archive.com/ticks/EURUSD_Raw_Spread/2025/07/Exness_EURUSD_Raw_Spread_2025_07.zip
   ```

**Data Format**:
- CSV format: `timestamp_ms,bid,ask`
- No header row
- Timestamp in milliseconds since epoch

---

## Analysis Workflow

### Step 1: Data Loading and Preparation

```python
import pandas as pd
import numpy as np
import zipfile
import io
import urllib.request

def load_variant_data(variant_name, year, month):
    """Load tick data from Exness archive"""
    url = f"https://ticks.ex2archive.com/ticks/{variant_name}/{year}/{month:02d}/Exness_{variant_name}_{year}_{month:02d}.zip"

    # Download and extract
    response = urllib.request.urlopen(url)
    zip_data = response.read()

    with zipfile.ZipFile(io.BytesIO(zip_data)) as zf:
        csv_file = [f for f in zf.namelist() if f.endswith('.csv')][0]
        with zf.open(csv_file) as f:
            df = pd.read_csv(f, names=['timestamp_ms', 'bid', 'ask'], header=None)

    # Calculate spread in pips
    df['spread_pips'] = (df['ask'] - df['bid']) * 10000
    df['timestamp'] = pd.to_datetime(df['timestamp_ms'], unit='ms')

    return df

# Load all variants for July-September 2025
variants = {}
for variant in ['EURUSD', 'EURUSDm', 'EURUSDc']:
    dfs = []
    for month in [7, 8, 9]:
        dfs.append(load_variant_data(variant, 2025, month))
    variants[variant] = pd.concat(dfs, ignore_index=True)

# Load Raw_Spread (July only for hurdle model)
raw_spread = load_variant_data('EURUSD_Raw_Spread', 2025, 7)
```

### Step 2: Mode-Truncated Analysis

```python
def calculate_mode_truncated_cv(spreads_arr, num_bins=100):
    """Calculate mode-truncated CV using histogram bins"""

    # Create histogram to identify mode
    hist, bin_edges = np.histogram(spreads_arr, bins=num_bins)
    bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2

    # Find modal bin
    mode_idx = hist.argmax()
    mode_value = bin_centers[mode_idx]

    # Identify observations in modal bin
    bin_width = bin_edges[1] - bin_edges[0]
    mode_mask = (spreads_arr >= bin_edges[mode_idx]) & \
                (spreads_arr < bin_edges[mode_idx + 1])

    # Calculate modal statistics
    mode_freq = mode_mask.sum()
    mode_pct = (mode_freq / len(spreads_arr)) * 100

    # Exclude modal bin
    non_mode = spreads_arr[~mode_mask]
    non_mode_pct = (len(non_mode) / len(spreads_arr)) * 100

    if len(non_mode) == 0:
        return None

    # Mode-truncated statistics
    mean_truncated = np.mean(non_mode)
    std_truncated = np.std(non_mode)
    cv_truncated = (std_truncated / mean_truncated * 100) if mean_truncated > 0 else np.nan

    # Signal Quality Score
    sq = non_mode_pct * cv_truncated / 100

    return {
        'mode_value': mode_value,
        'mode_pct': mode_pct,
        'non_mode_pct': non_mode_pct,
        'mean_truncated': mean_truncated,
        'std_truncated': std_truncated,
        'cv_truncated': cv_truncated,
        'signal_quality_score': sq
    }

# Analyze each variant
results = {}
for variant, df in variants.items():
    results[variant] = calculate_mode_truncated_cv(df['spread_pips'].values)
    print(f"{variant}: SQ = {results[variant]['signal_quality_score']:.2f}")
```

**Expected Output**:
```
EURUSD: SQ = 26.57
EURUSDm: SQ = 0.78
EURUSDc: SQ = 0.78
```

### Step 3: Hurdle Model Analysis (Raw_Spread)

```python
def analyze_hurdle_model(spreads_arr, zero_threshold=0.1):
    """Apply hurdle model for zero-inflated distributions"""

    # Part 1: Hurdle component
    zero_mask = spreads_arr < zero_threshold
    zero_pct = zero_mask.sum() / len(spreads_arr) * 100

    # Part 2: Positive tail (conditional on spread > 0)
    positive_tail = spreads_arr[~zero_mask]
    positive_pct = (len(positive_tail) / len(spreads_arr)) * 100

    if len(positive_tail) == 0:
        return None

    # Mode-truncated analysis on positive tail
    mode_truncated = calculate_mode_truncated_cv(positive_tail)

    return {
        'zero_pct': zero_pct,
        'positive_pct': positive_pct,
        'positive_tail_mode': mode_truncated['mode_value'],
        'positive_tail_cv': mode_truncated['cv_truncated'],
        'non_modal_pct_of_total': mode_truncated['non_mode_pct'] * positive_pct / 100,
        'signal_quality_score': mode_truncated['signal_quality_score'] * positive_pct / 100
    }

# Analyze Raw_Spread
raw_results = analyze_hurdle_model(raw_spread['spread_pips'].values)
print(f"Raw_Spread: SQ = {raw_results['signal_quality_score']:.2f}")
```

**Expected Output**:
```
Raw_Spread: SQ = 0.84
```

### Step 4: Visualization

```python
import matplotlib.pyplot as plt
import seaborn as sns

def plot_signal_quality_comparison(results):
    """Generate Signal Quality Score comparison chart"""

    fig, ax = plt.subplots(figsize=(10, 6))

    variants = list(results.keys())
    scores = [results[v]['signal_quality_score'] for v in variants]
    colors = ['#1f77b4', '#ff7f0e', '#2ca02c']

    bars = ax.bar(variants, scores, color=colors, alpha=0.8)
    ax.set_ylabel('Signal Quality Score')
    ax.set_title('Signal Quality Comparison: Mode-Truncated Analysis')
    ax.grid(True, alpha=0.3, axis='y')

    # Add value labels
    for bar, score in zip(bars, scores):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height(),
                f'{score:.2f}', ha='center', va='bottom', fontsize=12, fontweight='bold')

    plt.tight_layout()
    plt.savefig('signal_quality_comparison.png', dpi=300)
    plt.show()

plot_signal_quality_comparison(results)
```

---

## Statistical Validation

### Validate Mode-Truncated CV

```python
def validate_analysis(variant_name, df, expected_sq):
    """Validate analysis results against expected values"""

    result = calculate_mode_truncated_cv(df['spread_pips'].values)

    print(f"\n{variant_name} Validation:")
    print(f"  Mode value: {result['mode_value']:.2f}p (expected: varies by variant)")
    print(f"  Modal %: {result['mode_pct']:.1f}%")
    print(f"  Non-modal %: {result['non_mode_pct']:.1f}%")
    print(f"  Mode-truncated CV: {result['cv_truncated']:.1f}%")
    print(f"  Signal Quality: {result['signal_quality_score']:.2f} (expected: {expected_sq})")

    # Tolerance check
    tolerance = 0.1  # Allow 10% deviation
    if abs(result['signal_quality_score'] - expected_sq) / expected_sq < tolerance:
        print(f"  ✅ PASS")
    else:
        print(f"  ❌ FAIL: Deviation exceeds {tolerance*100}%")

# Validate each variant
validate_analysis('Standard', variants['EURUSD'], expected_sq=26.57)
validate_analysis('Mini', variants['EURUSDm'], expected_sq=0.78)
validate_analysis('Cent', variants['EURUSDc'], expected_sq=0.78)
```

---

## Output Files

### Generated Data Files

**Histogram Data**:
```python
# Save histogram data for each variant
for variant, df in variants.items():
    hist, bin_edges = np.histogram(df['spread_pips'].values, bins=100)
    bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2

    hist_df = pd.DataFrame({
        'bin_center': bin_centers,
        'frequency': hist,
        'percentage': (hist / len(df)) * 100
    })

    hist_df.to_csv(f'{variant.lower()}_histogram.csv', index=False)
```

**Mode-Truncated Results**:
```python
# Consolidate results
results_df = pd.DataFrame([
    {
        'variant': variant,
        **calculate_mode_truncated_cv(df['spread_pips'].values)
    }
    for variant, df in variants.items()
])

results_df.to_csv('mode_truncated_results.csv', index=False)
```

---

## Troubleshooting

### Issue 1: Data Type Errors
**Error**: `TypeError: unsupported operand type(s) for -: 'str' and 'str'`

**Solution**: Ensure numeric conversion during CSV loading:
```python
df['bid'] = pd.to_numeric(df['bid'], errors='coerce')
df['ask'] = pd.to_numeric(df['ask'], errors='coerce')
df = df.dropna()  # Remove rows with conversion errors
```

### Issue 2: Download Failures
**Error**: `HTTP 404 Not Found`

**Solution**: Verify URL pattern and date availability:
```python
# Check if data exists before downloading
import requests
response = requests.head(url)
if response.status_code != 200:
    print(f"Data not available for {variant} {year}-{month:02d}")
```

### Issue 3: Memory Issues (Large Files)
**Solution**: Process monthly data separately, then aggregate:
```python
# Load and analyze month by month
monthly_results = []
for month in [7, 8, 9]:
    df = load_variant_data(variant, 2025, month)
    result = calculate_mode_truncated_cv(df['spread_pips'].values)
    monthly_results.append(result)

# Average monthly Signal Quality Scores
avg_sq = np.mean([r['signal_quality_score'] for r in monthly_results])
```

---

## Expected Results Summary

### Mode-Truncated Analysis

| Variant | Modal % | Non-Modal % | CV_truncated | Signal Score | Status |
|---------|---------|-------------|--------------|--------------|--------|
| Standard | 77.5% | 22.5% | 118.1% | **26.57** | ✅ Expected |
| Mini | 98.4% | 1.6% | 48.9% | 0.78 | ✅ Expected |
| Cent | 98.4% | 1.6% | 48.9% | 0.78 | ✅ Expected |

### Hurdle Model (Raw_Spread)

| Component | Expected Value |
|-----------|---------------|
| Zero % | 98.3% |
| Positive % | 1.7% |
| Non-modal (of total) | 1.4% |
| Signal Score | 0.84 |

---

## Citation

When using this analysis methodology:

```bibtex
@misc{eurusd_spread_analysis_2025,
  title={EURUSD Spread Variant Analysis: Modal-Band-Excluded Variance Estimation},
  author={Gapless Crypto Data Research},
  year={2025},
  month={October},
  note={Framework: Mode-truncated CV with hurdle model decomposition},
  url={docs/research/eurusd-spread-analysis/}
}
```

---

## Contact & Support

For questions about this analysis:
- Review [README.md](../README.md) for overview
- Check [01-methodology.md](../01-methodology.md) for statistical framework
- See [05-final-recommendations.md](../05-final-recommendations.md) for ML guidance
