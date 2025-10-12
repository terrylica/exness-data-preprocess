#!/usr/bin/env python3
"""
Phase 6A: Inter-Arrival Time Analysis
Version: 1.0.0
Date: 2025-10-05

Analyzes temporal patterns of zero-spread deviations:
- Inter-arrival time statistics (mean, CV, autocorrelation)
- Distribution fitting (exponential, gamma, lognormal)
- Regime comparison (2024 vs 2025)

SLOs:
- Availability: 100% (all 16 months processed or fail explicitly)
- Correctness: scipy statistical tests, CV ±0.01 precision
- Observability: All metrics logged per month
- Maintainability: Out-of-the-box scipy/pandas/numpy only

Dependencies:
- Exness EURUSD data (Standard + Raw_Spread variants)
- Phase 2 zero-spread deviation extraction logic
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np
import zipfile
import logging
from scipy import stats
import json

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Paths
SCRIPT_DIR = Path(__file__).parent
DATA_DIR = Path("/tmp")  # Exness data location
OUTPUT_DIR = Path("/tmp")

# Constants (match Phase 2)
DEVIATION_THRESHOLD = 0.02

# Error classes
class InsufficientDataError(Exception):
    """Raised when insufficient data for analysis"""
    pass

class AnalysisError(Exception):
    """Raised when analysis execution fails"""
    pass

# =============================================================================
# Data Loading (Reuse Phase 2 Logic)
# =============================================================================

def load_month_deviations(year: str, month: str) -> pd.DataFrame:
    """
    Load zero-spread deviations for a month.
    Reuses Phase 2 data loading logic exactly.

    Returns:
        DataFrame with columns: Timestamp, position_ratio, deviation, std_mid
    """
    month_str = f"{year}-{month}"
    logger.info(f"Loading deviations: {month_str}")

    # Load Standard (quote) data
    std_path = DATA_DIR / f"Exness_EURUSD_{year}_{month}.zip"
    if not std_path.exists():
        raise FileNotFoundError(f"Missing Standard: {std_path}")

    with zipfile.ZipFile(std_path) as zf:
        csv = [f for f in zf.namelist() if f.endswith('.csv')][0]
        with zf.open(csv) as f:
            std_df = pd.read_csv(f)

    std_df = std_df[['Timestamp', 'Bid', 'Ask']].copy()
    std_df.columns = ['Timestamp', 'std_bid', 'std_ask']
    std_df['Timestamp'] = pd.to_datetime(std_df['Timestamp'], utc=True)
    std_df['std_mid'] = (std_df['std_bid'] + std_df['std_ask']) / 2
    std_df['std_spread'] = std_df['std_ask'] - std_df['std_bid']

    # Load Raw_Spread (execution prices)
    rs_path = DATA_DIR / f"Exness_EURUSD_Raw_Spread_{year}_{month}.zip"
    if not rs_path.exists():
        raise FileNotFoundError(f"Missing Raw_Spread: {rs_path}")

    with zipfile.ZipFile(rs_path) as zf:
        csv = [f for f in zf.namelist() if f.endswith('.csv')][0]
        with zf.open(csv) as f:
            rs_df = pd.read_csv(f)

    rs_df = rs_df[['Timestamp', 'Bid', 'Ask']].copy()
    rs_df.columns = ['Timestamp', 'raw_bid', 'raw_ask']
    rs_df['Timestamp'] = pd.to_datetime(rs_df['Timestamp'], utc=True)
    rs_df['raw_mid'] = (rs_df['raw_bid'] + rs_df['raw_ask']) / 2
    rs_df['raw_spread'] = rs_df['raw_ask'] - rs_df['raw_bid']

    # ASOF merge (match Phase 2 exactly)
    merged = pd.merge_asof(
        rs_df.sort_values('Timestamp'),
        std_df.sort_values('Timestamp'),
        on='Timestamp',
        direction='backward',
        tolerance=pd.Timedelta(seconds=10)
    )

    merged = merged.dropna().reset_index(drop=True)

    # Compute position ratio
    merged['position_ratio'] = (
        (merged['raw_mid'] - merged['std_bid']) /
        (merged['std_ask'] - merged['std_bid'])
    )

    # Filter to zero-spread deviations
    zero_spread = merged[merged['raw_spread'] <= 0.00001].copy()
    zero_spread['deviation'] = np.abs(zero_spread['position_ratio'] - 0.5)
    deviations = zero_spread[zero_spread['deviation'] > DEVIATION_THRESHOLD].copy()

    if len(deviations) < 1000:
        raise InsufficientDataError(
            f"{month_str}: Only {len(deviations)} deviations (need ≥1000)"
        )

    logger.info(f"  {len(deviations):,} deviations loaded")

    return deviations[['Timestamp', 'position_ratio', 'deviation', 'std_mid']]

# =============================================================================
# Inter-Arrival Time Statistics
# =============================================================================

def calculate_interval_statistics(timestamps: pd.Series) -> dict:
    """
    Calculate inter-arrival time statistics.

    Args:
        timestamps: Sorted timestamps of events

    Returns:
        {
            'n_events': int,
            'mean_interval': float,
            'std_interval': float,
            'cv': float,
            'min_interval': float,
            'max_interval': float,
            'median_interval': float,
            'acf_1': float  # Lag-1 autocorrelation
        }
    """
    # Calculate intervals
    intervals = timestamps.diff().dt.total_seconds()
    intervals = intervals[intervals > 0]  # Remove first NaN, zero intervals

    if len(intervals) < 10:
        raise InsufficientDataError("Need ≥10 intervals for statistics")

    # Descriptive statistics
    mean_interval = float(intervals.mean())
    std_interval = float(intervals.std())
    cv = std_interval / mean_interval if mean_interval > 0 else np.nan

    # Lag-1 autocorrelation
    if len(intervals) >= 3:
        acf_1, _ = stats.pearsonr(intervals[:-1], intervals[1:])
    else:
        acf_1 = np.nan

    return {
        'n_events': len(timestamps),
        'n_intervals': len(intervals),
        'mean_interval': mean_interval,
        'std_interval': std_interval,
        'cv': cv,
        'min_interval': float(intervals.min()),
        'max_interval': float(intervals.max()),
        'median_interval': float(intervals.median()),
        'acf_1': float(acf_1)
    }

# =============================================================================
# Distribution Fitting
# =============================================================================

def fit_distributions(intervals: np.ndarray) -> dict:
    """
    Fit exponential, gamma, lognormal distributions to intervals.
    Select best fit using AIC.

    Args:
        intervals: Array of inter-arrival times (seconds)

    Returns:
        {
            'best_fit': str,  # 'exponential', 'gamma', or 'lognormal'
            'exponential_aic': float,
            'gamma_aic': float,
            'lognormal_aic': float,
            'exponential_params': dict,
            'gamma_params': dict,
            'lognormal_params': dict
        }
    """
    # Filter out extreme outliers for fitting stability
    intervals_clean = intervals[intervals < np.quantile(intervals, 0.99)]

    if len(intervals_clean) < 10:
        raise InsufficientDataError("Need ≥10 intervals for distribution fitting")

    results = {}

    # Fit exponential (Poisson process - memoryless)
    try:
        exp_loc, exp_scale = stats.expon.fit(intervals_clean)
        exp_loglik = stats.expon.logpdf(intervals_clean, exp_loc, exp_scale).sum()
        exp_aic = -2 * exp_loglik + 2 * 2  # 2 parameters (loc, scale)
        results['exponential_aic'] = float(exp_aic)
        results['exponential_params'] = {'loc': float(exp_loc), 'scale': float(exp_scale)}
    except Exception as e:
        logger.warning(f"Exponential fit failed: {e}")
        results['exponential_aic'] = np.inf
        results['exponential_params'] = {}

    # Fit gamma (clustered process - shape > 1)
    try:
        gamma_a, gamma_loc, gamma_scale = stats.gamma.fit(intervals_clean)
        gamma_loglik = stats.gamma.logpdf(intervals_clean, gamma_a, gamma_loc, gamma_scale).sum()
        gamma_aic = -2 * gamma_loglik + 2 * 3  # 3 parameters
        results['gamma_aic'] = float(gamma_aic)
        results['gamma_params'] = {
            'shape': float(gamma_a),
            'loc': float(gamma_loc),
            'scale': float(gamma_scale)
        }
    except Exception as e:
        logger.warning(f"Gamma fit failed: {e}")
        results['gamma_aic'] = np.inf
        results['gamma_params'] = {}

    # Fit lognormal (multiplicative effects)
    try:
        lognorm_s, lognorm_loc, lognorm_scale = stats.lognorm.fit(intervals_clean)
        lognorm_loglik = stats.lognorm.logpdf(intervals_clean, lognorm_s, lognorm_loc, lognorm_scale).sum()
        lognorm_aic = -2 * lognorm_loglik + 2 * 3  # 3 parameters
        results['lognormal_aic'] = float(lognorm_aic)
        results['lognormal_params'] = {
            's': float(lognorm_s),
            'loc': float(lognorm_loc),
            'scale': float(lognorm_scale)
        }
    except Exception as e:
        logger.warning(f"Lognormal fit failed: {e}")
        results['lognormal_aic'] = np.inf
        results['lognormal_params'] = {}

    # Select best fit (minimum AIC)
    aics = {
        'exponential': results.get('exponential_aic', np.inf),
        'gamma': results.get('gamma_aic', np.inf),
        'lognormal': results.get('lognormal_aic', np.inf)
    }

    results['best_fit'] = min(aics, key=aics.get)

    return results

# =============================================================================
# Main Analysis
# =============================================================================

def analyze_month(year: str, month: str) -> dict:
    """Run full Phase 6A analysis for one month"""

    month_str = f"{year}-{month}"

    # Load deviations
    deviations = load_month_deviations(year, month)

    # Get timestamps
    timestamps = deviations['Timestamp'].sort_values()
    intervals = timestamps.diff().dt.total_seconds()
    intervals_clean = intervals[intervals > 0].values

    # Calculate statistics
    stats_dict = calculate_interval_statistics(timestamps)

    # Fit distributions
    dist_dict = fit_distributions(intervals_clean)

    # Combine results
    result = {
        'month': month_str,
        **stats_dict,
        **dist_dict
    }

    logger.info(f"  Mean interval: {stats_dict['mean_interval']:.1f}s, "
                f"CV: {stats_dict['cv']:.3f}, "
                f"ACF(1): {stats_dict['acf_1']:.3f}, "
                f"Best fit: {dist_dict['best_fit']}")

    return result

def main():
    """Execute Phase 6A: Inter-Arrival Time Analysis"""

    logger.info("=" * 80)
    logger.info("Phase 6A: Inter-Arrival Time Analysis")
    logger.info("=" * 80)

    # All 16 months
    months = [
        ('2024', '01'), ('2024', '02'), ('2024', '03'), ('2024', '04'),
        ('2024', '05'), ('2024', '06'), ('2024', '07'), ('2024', '08'),
        ('2025', '01'), ('2025', '02'), ('2025', '03'), ('2025', '04'),
        ('2025', '05'), ('2025', '06'), ('2025', '07'), ('2025', '08')
    ]

    all_results = []

    for year, month in months:
        try:
            result = analyze_month(year, month)
            all_results.append(result)
        except Exception as e:
            logger.error(f"Analysis failed for {year}-{month}: {e}")
            raise

    # Save results
    output_csv = OUTPUT_DIR / "phase6a_interval_statistics.csv"
    df_results = pd.DataFrame(all_results)

    # Flatten distribution params
    for dist in ['exponential', 'gamma', 'lognormal']:
        params_col = f'{dist}_params'
        if params_col in df_results.columns:
            df_results = df_results.drop(columns=[params_col])

    df_results.to_csv(output_csv, index=False)
    logger.info(f"\n✓ Interval statistics saved: {output_csv}")

    # =============================================================================
    # Regime Comparison (2024 vs 2025)
    # =============================================================================

    logger.info("\n--- Regime Comparison (2024 vs 2025) ---")

    results_2024 = df_results[df_results['month'].str.startswith('2024')]
    results_2025 = df_results[df_results['month'].str.startswith('2025')]

    cv_2024 = results_2024['cv'].mean()
    cv_2025 = results_2025['cv'].mean()

    logger.info(f"  2024 mean CV: {cv_2024:.3f}")
    logger.info(f"  2025 mean CV: {cv_2025:.3f}")
    logger.info(f"  Change: {((cv_2025 / cv_2024) - 1) * 100:+.1f}%")

    # Combined intervals for KS test (need raw data)
    # For simplicity, use month-level CVs as proxy
    ks_stat, ks_pvalue = stats.ks_2samp(
        results_2024['cv'].values,
        results_2025['cv'].values
    )

    regime_comparison = {
        'cv_2024_mean': float(cv_2024),
        'cv_2024_std': float(results_2024['cv'].std()),
        'cv_2025_mean': float(cv_2025),
        'cv_2025_std': float(results_2025['cv'].std()),
        'cv_change_pct': float(((cv_2025 / cv_2024) - 1) * 100),
        'ks_statistic': float(ks_stat),
        'ks_pvalue': float(ks_pvalue),
        'regime_shift': bool(ks_pvalue < 0.05),
        'alpha': 0.05
    }

    output_json = OUTPUT_DIR / "phase6a_regime_comparison.json"
    with open(output_json, 'w') as f:
        json.dump(regime_comparison, f, indent=2)

    logger.info(f"\n✓ Regime comparison saved: {output_json}")

    if regime_comparison['regime_shift']:
        logger.info("  ✅ Regime shift detected (p < 0.05)")
    else:
        logger.info("  ❌ No significant regime shift (p ≥ 0.05)")

    # =============================================================================
    # Summary
    # =============================================================================

    logger.info("\n" + "=" * 80)
    logger.info("Phase 6A Complete - Temporal Pattern Summary")
    logger.info("=" * 80)

    overall_cv = df_results['cv'].mean()
    overall_acf = df_results['acf_1'].mean()

    logger.info(f"\nOverall Statistics (16 months):")
    logger.info(f"  Mean interval: {df_results['mean_interval'].mean():.1f}s")
    logger.info(f"  CV: {overall_cv:.3f}")
    logger.info(f"  ACF(1): {overall_acf:.3f}")

    # Interpret CV
    if overall_cv < 0.5:
        pattern = "Regular/Periodic"
    elif overall_cv < 1.5:
        pattern = "Random (Poisson-like)"
    else:
        pattern = "Clustered/Bursty"

    logger.info(f"  Pattern: {pattern}")

    # Interpret ACF
    if abs(overall_acf) > 0.3:
        clustering = "Strong temporal clustering"
    else:
        clustering = "Weak/no temporal clustering"

    logger.info(f"  Clustering: {clustering}")

    # Best fit distribution
    best_fits = df_results['best_fit'].value_counts()
    logger.info(f"\nBest Fit Distributions:")
    for dist, count in best_fits.items():
        logger.info(f"  {dist}: {count}/16 months")

    logger.info(f"\n✅ Phase 6A completed successfully")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error(f"Phase 6A execution failed: {e}")
        sys.exit(1)
