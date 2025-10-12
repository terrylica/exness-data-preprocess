#!/usr/bin/env python3
"""
Phase 5: Survivorship Bias Investigation
Version: 1.0.1 (CORRECTED - Windowed Lookup)
Date: 2025-10-05

CORRECTIVE ACTION: v1.0.0 used incorrect exact timestamp matching
v1.0.1 uses windowed lookup matching Phase 2 methodology exactly

Analyses:
- Exclusion reason taxonomy (why cases excluded)
- Survivorship bias quantification (compare analyzed vs excluded)
- Sensitivity analysis (test robustness under different assumptions)

SLOs:
- Availability: 100% (all analyses complete or fail explicitly)
- Correctness: Exclusion rate < 10% (validate methodology)
- Observability: Detailed logging of exclusion reasons
- Maintainability: Out-of-the-box pandas/numpy only

Dependencies:
- Exness EURUSD data (Standard + Raw_Spread variants)
- Phase 2 methodology (windowed lookup, not exact matching)
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np
import zipfile
import logging
from datetime import timedelta

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

# Constants (match Phase 2 exactly)
DEVIATION_THRESHOLD = 0.02
SAMPLE_SIZE = 5000
REVERSION_WINDOWS = [5, 10, 30, 60]

# Error classes
class InsufficientDataError(Exception):
    """Raised when insufficient data for analysis"""
    pass

class AnalysisError(Exception):
    """Raised when analysis execution fails"""
    pass

class SLOViolationError(Exception):
    """Raised when SLO is violated (e.g., exclusion rate > 10%)"""
    pass

# =============================================================================
# Phase 5.1: Exclusion Reason Taxonomy (CORRECTED)
# =============================================================================

def analyze_exclusion_reasons(year: str, month: str) -> dict:
    """
    Categorize why zero-spread deviations are excluded from 5s reversion analysis.

    CORRECTED v1.0.1: Uses windowed lookup matching Phase 2 exactly.

    Exclusion criteria:
    1. End of dataset (window extends beyond available data)
    2. Insufficient window data (< 2 points in [t0, t1])
    3. Other reasons

    Args:
        year: Year string (e.g., '2024')
        month: Month string (e.g., '01')

    Returns:
        {
            'month': str,
            'sample_size': int,
            'analyzed': int,
            'excluded': int,
            'exclusion_reasons': {
                'end_of_dataset': int,
                'insufficient_window_data': int,
                'other': int
            },
            'exclusion_rate': float
        }

    Raises:
        FileNotFoundError: If data files not found
        AnalysisError: If analysis fails
        SLOViolationError: If exclusion_rate > 10%
    """
    month_str = f"{year}-{month}"
    logger.info(f"Analyzing exclusion reasons: {month_str}")

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

    # ASOF merge (match Phase 2 methodology exactly)
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

    # Filter to zero-spread events
    zero_spread = merged[merged['raw_spread'] <= 0.00001].copy()

    # Identify deviations
    zero_spread['deviation'] = np.abs(zero_spread['position_ratio'] - 0.5)
    deviations = zero_spread[zero_spread['deviation'] > DEVIATION_THRESHOLD].copy()

    if len(deviations) == 0:
        raise AnalysisError(f"No deviations in {month_str}")

    # Sample for analysis (match Phase 2)
    sample_size = min(SAMPLE_SIZE, len(deviations))
    deviations_sample = deviations.sample(n=sample_size, random_state=42).copy()

    # Index for windowed lookup (MATCH PHASE 2 EXACTLY)
    zero_spread_indexed = zero_spread.set_index('Timestamp')
    max_time = zero_spread['Timestamp'].max()

    # Analyze exclusion reasons
    reasons = {
        'end_of_dataset': 0,
        'insufficient_window_data': 0,
        'other': 0
    }

    analyzed = 0
    horizon_sec = 5

    for idx, row in deviations_sample.iterrows():
        t0 = row['Timestamp']
        t1 = t0 + timedelta(seconds=horizon_sec)

        # Reason 1: Window extends beyond dataset
        if t1 > max_time:
            reasons['end_of_dataset'] += 1
            continue

        # CORRECTED: Use windowed lookup (Phase 2 methodology)
        try:
            future = zero_spread_indexed.loc[t0:t1]
        except KeyError:
            reasons['other'] += 1
            continue

        # Reason 2: Insufficient data in window (need at least 2 points)
        if len(future) < 2:
            reasons['insufficient_window_data'] += 1
            continue

        # Successfully analyzed
        analyzed += 1

    excluded = sample_size - analyzed
    exclusion_rate = excluded / sample_size if sample_size > 0 else 0

    logger.info(f"  Sample: {sample_size}, Analyzed: {analyzed}, Excluded: {excluded}")
    logger.info(f"  Exclusion rate: {exclusion_rate:.1%}")
    logger.info(f"  Reasons: end_of_dataset={reasons['end_of_dataset']}, "
                f"insufficient_window={reasons['insufficient_window_data']}, "
                f"other={reasons['other']}")

    # SLO VALIDATION: Exclusion rate must be < 10%
    if exclusion_rate > 0.10:
        raise SLOViolationError(
            f"Exclusion rate {exclusion_rate:.1%} exceeds 10% threshold. "
            f"Methodology may still be flawed."
        )

    return {
        'month': month_str,
        'sample_size': sample_size,
        'analyzed': analyzed,
        'excluded': excluded,
        'exclusion_reasons': reasons,
        'exclusion_rate': exclusion_rate
    }

# =============================================================================
# Phase 5.2: Survivorship Bias Quantification (CORRECTED)
# =============================================================================

def estimate_survivorship_bias(year: str, month: str) -> dict:
    """
    Compare reversion behavior of analyzed vs excluded cases.

    CORRECTED v1.0.1: Uses windowed lookup matching Phase 2.

    Args:
        year: Year string
        month: Month string

    Returns:
        {
            'month': str,
            'analyzed_reversion_rate': float,
            'excluded_reversion_rate': float,
            'bias_magnitude': float,
            'bias_direction': str,
            'n_analyzed': int,
            'n_excluded': int
        }
    """
    month_str = f"{year}-{month}"
    logger.info(f"Estimating survivorship bias: {month_str}")

    # Load and prepare data (same as Phase 5.1)
    std_path = DATA_DIR / f"Exness_EURUSD_{year}_{month}.zip"
    rs_path = DATA_DIR / f"Exness_EURUSD_Raw_Spread_{year}_{month}.zip"

    if not std_path.exists() or not rs_path.exists():
        raise FileNotFoundError(f"Missing data for {month_str}")

    with zipfile.ZipFile(std_path) as zf:
        csv = [f for f in zf.namelist() if f.endswith('.csv')][0]
        with zf.open(csv) as f:
            std_df = pd.read_csv(f)

    std_df = std_df[['Timestamp', 'Bid', 'Ask']].copy()
    std_df.columns = ['Timestamp', 'std_bid', 'std_ask']
    std_df['Timestamp'] = pd.to_datetime(std_df['Timestamp'], utc=True)

    with zipfile.ZipFile(rs_path) as zf:
        csv = [f for f in zf.namelist() if f.endswith('.csv')][0]
        with zf.open(csv) as f:
            rs_df = pd.read_csv(f)

    rs_df = rs_df[['Timestamp', 'Bid', 'Ask']].copy()
    rs_df.columns = ['Timestamp', 'raw_bid', 'raw_ask']
    rs_df['Timestamp'] = pd.to_datetime(rs_df['Timestamp'], utc=True)
    rs_df['raw_mid'] = (rs_df['raw_bid'] + rs_df['raw_ask']) / 2
    rs_df['raw_spread'] = rs_df['raw_ask'] - rs_df['raw_bid']

    # ASOF merge
    merged = pd.merge_asof(
        rs_df.sort_values('Timestamp'),
        std_df.sort_values('Timestamp'),
        on='Timestamp',
        direction='backward',
        tolerance=pd.Timedelta(seconds=10)
    )

    merged = merged.dropna().reset_index(drop=True)
    merged['position_ratio'] = (
        (merged['raw_mid'] - merged['std_bid']) /
        (merged['std_ask'] - merged['std_bid'])
    )

    zero_spread = merged[merged['raw_spread'] <= 0.00001].copy()
    zero_spread['deviation'] = np.abs(zero_spread['position_ratio'] - 0.5)
    deviations = zero_spread[zero_spread['deviation'] > DEVIATION_THRESHOLD].copy()

    if len(deviations) == 0:
        raise AnalysisError(f"No deviations in {month_str}")

    sample_size = min(SAMPLE_SIZE, len(deviations))
    deviations_sample = deviations.sample(n=sample_size, random_state=42).copy()

    # Index for windowed lookup
    zero_spread_indexed = zero_spread.set_index('Timestamp')
    max_time = zero_spread['Timestamp'].max()

    # Separate analyzed vs excluded cases
    horizon_sec = 5
    analyzed_cases = []
    excluded_cases = []

    for idx, row in deviations_sample.iterrows():
        t0 = row['Timestamp']
        t1 = t0 + timedelta(seconds=horizon_sec)

        if t1 > max_time:
            excluded_cases.append(row)
            continue

        try:
            future = zero_spread_indexed.loc[t0:t1]
        except KeyError:
            excluded_cases.append(row)
            continue

        if len(future) < 2:
            excluded_cases.append(row)
            continue

        analyzed_cases.append(row)

    # Calculate reversion rates for both groups
    def calc_reversion_rate(cases):
        """Calculate reversion rate using Phase 2 methodology"""
        if len(cases) == 0:
            return np.nan

        toward_mid = 0
        for case in cases:
            t0 = case['Timestamp']
            t1 = t0 + timedelta(seconds=horizon_sec)

            try:
                future = zero_spread_indexed.loc[t0:t1]
            except KeyError:
                continue

            if len(future) < 2:
                continue

            # Match Phase 2: use last point in window
            final_pos = future['position_ratio'].iloc[-1]

            # Check if moved toward 0.5
            initial_dev = abs(case['position_ratio'] - 0.5)
            final_dev = abs(final_pos - 0.5)

            if final_dev < initial_dev:
                toward_mid += 1

        return toward_mid / len(cases) if len(cases) > 0 else 0

    analyzed_rate = calc_reversion_rate(analyzed_cases)
    excluded_rate = calc_reversion_rate(excluded_cases)

    bias_magnitude = analyzed_rate - excluded_rate
    bias_direction = 'upward' if bias_magnitude > 0 else 'downward' if bias_magnitude < 0 else 'none'

    logger.info(f"  Analyzed: {len(analyzed_cases)} cases, reversion={analyzed_rate:.1%}")
    logger.info(f"  Excluded: {len(excluded_cases)} cases, reversion={excluded_rate:.1%}")
    logger.info(f"  Bias: {bias_magnitude:+.1%} ({bias_direction})")

    return {
        'month': month_str,
        'analyzed_reversion_rate': analyzed_rate,
        'excluded_reversion_rate': excluded_rate,
        'bias_magnitude': bias_magnitude,
        'bias_direction': bias_direction,
        'n_analyzed': len(analyzed_cases),
        'n_excluded': len(excluded_cases)
    }

# =============================================================================
# Phase 5.3: Sensitivity Analysis
# =============================================================================

def sensitivity_analysis_exclusions(year: str, month: str) -> dict:
    """
    Recalculate mean reversion under different exclusion assumptions.

    Scenarios:
    1. Baseline: Exclude cases with insufficient window data (Phase 2)
    2. Pessimistic: Assume excluded cases never revert (0% reversion)
    3. Optimistic: Assume excluded cases revert at same rate as analyzed
    4. Realistic: Use actual excluded case reversion rate

    Args:
        year: Year string
        month: Month string

    Returns:
        {
            'month': str,
            'baseline_5s': float,
            'pessimistic_5s': float,
            'optimistic_5s': float,
            'realistic_5s': float,
            'range_5s': float  # max - min
        }
    """
    month_str = f"{year}-{month}"
    logger.info(f"Sensitivity analysis: {month_str}")

    # Get bias estimates
    bias = estimate_survivorship_bias(year, month)

    n_analyzed = bias['n_analyzed']
    n_excluded = bias['n_excluded']
    analyzed_rate = bias['analyzed_reversion_rate']
    excluded_rate = bias['excluded_reversion_rate']

    # Scenario 1: Baseline (analyzed only, current Phase 2)
    baseline = analyzed_rate

    # Scenario 2: Pessimistic (excluded = 0% reversion)
    pessimistic = (n_analyzed * analyzed_rate + n_excluded * 0) / (n_analyzed + n_excluded)

    # Scenario 3: Optimistic (excluded = same as analyzed)
    optimistic = (n_analyzed * analyzed_rate + n_excluded * analyzed_rate) / (n_analyzed + n_excluded)

    # Scenario 4: Realistic (excluded = estimated rate)
    realistic = (n_analyzed * analyzed_rate + n_excluded * excluded_rate) / (n_analyzed + n_excluded)

    range_5s = max(baseline, pessimistic, optimistic, realistic) - min(baseline, pessimistic, optimistic, realistic)

    logger.info(f"  Baseline: {baseline:.1%}")
    logger.info(f"  Pessimistic: {pessimistic:.1%}")
    logger.info(f"  Optimistic: {optimistic:.1%}")
    logger.info(f"  Realistic: {realistic:.1%}")
    logger.info(f"  Range: {range_5s:.1%}")

    return {
        'month': month_str,
        'baseline_5s': baseline,
        'pessimistic_5s': pessimistic,
        'optimistic_5s': optimistic,
        'realistic_5s': realistic,
        'range_5s': range_5s
    }

# =============================================================================
# Main Execution
# =============================================================================

def main():
    """Execute Phase 5 survivorship bias investigation (v1.0.1 CORRECTED)"""

    logger.info("=" * 80)
    logger.info("Phase 5: Survivorship Bias Investigation (v1.0.1 CORRECTED)")
    logger.info("=" * 80)
    logger.info("Methodology: Windowed lookup matching Phase 2 exactly")
    logger.info("=" * 80)

    # Test months (sample 3 months for speed: Jan 2024, Aug 2024, Jan 2025)
    test_months = [
        ('2024', '01'),
        ('2024', '08'),
        ('2025', '01')
    ]

    # =============================================================================
    # Phase 5.1: Exclusion Reason Taxonomy
    # =============================================================================

    logger.info("\n--- Phase 5.1: Exclusion Reason Taxonomy (CORRECTED) ---")

    exclusion_results = []
    for year, month in test_months:
        try:
            result = analyze_exclusion_reasons(year, month)
            exclusion_results.append(result)
        except Exception as e:
            logger.error(f"Exclusion taxonomy failed for {year}-{month}: {e}")
            raise

    # Save exclusion taxonomy
    exclusion_output = OUTPUT_DIR / "phase5_exclusion_taxonomy_v1.0.1.csv"
    df_exclusion = pd.DataFrame(exclusion_results)

    # Flatten exclusion_reasons dict
    reasons_df = pd.DataFrame(df_exclusion['exclusion_reasons'].tolist())
    df_exclusion = pd.concat([
        df_exclusion.drop('exclusion_reasons', axis=1),
        reasons_df
    ], axis=1)

    df_exclusion.to_csv(exclusion_output, index=False)
    logger.info(f"\n✓ Exclusion taxonomy saved: {exclusion_output}")

    # =============================================================================
    # Phase 5.2: Survivorship Bias Quantification
    # =============================================================================

    logger.info("\n--- Phase 5.2: Survivorship Bias Quantification (CORRECTED) ---")

    bias_results = []
    for year, month in test_months:
        try:
            result = estimate_survivorship_bias(year, month)
            bias_results.append(result)
        except Exception as e:
            logger.error(f"Bias quantification failed for {year}-{month}: {e}")
            raise

    bias_output = OUTPUT_DIR / "phase5_survivorship_bias_v1.0.1.csv"
    pd.DataFrame(bias_results).to_csv(bias_output, index=False)
    logger.info(f"\n✓ Survivorship bias results saved: {bias_output}")

    # =============================================================================
    # Phase 5.3: Sensitivity Analysis
    # =============================================================================

    logger.info("\n--- Phase 5.3: Sensitivity Analysis (CORRECTED) ---")

    sensitivity_results = []
    for year, month in test_months:
        try:
            result = sensitivity_analysis_exclusions(year, month)
            sensitivity_results.append(result)
        except Exception as e:
            logger.error(f"Sensitivity analysis failed for {year}-{month}: {e}")
            raise

    sensitivity_output = OUTPUT_DIR / "phase5_sensitivity_analysis_v1.0.1.csv"
    pd.DataFrame(sensitivity_results).to_csv(sensitivity_output, index=False)
    logger.info(f"\n✓ Sensitivity analysis saved: {sensitivity_output}")

    # =============================================================================
    # Summary Report
    # =============================================================================

    logger.info("\n" + "=" * 80)
    logger.info("Phase 5 Complete - Survivorship Bias Summary (v1.0.1)")
    logger.info("=" * 80)

    # Average exclusion rate
    avg_exclusion_rate = df_exclusion['exclusion_rate'].mean()
    logger.info(f"\nAverage Exclusion Rate: {avg_exclusion_rate:.1%}")

    # SLO Validation
    if avg_exclusion_rate < 0.10:
        logger.info("✅ SLO MET: Exclusion rate < 10%")
    else:
        logger.info(f"❌ SLO FAILED: Exclusion rate {avg_exclusion_rate:.1%} exceeds 10%")

    # Dominant exclusion reason
    reason_cols = ['end_of_dataset', 'insufficient_window_data', 'other']
    reason_totals = df_exclusion[reason_cols].sum()
    dominant_reason = reason_totals.idxmax()
    logger.info(f"Dominant Exclusion Reason: {dominant_reason} ({reason_totals[dominant_reason]} cases)")

    # Average bias magnitude
    df_bias = pd.DataFrame(bias_results)
    avg_bias = df_bias['bias_magnitude'].mean()
    logger.info(f"\nAverage Bias Magnitude: {avg_bias:+.1%}")

    # Sensitivity range
    df_sensitivity = pd.DataFrame(sensitivity_results)
    avg_range = df_sensitivity['range_5s'].mean()
    logger.info(f"Average Sensitivity Range: {avg_range:.1%}")

    if avg_range < 0.05:
        logger.info("✅ Conclusions ROBUST (range < 5pp)")
    else:
        logger.info("⚠️  Survivorship bias is SIGNIFICANT (range ≥ 5pp)")

    logger.info(f"\n✅ All Phase 5 analyses completed successfully (v1.0.1 CORRECTED)")
    logger.info(f"Results saved to: {OUTPUT_DIR}")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error(f"Phase 5 execution failed: {e}")
        sys.exit(1)
