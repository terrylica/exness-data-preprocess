#!/usr/bin/env python3
"""
Phase 5: Survivorship Bias Investigation
Version: 1.0.0
Date: 2025-10-05

Analyses:
- Exclusion reason taxonomy (why ~4% cases excluded)
- Survivorship bias quantification (compare analyzed vs excluded)
- Sensitivity analysis (test robustness under different assumptions)

SLOs:
- Availability: 100% (all analyses complete or fail explicitly)
- Correctness: ±0.1% absolute error tolerance
- Observability: Detailed logging of exclusion reasons
- Maintainability: Out-of-the-box pandas/numpy only

Dependencies:
- Exness EURUSD data (Standard + Raw_Spread variants)
- Phase 2 methodology (same ASOF merge, filtering, sampling)
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np
import zipfile
import logging

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

# =============================================================================
# Phase 5.1: Exclusion Reason Taxonomy
# =============================================================================

def analyze_exclusion_reasons(year: str, month: str) -> dict:
    """
    Categorize why zero-spread deviations are excluded from 5s reversion analysis.

    Potential exclusion reasons:
    1. End of dataset (event near end, no future data)
    2. Missing future Standard quote at t+5s (data gap)
    3. Zero-spread widened before 5s (transient zero-spread)
    4. Other (to be determined)

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
                'missing_future_quote': int,
                'no_std_quote_match': int,
                'other': int
            },
            'exclusion_rate': float
        }

    Raises:
        FileNotFoundError: If data files not found
        AnalysisError: If analysis fails
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

    # Analyze exclusion reasons
    reasons = {
        'end_of_dataset': 0,
        'missing_future_quote': 0,
        'no_std_quote_match': 0,
        'other': 0
    }

    analyzed = 0
    horizon_sec = 5

    # Index Standard data for fast lookup
    std_df_indexed = std_df.set_index('Timestamp').sort_index()
    max_std_time = std_df['Timestamp'].max()

    for idx, row in deviations_sample.iterrows():
        future_time = row['Timestamp'] + pd.Timedelta(seconds=horizon_sec)

        # Reason 1: Beyond dataset range
        if future_time > max_std_time:
            reasons['end_of_dataset'] += 1
            continue

        # Find future Standard quote at exactly t+5s
        future_quotes = std_df[std_df['Timestamp'] >= future_time]

        if len(future_quotes) == 0:
            reasons['missing_future_quote'] += 1
            continue

        # Check if we have a matching Standard quote
        # (In Phase 2, we use indexed lookup which may fail)
        try:
            # Simulate the Phase 2 lookup logic
            # Phase 2 uses: df_indexed.loc[future_time:future_time]
            # This will return empty if exact timestamp doesn't exist
            future_std = std_df_indexed.loc[future_time:future_time]
            if len(future_std) == 0:
                reasons['no_std_quote_match'] += 1
                continue
        except KeyError:
            reasons['no_std_quote_match'] += 1
            continue

        # Successfully analyzed
        analyzed += 1

    excluded = sample_size - analyzed

    logger.info(f"  Sample: {sample_size}, Analyzed: {analyzed}, Excluded: {excluded}")
    logger.info(f"  Reasons: end_of_dataset={reasons['end_of_dataset']}, "
                f"missing_future={reasons['missing_future_quote']}, "
                f"no_std_match={reasons['no_std_quote_match']}")

    return {
        'month': month_str,
        'sample_size': sample_size,
        'analyzed': analyzed,
        'excluded': excluded,
        'exclusion_reasons': reasons,
        'exclusion_rate': excluded / sample_size if sample_size > 0 else 0
    }

# =============================================================================
# Phase 5.2: Survivorship Bias Quantification
# =============================================================================

def estimate_survivorship_bias(year: str, month: str) -> dict:
    """
    Compare reversion behavior of analyzed vs excluded cases.

    For excluded cases, use nearest available future quote as proxy.

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

    # Separate analyzed vs excluded cases
    horizon_sec = 5
    std_df_indexed = std_df.set_index('Timestamp').sort_index()
    max_std_time = std_df['Timestamp'].max()

    analyzed_cases = []
    excluded_cases = []

    for idx, row in deviations_sample.iterrows():
        future_time = row['Timestamp'] + pd.Timedelta(seconds=horizon_sec)

        if future_time > max_std_time:
            excluded_cases.append(row)
            continue

        try:
            future_std = std_df_indexed.loc[future_time:future_time]
            if len(future_std) == 0:
                excluded_cases.append(row)
                continue
            analyzed_cases.append(row)
        except KeyError:
            excluded_cases.append(row)

    # Calculate reversion rates for both groups
    # For analyzed: use exact Phase 2 logic
    # For excluded: use nearest available future quote (best proxy)

    def calc_reversion_rate(cases, exact_match=True):
        if len(cases) == 0:
            return np.nan

        toward_mid = 0
        for case in cases:
            future_time = case['Timestamp'] + pd.Timedelta(seconds=horizon_sec)

            if exact_match:
                try:
                    future_std = std_df_indexed.loc[future_time:future_time]
                    if len(future_std) == 0:
                        continue
                    future_std_row = future_std.iloc[0]
                except KeyError:
                    continue
            else:
                # Use nearest future quote (for excluded cases)
                future_std = std_df[std_df['Timestamp'] >= future_time]
                if len(future_std) == 0:
                    continue
                future_std_row = future_std.iloc[0]

            # Calculate future position ratio
            future_pos = (
                (case['raw_mid'] - future_std_row['std_bid']) /
                (future_std_row['std_ask'] - future_std_row['std_bid'])
            )

            # Check if moved toward 0.5
            initial_dev = abs(case['position_ratio'] - 0.5)
            future_dev = abs(future_pos - 0.5)

            if future_dev < initial_dev:
                toward_mid += 1

        return toward_mid / len(cases) if len(cases) > 0 else 0

    analyzed_rate = calc_reversion_rate(analyzed_cases, exact_match=True)
    excluded_rate = calc_reversion_rate(excluded_cases, exact_match=False)

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
    1. Baseline: Exclude all cases where exact future quote unavailable (Phase 2)
    2. Pessimistic: Assume excluded cases never revert (0% reversion)
    3. Optimistic: Assume excluded cases revert at same rate as analyzed
    4. Realistic: Use nearest available future quote for excluded cases

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
    """Execute Phase 5 survivorship bias investigation"""

    logger.info("=" * 80)
    logger.info("Phase 5: Survivorship Bias Investigation")
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

    logger.info("\n--- Phase 5.1: Exclusion Reason Taxonomy ---")

    exclusion_results = []
    for year, month in test_months:
        try:
            result = analyze_exclusion_reasons(year, month)
            exclusion_results.append(result)
        except Exception as e:
            logger.error(f"Exclusion taxonomy failed for {year}-{month}: {e}")
            raise

    # Save exclusion taxonomy
    exclusion_output = OUTPUT_DIR / "phase5_exclusion_taxonomy.csv"
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

    logger.info("\n--- Phase 5.2: Survivorship Bias Quantification ---")

    bias_results = []
    for year, month in test_months:
        try:
            result = estimate_survivorship_bias(year, month)
            bias_results.append(result)
        except Exception as e:
            logger.error(f"Bias quantification failed for {year}-{month}: {e}")
            raise

    bias_output = OUTPUT_DIR / "phase5_survivorship_bias.csv"
    pd.DataFrame(bias_results).to_csv(bias_output, index=False)
    logger.info(f"\n✓ Survivorship bias results saved: {bias_output}")

    # =============================================================================
    # Phase 5.3: Sensitivity Analysis
    # =============================================================================

    logger.info("\n--- Phase 5.3: Sensitivity Analysis ---")

    sensitivity_results = []
    for year, month in test_months:
        try:
            result = sensitivity_analysis_exclusions(year, month)
            sensitivity_results.append(result)
        except Exception as e:
            logger.error(f"Sensitivity analysis failed for {year}-{month}: {e}")
            raise

    sensitivity_output = OUTPUT_DIR / "phase5_sensitivity_analysis.csv"
    pd.DataFrame(sensitivity_results).to_csv(sensitivity_output, index=False)
    logger.info(f"\n✓ Sensitivity analysis saved: {sensitivity_output}")

    # =============================================================================
    # Summary Report
    # =============================================================================

    logger.info("\n" + "=" * 80)
    logger.info("Phase 5 Complete - Survivorship Bias Summary")
    logger.info("=" * 80)

    # Average exclusion rate
    avg_exclusion_rate = df_exclusion['exclusion_rate'].mean()
    logger.info(f"\nAverage Exclusion Rate: {avg_exclusion_rate:.1%}")

    # Dominant exclusion reason
    reason_cols = ['end_of_dataset', 'missing_future_quote', 'no_std_quote_match', 'other']
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

    logger.info(f"\n✅ All Phase 5 analyses completed successfully")
    logger.info(f"Results saved to: {OUTPUT_DIR}")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error(f"Phase 5 execution failed: {e}")
        sys.exit(1)
