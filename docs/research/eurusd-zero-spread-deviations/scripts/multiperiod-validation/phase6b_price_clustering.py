#!/usr/bin/env python3
"""
Phase 6B: Price Clustering Analysis
Version: 1.0.0
Date: 2025-10-05

Analyzes spatial patterns of zero-spread deviations:
- Price level clustering (chi-square test vs uniform)
- Hot zone identification (>2× baseline frequency)
- Round number bias (.00, .50 levels)
- Technical level overlap (daily highs/lows)
- Extreme deviation price distribution

SLOs:
- Availability: 100% (all 16 months processed or fail explicitly)
- Correctness: Cluster p < 0.05, enrichment >2× for hot zones
- Observability: All clusters logged with confidence levels
- Maintainability: Out-of-the-box scipy/pandas only

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
DATA_DIR = Path("/tmp")
OUTPUT_DIR = Path("/tmp")

# Constants
DEVIATION_THRESHOLD = 0.02
BIN_WIDTH = 0.0005  # 5 pips
ROUND_LEVEL_PIPS = 50  # Test for .00, .50 levels (50 pips)
TECHNICAL_TOLERANCE = 0.0010  # 10 pips

# Error classes
class InsufficientDataError(Exception):
    """Raised when insufficient data for analysis"""
    pass

class SLOViolationError(Exception):
    """Raised when SLO is violated"""
    pass

# =============================================================================
# Data Loading (Reuse Phase 2 Logic)
# =============================================================================

def load_month_data(year: str, month: str) -> tuple:
    """
    Load zero-spread deviations + Standard data for a month.

    Returns:
        (deviations_df, std_df_full)
    """
    month_str = f"{year}-{month}"
    logger.info(f"Loading data: {month_str}")

    # Load Standard
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

    # Load Raw_Spread
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

    # ASOF merge
    merged = pd.merge_asof(
        rs_df.sort_values('Timestamp'),
        std_df.sort_values('Timestamp'),
        on='Timestamp',
        direction='backward',
        tolerance=pd.Timedelta(seconds=10)
    )

    merged = merged.dropna().reset_index(drop=True)

    # Position ratio
    merged['position_ratio'] = (
        (merged['raw_mid'] - merged['std_bid']) /
        (merged['std_ask'] - merged['std_bid'])
    )

    # Zero-spread deviations
    zero_spread = merged[merged['raw_spread'] <= 0.00001].copy()
    zero_spread['deviation'] = np.abs(zero_spread['position_ratio'] - 0.5)
    deviations = zero_spread[zero_spread['deviation'] > DEVIATION_THRESHOLD].copy()

    # Add price column (Standard midpoint)
    deviations['price'] = deviations['std_mid']

    if len(deviations) < 1000:
        raise InsufficientDataError(
            f"{month_str}: Only {len(deviations)} deviations (need ≥1000)"
        )

    logger.info(f"  {len(deviations):,} deviations loaded")

    return deviations, std_df

# =============================================================================
# Price Histogram Analysis
# =============================================================================

def analyze_price_distribution(deviations: pd.DataFrame) -> dict:
    """
    Bin prices and test for clustering.

    Returns dict with histogram data and chi-square test results.
    """
    prices = deviations['price'].values

    # Create bins
    price_min = prices.min()
    price_max = prices.max()

    bins = np.arange(
        np.floor(price_min / BIN_WIDTH) * BIN_WIDTH,
        np.ceil(price_max / BIN_WIDTH) * BIN_WIDTH + BIN_WIDTH,
        BIN_WIDTH
    )

    # Histogram
    counts, bin_edges = np.histogram(prices, bins=bins)

    # Prepare histogram dataframe
    hist_df = pd.DataFrame({
        'bin_start': bin_edges[:-1],
        'bin_end': bin_edges[1:],
        'event_count': counts
    })

    hist_df['bin_mid'] = (hist_df['bin_start'] + hist_df['bin_end']) / 2

    # Chi-square test vs uniform distribution
    observed = counts[counts > 0]  # Only non-zero bins
    expected = np.full_like(observed, observed.mean(), dtype=float)

    if len(observed) < 2:
        raise InsufficientDataError("Need ≥2 non-empty bins for chi-square test")

    chi2, p_value = stats.chisquare(observed, expected)

    clustering_detected = bool(p_value < 0.05)

    logger.info(f"  Price clustering: χ²={chi2:.2f}, p={p_value:.4f}")
    if clustering_detected:
        logger.info(f"    ✅ Clustering detected (p < 0.05)")
    else:
        logger.info(f"    ❌ No clustering (p ≥ 0.05)")

    return {
        'histogram': hist_df,
        'chi2_statistic': float(chi2),
        'chi2_pvalue': float(p_value),
        'clustering_detected': clustering_detected,
        'n_bins': len(bins) - 1,
        'n_nonempty_bins': int((counts > 0).sum())
    }

# =============================================================================
# Hot Zone Identification
# =============================================================================

def identify_hot_zones(hist_df: pd.DataFrame, threshold_multiplier: float = 2.0) -> pd.DataFrame:
    """
    Identify price bins with >threshold_multiplier × baseline frequency.

    Returns DataFrame of hot zones.
    """
    baseline = hist_df['event_count'].mean()
    hot_zones = hist_df[hist_df['event_count'] > threshold_multiplier * baseline].copy()

    hot_zones['enrichment'] = hot_zones['event_count'] / baseline
    hot_zones['significance'] = hot_zones['enrichment'].apply(
        lambda x: 'high' if x > 3 else 'moderate'
    )

    # Rename for output
    hot_zones = hot_zones.rename(columns={'bin_mid': 'price_level'})
    hot_zones = hot_zones[['price_level', 'event_count', 'enrichment', 'significance']]

    logger.info(f"  Hot zones: {len(hot_zones)} levels (>{threshold_multiplier}× baseline)")

    for _, zone in hot_zones.iterrows():
        logger.info(f"    {zone['price_level']:.4f}: {zone['enrichment']:.2f}× ({zone['significance']})")

    return hot_zones

# =============================================================================
# Round Number Bias Test
# =============================================================================

def test_round_number_bias(deviations: pd.DataFrame) -> dict:
    """
    Test if deviations cluster at round numbers (.00, .50 levels).

    Returns dict with bias statistics.
    """
    # Round to nearest 50 pips
    deviations['price_rounded'] = (
        (deviations['price'] * 10000 / ROUND_LEVEL_PIPS).round() * ROUND_LEVEL_PIPS / 10000
    )

    # Count events at exact round levels vs all
    total_events = len(deviations)

    # Identify round level events
    # A price is "round" if it's exactly at .00 or .50 level
    deviations['is_round'] = (
        ((deviations['price'] * 10000) % ROUND_LEVEL_PIPS).abs() < 0.5
    )

    round_events = deviations['is_round'].sum()
    round_frequency = round_events / total_events

    # Expected frequency (50 pips spacing, so 2% of prices are round)
    expected_frequency = 1 / ROUND_LEVEL_PIPS

    bias_ratio = round_frequency / expected_frequency if expected_frequency > 0 else 0

    # Binomial test
    binom_result = stats.binomtest(
        round_events,
        total_events,
        expected_frequency,
        alternative='greater'
    )
    binom_pvalue = binom_result.pvalue

    round_bias = bool(bias_ratio > 1.5 and binom_pvalue < 0.05)

    logger.info(f"  Round number bias: {round_frequency:.1%} (expected {expected_frequency:.1%})")
    logger.info(f"    Bias ratio: {bias_ratio:.2f}×, p={binom_pvalue:.4f}")

    if round_bias:
        logger.info(f"    ✅ Significant round number bias")
    else:
        logger.info(f"    ❌ No significant round number bias")

    return {
        'total_events': total_events,
        'round_events': int(round_events),
        'round_frequency': float(round_frequency),
        'expected_frequency': float(expected_frequency),
        'bias_ratio': float(bias_ratio),
        'binom_pvalue': float(binom_pvalue),
        'round_bias': round_bias
    }

# =============================================================================
# Technical Level Overlap
# =============================================================================

def analyze_technical_overlap(deviations: pd.DataFrame, std_df: pd.DataFrame) -> dict:
    """
    Check if deviations overlap with daily highs/lows (support/resistance).

    Returns dict with overlap statistics.
    """
    # Calculate daily extremes
    std_df_copy = std_df.copy()
    std_df_copy['date'] = std_df_copy['Timestamp'].dt.date

    daily_extremes = std_df_copy.groupby('date').agg({
        'std_bid': 'min',  # Daily support
        'std_ask': 'max'   # Daily resistance
    })

    # For each deviation, check if near daily extremes
    deviations = deviations.copy()
    deviations['date'] = deviations['Timestamp'].dt.date
    deviations['near_support'] = False
    deviations['near_resistance'] = False

    for date in deviations['date'].unique():
        if date not in daily_extremes.index:
            continue

        support = daily_extremes.loc[date, 'std_bid']
        resistance = daily_extremes.loc[date, 'std_ask']

        mask = deviations['date'] == date
        deviations.loc[mask, 'near_support'] = (
            (deviations.loc[mask, 'price'] - support).abs() < TECHNICAL_TOLERANCE
        )
        deviations.loc[mask, 'near_resistance'] = (
            (deviations.loc[mask, 'price'] - resistance).abs() < TECHNICAL_TOLERANCE
        )

    near_technical = (deviations['near_support'] | deviations['near_resistance']).sum()
    overlap_rate = near_technical / len(deviations)

    # Random expectation: ~10 pips tolerance / typical daily range (~100 pips) ≈ 10%
    expected_rate = 0.10
    technical_overlap = bool(overlap_rate > 0.15)

    logger.info(f"  Technical overlap: {overlap_rate:.1%} (expected ~{expected_rate:.1%})")

    if technical_overlap:
        logger.info(f"    ✅ Significant overlap with daily extremes")
    else:
        logger.info(f"    ❌ No significant overlap")

    return {
        'total_deviations': len(deviations),
        'near_support': int(deviations['near_support'].sum()),
        'near_resistance': int(deviations['near_resistance'].sum()),
        'near_technical': int(near_technical),
        'overlap_rate': float(overlap_rate),
        'expected_rate': float(expected_rate),
        'technical_overlap': technical_overlap
    }

# =============================================================================
# Extreme Deviation Analysis
# =============================================================================

def analyze_extreme_deviation_prices(deviations: pd.DataFrame) -> dict:
    """
    Test if extreme deviations (>2σ) have different price distribution.

    Returns dict with KS test results.
    """
    mean_dev = deviations['deviation'].mean()
    std_dev = deviations['deviation'].std()

    threshold = mean_dev + 2 * std_dev

    extreme = deviations[deviations['deviation'] > threshold]
    normal = deviations[deviations['deviation'] <= threshold]

    if len(extreme) < 10 or len(normal) < 10:
        logger.warning(f"  Extreme deviation test: insufficient data")
        return {
            'n_extreme': len(extreme),
            'n_normal': len(normal),
            'extreme_price_different': False,
            'ks_statistic': np.nan,
            'ks_pvalue': np.nan
        }

    # KS test
    ks_stat, ks_pvalue = stats.ks_2samp(extreme['price'], normal['price'])

    extreme_different = bool(ks_pvalue < 0.05)

    logger.info(f"  Extreme deviation prices: KS={ks_stat:.3f}, p={ks_pvalue:.4f}")

    if extreme_different:
        logger.info(f"    ✅ Extreme deviations have different price distribution")
    else:
        logger.info(f"    ❌ No difference in price distribution")

    return {
        'n_extreme': len(extreme),
        'n_normal': len(normal),
        'extreme_threshold': float(threshold),
        'extreme_price_different': extreme_different,
        'ks_statistic': float(ks_stat),
        'ks_pvalue': float(ks_pvalue)
    }

# =============================================================================
# Main Analysis
# =============================================================================

def analyze_month(year: str, month: str) -> tuple:
    """
    Run full Phase 6B analysis for one month.

    Returns:
        (month_summary, histogram_df, hot_zones_df)
    """
    month_str = f"{year}-{month}"

    # Load data
    deviations, std_df = load_month_data(year, month)

    # Price distribution analysis
    dist_result = analyze_price_distribution(deviations)
    hist_df = dist_result['histogram']

    # Hot zones
    hot_zones = identify_hot_zones(hist_df)

    # Round number bias
    round_bias = test_round_number_bias(deviations)

    # Technical overlap
    tech_overlap = analyze_technical_overlap(deviations, std_df)

    # Extreme deviation prices
    extreme_analysis = analyze_extreme_deviation_prices(deviations)

    # Combine summary
    summary = {
        'month': month_str,
        'n_deviations': len(deviations),
        'price_min': float(deviations['price'].min()),
        'price_max': float(deviations['price'].max()),
        'chi2_statistic': dist_result['chi2_statistic'],
        'chi2_pvalue': dist_result['chi2_pvalue'],
        'clustering_detected': dist_result['clustering_detected'],
        'n_bins': dist_result['n_bins'],
        'n_hot_zones': len(hot_zones),
        **round_bias,
        **tech_overlap,
        **extreme_analysis
    }

    # Add month column to dataframes
    hist_df['month'] = month_str
    hot_zones['month'] = month_str

    return summary, hist_df, hot_zones

def main():
    """Execute Phase 6B: Price Clustering Analysis"""

    logger.info("=" * 80)
    logger.info("Phase 6B: Price Clustering Analysis")
    logger.info("=" * 80)

    # All 16 months
    months = [
        ('2024', '01'), ('2024', '02'), ('2024', '03'), ('2024', '04'),
        ('2024', '05'), ('2024', '06'), ('2024', '07'), ('2024', '08'),
        ('2025', '01'), ('2025', '02'), ('2025', '03'), ('2025', '04'),
        ('2025', '05'), ('2025', '06'), ('2025', '07'), ('2025', '08')
    ]

    all_summaries = []
    all_histograms = []
    all_hot_zones = []

    for year, month in months:
        try:
            summary, hist_df, hot_zones = analyze_month(year, month)
            all_summaries.append(summary)
            all_histograms.append(hist_df)
            all_hot_zones.append(hot_zones)
        except Exception as e:
            logger.error(f"Analysis failed for {year}-{month}: {e}")
            raise

    # Save results
    summary_df = pd.DataFrame(all_summaries)
    histogram_df = pd.concat(all_histograms, ignore_index=True)
    hot_zones_df = pd.concat(all_hot_zones, ignore_index=True)

    output_summary = OUTPUT_DIR / "phase6b_clustering_summary.json"
    with open(output_summary, 'w') as f:
        json.dump(all_summaries, f, indent=2)

    output_histogram = OUTPUT_DIR / "phase6b_price_histogram.csv"
    histogram_df.to_csv(output_histogram, index=False)

    output_hot_zones = OUTPUT_DIR / "phase6b_hot_zones.csv"
    hot_zones_df.to_csv(output_hot_zones, index=False)

    logger.info(f"\n✓ Clustering summary saved: {output_summary}")
    logger.info(f"✓ Price histogram saved: {output_histogram}")
    logger.info(f"✓ Hot zones saved: {output_hot_zones}")

    # =============================================================================
    # Overall Summary
    # =============================================================================

    logger.info("\n" + "=" * 80)
    logger.info("Phase 6B Complete - Price Clustering Summary")
    logger.info("=" * 80)

    clustering_rate = summary_df['clustering_detected'].mean()
    logger.info(f"\nClustering detected: {clustering_rate:.0%} of months ({summary_df['clustering_detected'].sum()}/16)")

    avg_hot_zones = summary_df['n_hot_zones'].mean()
    logger.info(f"Average hot zones per month: {avg_hot_zones:.1f}")

    round_bias_rate = summary_df['round_bias'].mean()
    logger.info(f"Round number bias: {round_bias_rate:.0%} of months")

    tech_overlap_rate = summary_df['technical_overlap'].mean()
    logger.info(f"Technical overlap: {tech_overlap_rate:.0%} of months")

    # Aggregate hot zones across all months
    if len(hot_zones_df) > 0:
        # Group by price level (round to 10 pips for clustering)
        hot_zones_df['price_rounded'] = (hot_zones_df['price_level'] * 100).round() / 100

        recurring_zones = hot_zones_df.groupby('price_rounded').agg({
            'month': 'count',
            'enrichment': 'mean'
        }).rename(columns={'month': 'frequency'})

        recurring_zones = recurring_zones[recurring_zones['frequency'] >= 3].sort_values('frequency', ascending=False)

        logger.info(f"\nRecurring hot zones (≥3 months):")
        for price, row in recurring_zones.head(10).iterrows():
            logger.info(f"  {price:.4f}: {row['frequency']}/16 months, avg enrichment {row['enrichment']:.2f}×")

    logger.info(f"\n✅ Phase 6B completed successfully")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error(f"Phase 6B execution failed: {e}")
        sys.exit(1)
