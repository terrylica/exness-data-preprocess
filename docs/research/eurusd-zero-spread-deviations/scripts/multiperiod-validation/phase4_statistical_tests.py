#!/usr/bin/env python3
"""
Phase 4: Formal Statistical Tests
Version: 1.0.0
Date: 2025-10-05

Tests:
- Mann-Kendall trend test for temporal monotonicity
- Chow structural break test for regime shift validation
- Breakpoint scan for optimal regime change timing

SLOs:
- Availability: 100% (all tests complete or fail explicitly)
- Correctness: scipy/statsmodels reference implementations
- Observability: p-values, test stats, confidence intervals logged
- Maintainability: Out-of-the-box tools only (no custom stats)

Dependencies:
- Phase 2-3 v1.0.6 corrected results (mean_reversion_results.csv, volatility_model_results.csv)
- scipy 1.16.2, statsmodels 0.14.4, pandas 2.0+
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np
from scipy import stats
import json
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Paths
SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR.parent.parent / "data" / "multiperiod-validation"
OUTPUT_DIR = Path("/tmp")

# Error classes
class InsufficientDataError(Exception):
    """Raised when insufficient data for statistical test"""
    pass

class TestFailedError(Exception):
    """Raised when statistical test execution fails"""
    pass

# =============================================================================
# Phase 4.1: Mann-Kendall Trend Test
# =============================================================================

def mann_kendall_trend_test(csv_path: Path, metric: str = 'toward_5s') -> dict:
    """
    Mann-Kendall trend test for temporal monotonicity.

    Null Hypothesis (H₀): No monotonic trend
    Alternative Hypothesis (H₁): Significant monotonic trend exists

    Args:
        csv_path: Path to mean_reversion_results.csv
        metric: Column to test (toward_5s, full_5s, toward_60s, etc.)

    Returns:
        {
            'metric': str,
            'tau': float,        # Kendall's tau statistic
            'p_value': float,    # Two-tailed p-value
            'trend': str,        # 'increasing', 'decreasing', 'no trend'
            'alpha': float,      # Significance level (0.05)
            'n_months': int,
            's_statistic': int   # Mann-Kendall S statistic
        }

    Raises:
        FileNotFoundError: If CSV not found
        ValueError: If metric not found in CSV
        InsufficientDataError: If n < 4 months
    """
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV not found: {csv_path}")

    df = pd.read_csv(csv_path)

    if metric not in df.columns:
        raise ValueError(
            f"Metric '{metric}' not found. Available: {df.columns.tolist()}"
        )

    if len(df) < 4:
        raise InsufficientDataError(f"Need ≥4 months, got {len(df)}")

    # Extract time series (chronological order assumed)
    values = df[metric].values
    n = len(values)

    # Calculate Mann-Kendall S statistic manually for full control
    # S = sum of sign(x_j - x_i) for all j > i
    s_statistic = 0
    for i in range(n - 1):
        for j in range(i + 1, n):
            s_statistic += np.sign(values[j] - values[i])

    # Use scipy's kendalltau for tau and p-value (reference implementation)
    tau, p_value = stats.kendalltau(range(n), values)

    # Interpret trend
    alpha = 0.05
    if p_value < alpha:
        trend = 'increasing' if tau > 0 else 'decreasing'
    else:
        trend = 'no trend'

    logger.info(f"  Mann-Kendall [{metric}]: tau={tau:.4f}, p={p_value:.4f}, trend={trend}")

    return {
        'metric': metric,
        'tau': tau,
        'p_value': p_value,
        'trend': trend,
        'alpha': alpha,
        'n_months': n,
        's_statistic': s_statistic
    }

# =============================================================================
# Phase 4.2: Chow Test for Structural Break
# =============================================================================

def chow_test_regime_shift(csv_path: Path, breakpoint_month: int = 8) -> dict:
    """
    Chow test for structural break in volatility model R².

    Null Hypothesis (H₀): No structural break (single regime)
    Alternative Hypothesis (H₁): Significant structural break exists

    Tests if mean R² differs significantly between two periods.

    Args:
        csv_path: Path to volatility_model_results.csv
        breakpoint_month: Month index for break (8 = between Aug 2024 and Jan 2025)

    Returns:
        {
            'breakpoint': str,           # '2024-08 / 2025-01'
            'f_statistic': float,
            'p_value': float,
            'n_before': int,
            'n_after': int,
            'r2_before': float,
            'r2_after': float,
            'r2_before_std': float,
            'r2_after_std': float,
            'regime_shift': bool,        # True if p < 0.05
            'alpha': float,
            'effect_size': float         # (r2_before - r2_after) / r2_before
        }

    Raises:
        FileNotFoundError: If CSV not found
        ValueError: If breakpoint out of range
        InsufficientDataError: If either period has <3 months
    """
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV not found: {csv_path}")

    df = pd.read_csv(csv_path)

    if breakpoint_month < 1 or breakpoint_month >= len(df):
        raise ValueError(
            f"Breakpoint {breakpoint_month} out of range [1, {len(df)-1}]"
        )

    # Split into two periods
    period1 = df.iloc[:breakpoint_month]  # 2024 (months 0-7)
    period2 = df.iloc[breakpoint_month:]  # 2025 (months 8-15)

    if len(period1) < 3 or len(period2) < 3:
        raise InsufficientDataError(
            f"Need ≥3 months per period, got {len(period1)} and {len(period2)}"
        )

    # Extract R² values
    r2_before = period1['r_squared'].values
    r2_after = period2['r_squared'].values

    # Chow test formula for mean comparison:
    # F = [(SSR_pooled - (SSR_1 + SSR_2)) / k] / [(SSR_1 + SSR_2) / (n1 + n2 - 2k)]
    # where k = number of parameters (k=1 for mean-only model)

    # Calculate pooled and individual residuals
    mean_pooled = df['r_squared'].mean()
    ssr_pooled = np.sum((df['r_squared'] - mean_pooled) ** 2)

    mean_before = r2_before.mean()
    mean_after = r2_after.mean()
    ssr_before = np.sum((r2_before - mean_before) ** 2)
    ssr_after = np.sum((r2_after - mean_after) ** 2)

    k = 1  # Number of parameters (intercept only for mean comparison)
    n1, n2 = len(period1), len(period2)

    # F-statistic calculation
    numerator = (ssr_pooled - (ssr_before + ssr_after)) / k
    denominator = (ssr_before + ssr_after) / (n1 + n2 - 2*k)

    if denominator == 0:
        raise TestFailedError("Zero denominator in Chow test (no variance)")

    f_stat = numerator / denominator
    p_value = 1 - stats.f.cdf(f_stat, k, n1 + n2 - 2*k)

    # Effect size (percentage drop)
    effect_size = (mean_before - mean_after) / mean_before if mean_before != 0 else 0

    breakpoint_str = f"{period1.iloc[-1]['month']} / {period2.iloc[0]['month']}"

    logger.info(f"  Chow test [{breakpoint_str}]: F={f_stat:.4f}, p={p_value:.4f}")
    logger.info(f"    R² before: {mean_before:.4f} ± {r2_before.std():.4f}")
    logger.info(f"    R² after: {mean_after:.4f} ± {r2_after.std():.4f}")
    logger.info(f"    Effect size: {effect_size:.1%}")

    return {
        'breakpoint': breakpoint_str,
        'f_statistic': f_stat,
        'p_value': p_value,
        'n_before': n1,
        'n_after': n2,
        'r2_before': mean_before,
        'r2_after': mean_after,
        'r2_before_std': r2_before.std(),
        'r2_after_std': r2_after.std(),
        'regime_shift': p_value < 0.05,
        'alpha': 0.05,
        'effect_size': effect_size
    }

# =============================================================================
# Phase 4.3: Breakpoint Scan Analysis
# =============================================================================

def find_optimal_breakpoint(csv_path: Path) -> dict:
    """
    Iterate through all possible breakpoints, find maximum F-statistic.

    Tests breakpoints leaving ≥3 months on each side.

    Args:
        csv_path: Path to volatility_model_results.csv

    Returns:
        {
            'optimal_breakpoint_index': int,
            'optimal_breakpoint_month': str,
            'max_f_statistic': float,
            'min_p_value': float,
            'all_tests': List[dict]  # All Chow test results
        }

    Raises:
        FileNotFoundError: If CSV not found
        InsufficientDataError: If <7 months total
    """
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV not found: {csv_path}")

    df = pd.read_csv(csv_path)

    if len(df) < 7:
        raise InsufficientDataError(
            f"Need ≥7 months for breakpoint scan, got {len(df)}"
        )

    results = []

    # Test all possible breakpoints (leave ≥3 months on each side)
    logger.info(f"Scanning {len(df) - 6} possible breakpoints...")

    for bp in range(3, len(df) - 3):
        result = chow_test_regime_shift(csv_path, breakpoint_month=bp)
        result['breakpoint_index'] = bp
        results.append(result)

    # Find optimal (maximum F-statistic)
    optimal = max(results, key=lambda x: x['f_statistic'])

    logger.info(f"  Optimal breakpoint: index={optimal['breakpoint_index']}, "
                f"F={optimal['f_statistic']:.4f}, p={optimal['p_value']:.4f}")

    return {
        'optimal_breakpoint_index': optimal['breakpoint_index'],
        'optimal_breakpoint_month': optimal['breakpoint'],
        'max_f_statistic': optimal['f_statistic'],
        'min_p_value': optimal['p_value'],
        'all_tests': results
    }

# =============================================================================
# Main Execution
# =============================================================================

def main():
    """Execute Phase 4 statistical tests"""

    logger.info("=" * 80)
    logger.info("Phase 4: Formal Statistical Tests")
    logger.info("=" * 80)

    # Input paths
    mean_reversion_csv = DATA_DIR / "mean_reversion_results.csv"
    volatility_csv = DATA_DIR / "volatility_model_results.csv"

    # Validate input files exist
    if not mean_reversion_csv.exists():
        raise FileNotFoundError(f"Missing Phase 2 results: {mean_reversion_csv}")
    if not volatility_csv.exists():
        raise FileNotFoundError(f"Missing Phase 3 results: {volatility_csv}")

    # =============================================================================
    # Phase 4.1: Mann-Kendall Trend Tests
    # =============================================================================

    logger.info("\n--- Phase 4.1: Mann-Kendall Trend Tests ---")

    # Test multiple metrics
    metrics_to_test = ['toward_5s', 'full_5s', 'toward_60s', 'full_60s']
    mann_kendall_results = []

    for metric in metrics_to_test:
        try:
            result = mann_kendall_trend_test(mean_reversion_csv, metric)
            mann_kendall_results.append(result)
        except Exception as e:
            logger.error(f"Mann-Kendall test failed for {metric}: {e}")
            raise

    # Save Mann-Kendall results
    mk_output = OUTPUT_DIR / "phase4_mann_kendall_results.csv"
    pd.DataFrame(mann_kendall_results).to_csv(mk_output, index=False)
    logger.info(f"\n✓ Mann-Kendall results saved: {mk_output}")

    # =============================================================================
    # Phase 4.2: Chow Test at 2024/2025 Boundary
    # =============================================================================

    logger.info("\n--- Phase 4.2: Chow Test (2024/2025 Boundary) ---")

    try:
        chow_result = chow_test_regime_shift(volatility_csv, breakpoint_month=8)
    except Exception as e:
        logger.error(f"Chow test failed: {e}")
        raise

    # Save Chow test result (convert bool to int for JSON compatibility)
    chow_output = OUTPUT_DIR / "phase4_chow_test_results.json"
    chow_result_json = {
        k: (int(v) if isinstance(v, (bool, np.bool_)) else v)
        for k, v in chow_result.items()
    }
    with open(chow_output, 'w') as f:
        json.dump(chow_result_json, f, indent=2)
    logger.info(f"\n✓ Chow test results saved: {chow_output}")

    # =============================================================================
    # Phase 4.3: Breakpoint Scan
    # =============================================================================

    logger.info("\n--- Phase 4.3: Breakpoint Scan Analysis ---")

    try:
        breakpoint_scan = find_optimal_breakpoint(volatility_csv)
    except Exception as e:
        logger.error(f"Breakpoint scan failed: {e}")
        raise

    # Save all breakpoint results
    bp_output = OUTPUT_DIR / "phase4_breakpoint_scan.csv"
    pd.DataFrame(breakpoint_scan['all_tests']).to_csv(bp_output, index=False)
    logger.info(f"\n✓ Breakpoint scan saved: {bp_output}")

    # Save summary
    bp_summary_output = OUTPUT_DIR / "phase4_breakpoint_summary.json"
    with open(bp_summary_output, 'w') as f:
        summary = {
            k: v for k, v in breakpoint_scan.items() if k != 'all_tests'
        }
        json.dump(summary, f, indent=2)
    logger.info(f"✓ Breakpoint summary saved: {bp_summary_output}")

    # =============================================================================
    # Summary Report
    # =============================================================================

    logger.info("\n" + "=" * 80)
    logger.info("Phase 4 Complete - Statistical Tests Summary")
    logger.info("=" * 80)

    logger.info("\nMann-Kendall Trend Tests:")
    for result in mann_kendall_results:
        trend_symbol = "↑" if result['trend'] == 'increasing' else "↓" if result['trend'] == 'decreasing' else "→"
        sig = "***" if result['p_value'] < 0.001 else "**" if result['p_value'] < 0.01 else "*" if result['p_value'] < 0.05 else "ns"
        logger.info(f"  {result['metric']:15s}: tau={result['tau']:+.4f}, p={result['p_value']:.4f} {sig} {trend_symbol}")

    logger.info(f"\nChow Test (2024/2025 Boundary):")
    logger.info(f"  F-statistic: {chow_result['f_statistic']:.4f}")
    logger.info(f"  p-value: {chow_result['p_value']:.4f}")
    logger.info(f"  Regime shift: {'YES' if chow_result['regime_shift'] else 'NO'}")
    logger.info(f"  Effect size: {chow_result['effect_size']:.1%} drop in R²")

    logger.info(f"\nBreakpoint Scan:")
    logger.info(f"  Optimal: {breakpoint_scan['optimal_breakpoint_month']}")
    logger.info(f"  Max F: {breakpoint_scan['max_f_statistic']:.4f}")
    logger.info(f"  Min p: {breakpoint_scan['min_p_value']:.4f}")

    logger.info("\n✅ All Phase 4 tests completed successfully")
    logger.info(f"Results saved to: {OUTPUT_DIR}")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error(f"Phase 4 execution failed: {e}")
        sys.exit(1)
