#!/usr/bin/env python3
"""
Phase 6C: Combined Pattern Analysis
Version: 1.0.0
Date: 2025-10-05

Analyzes interaction between temporal and price patterns:
- Conditional inter-arrival times (in/out of hot zones)
- Burst detection and prediction
- Trading zone classification (RED/YELLOW/GREEN)

SLOs:
- Availability: 100% (all analyses complete or fail explicitly)
- Correctness: Sticky zone <70% baseline, burst persistence >2×
- Observability: All zones classified with rationale logged
- Maintainability: Out-of-the-box pandas/numpy only

Dependencies:
- Phase 6A results (interval statistics)
- Phase 6B results (hot zones)
- Exness EURUSD data for deviation timestamps + prices
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np
import zipfile
import logging
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
HOT_ZONE_TOLERANCE = 0.0005  # 5 pips

# Error classes
class InsufficientDataError(Exception):
    """Raised when insufficient data for analysis"""
    pass

# =============================================================================
# Data Loading
# =============================================================================

def load_month_deviations_with_prices(year: str, month: str) -> pd.DataFrame:
    """Load zero-spread deviations with timestamps and prices"""

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
    rs_df['raw_spread'] = rs_df['raw_ask'] - rs_df['raw_bid']
    rs_df['raw_mid'] = (rs_df['raw_bid'] + rs_df['raw_ask']) / 2

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

    # Add price
    deviations['price'] = deviations['std_mid']

    # Calculate intervals
    deviations = deviations.sort_values('Timestamp').reset_index(drop=True)
    deviations['interval'] = deviations['Timestamp'].diff().dt.total_seconds()

    logger.info(f"  {len(deviations):,} deviations loaded")

    return deviations[['Timestamp', 'price', 'deviation', 'interval']]

def load_hot_zones() -> pd.DataFrame:
    """Load hot zones from Phase 6B"""

    hot_zones_path = OUTPUT_DIR / "phase6b_hot_zones.csv"
    if not hot_zones_path.exists():
        raise FileNotFoundError(
            f"Phase 6B hot zones not found: {hot_zones_path}. Run Phase 6B first."
        )

    hot_zones = pd.read_csv(hot_zones_path)
    logger.info(f"Loaded {len(hot_zones)} hot zones from Phase 6B")

    return hot_zones

# =============================================================================
# Conditional Interval Analysis
# =============================================================================

def analyze_conditional_intervals(deviations: pd.DataFrame, hot_zone_prices: list) -> dict:
    """
    Compare inter-arrival times in vs out of hot zones.

    Returns dict with conditional statistics.
    """
    # Classify each deviation as in/out of hot zone
    deviations = deviations.copy()
    deviations['in_hot_zone'] = deviations['price'].apply(
        lambda p: any(abs(p - hz) < HOT_ZONE_TOLERANCE for hz in hot_zone_prices)
    )

    # Get intervals (skip first row which has NaN interval)
    intervals_all = deviations['interval'].dropna()

    in_zone = deviations[deviations['in_hot_zone']]['interval'].dropna()
    out_zone = deviations[~deviations['in_hot_zone']]['interval'].dropna()

    if len(in_zone) < 5 or len(out_zone) < 5:
        return {
            'in_zone_mean': np.nan,
            'in_zone_cv': np.nan,
            'in_zone_count': len(in_zone),
            'out_zone_mean': np.nan,
            'out_zone_cv': np.nan,
            'out_zone_count': len(out_zone),
            'interval_ratio': np.nan,
            'sticky_zone_effect': False
        }

    in_zone_mean = in_zone.mean()
    in_zone_cv = in_zone.std() / in_zone_mean if in_zone_mean > 0 else np.nan

    out_zone_mean = out_zone.mean()
    out_zone_cv = out_zone.std() / out_zone_mean if out_zone_mean > 0 else np.nan

    interval_ratio = in_zone_mean / out_zone_mean if out_zone_mean > 0 else np.nan

    # Sticky zone effect: intervals shorten by >30% in hot zones
    sticky_zone_effect = interval_ratio < 0.7

    return {
        'in_zone_mean': float(in_zone_mean),
        'in_zone_cv': float(in_zone_cv),
        'in_zone_count': int(len(in_zone)),
        'out_zone_mean': float(out_zone_mean),
        'out_zone_cv': float(out_zone_cv),
        'out_zone_count': int(len(out_zone)),
        'interval_ratio': float(interval_ratio),
        'sticky_zone_effect': sticky_zone_effect
    }

# =============================================================================
# Burst Detection
# =============================================================================

def detect_bursts(deviations: pd.DataFrame) -> dict:
    """
    Detect bursts (3+ consecutive intervals below 25th percentile).

    Returns dict with burst statistics.
    """
    intervals = deviations['interval'].dropna()

    if len(intervals) < 10:
        return {
            'burst_threshold': np.nan,
            'n_bursts': 0,
            'burst_rate': 0.0,
            'p_burst_given_burst': np.nan,
            'p_burst_given_quiet': np.nan,
            'burst_persistence': np.nan,
            'bursts_predict_bursts': False
        }

    # Define burst threshold (25th percentile)
    burst_threshold = intervals.quantile(0.25)

    # Mark bursts (3+ consecutive short intervals)
    deviations = deviations.copy()
    deviations['is_short'] = deviations['interval'] < burst_threshold
    deviations['is_burst'] = False

    for i in range(2, len(deviations)):
        if all(deviations['is_short'].iloc[i-2:i+1]):
            deviations.loc[deviations.index[i-2:i+1], 'is_burst'] = True

    n_bursts = deviations['is_burst'].sum()
    burst_rate = n_bursts / len(deviations)

    # Transition probabilities
    deviations['next_is_burst'] = deviations['is_burst'].shift(-1)

    burst_events = deviations[deviations['is_burst']]
    quiet_events = deviations[~deviations['is_burst']]

    if len(burst_events) > 0 and len(quiet_events) > 0:
        p_burst_given_burst = burst_events['next_is_burst'].mean()
        p_burst_given_quiet = quiet_events['next_is_burst'].mean()

        burst_persistence = (
            p_burst_given_burst / p_burst_given_quiet
            if p_burst_given_quiet > 0 else np.nan
        )

        bursts_predict_bursts = burst_persistence > 2.0
    else:
        p_burst_given_burst = np.nan
        p_burst_given_quiet = np.nan
        burst_persistence = np.nan
        bursts_predict_bursts = False

    return {
        'burst_threshold': float(burst_threshold),
        'n_bursts': int(n_bursts),
        'burst_rate': float(burst_rate),
        'p_burst_given_burst': float(p_burst_given_burst) if not pd.isna(p_burst_given_burst) else 0.0,
        'p_burst_given_quiet': float(p_burst_given_quiet) if not pd.isna(p_burst_given_quiet) else 0.0,
        'burst_persistence': float(burst_persistence) if not pd.isna(burst_persistence) else 0.0,
        'bursts_predict_bursts': bursts_predict_bursts
    }

# =============================================================================
# Trading Zone Classification
# =============================================================================

def classify_trading_zones(hot_zones: pd.DataFrame, month_deviations: dict) -> list:
    """
    Classify each hot zone as RED/YELLOW/GREEN based on combined criteria.

    Criteria:
    - RED: High enrichment (>3×) AND high burstiness (CV > 2.0)
    - YELLOW: Moderate enrichment (>2×) OR moderate burstiness (CV > 1.5)
    - GREEN: Low risk

    Args:
        hot_zones: DataFrame of hot zones for this month
        month_deviations: Dict containing deviations data

    Returns:
        List of classified trading zones
    """
    trading_zones = []

    for _, zone in hot_zones.iterrows():
        price_level = zone['price_level']
        enrichment = zone['enrichment']

        # Get CV for this zone (simplified: use overall CV as proxy)
        # In production, would calculate zone-specific CV
        zone_cv = month_deviations.get('in_zone_cv', 1.0)

        # Classify
        if enrichment > 3.0 and zone_cv > 2.0:
            risk_level = 'RED'
            recommendation = 'AVOID - High deviation frequency + burst behavior'
        elif enrichment > 2.0 or zone_cv > 1.5:
            risk_level = 'YELLOW'
            recommendation = 'CAUTION - Reduce size 50%, widen stops'
        else:
            risk_level = 'GREEN'
            recommendation = 'NORMAL - Standard risk parameters'

        trading_zones.append({
            'price_level': price_level,
            'risk_level': risk_level,
            'enrichment': enrichment,
            'cv': zone_cv,
            'recommendation': recommendation
        })

    return trading_zones

# =============================================================================
# Main Analysis
# =============================================================================

def analyze_month(year: str, month: str, hot_zones_all: pd.DataFrame) -> tuple:
    """
    Run Phase 6C analysis for one month.

    Returns:
        (conditional_result, burst_result, trading_zones)
    """
    month_str = f"{year}-{month}"

    # Load deviations
    deviations = load_month_deviations_with_prices(year, month)

    # Get hot zones for this month
    month_hot_zones = hot_zones_all[hot_zones_all['month'] == month_str]

    if len(month_hot_zones) == 0:
        logger.warning(f"  No hot zones for {month_str}, skipping conditional analysis")
        return None, None, []

    hot_zone_prices = month_hot_zones['price_level'].tolist()

    # Conditional interval analysis
    conditional = analyze_conditional_intervals(deviations, hot_zone_prices)
    conditional['month'] = month_str

    logger.info(f"  Conditional intervals: in_zone={conditional['in_zone_mean']:.1f}s, "
                f"out_zone={conditional['out_zone_mean']:.1f}s, "
                f"ratio={conditional['interval_ratio']:.2f}")

    if conditional['sticky_zone_effect']:
        logger.info(f"    ✅ Sticky zone effect detected (ratio < 0.7)")

    # Burst analysis
    burst = detect_bursts(deviations)
    burst['month'] = month_str

    logger.info(f"  Bursts: {burst['burst_rate']:.1%} of events, "
                f"persistence={burst['burst_persistence']:.2f}×")

    if burst['bursts_predict_bursts']:
        logger.info(f"    ✅ Bursts predict bursts (persistence > 2×)")

    # Trading zone classification
    trading_zones = classify_trading_zones(month_hot_zones, conditional)

    for zone in trading_zones:
        logger.info(f"  Zone {zone['price_level']:.4f}: {zone['risk_level']} "
                    f"(enrichment={zone['enrichment']:.2f}×)")

    return conditional, burst, trading_zones

def main():
    """Execute Phase 6C: Combined Pattern Analysis"""

    logger.info("=" * 80)
    logger.info("Phase 6C: Combined Pattern Analysis")
    logger.info("=" * 80)

    # Load hot zones from Phase 6B
    hot_zones = load_hot_zones()

    # All 16 months
    months = [
        ('2024', '01'), ('2024', '02'), ('2024', '03'), ('2024', '04'),
        ('2024', '05'), ('2024', '06'), ('2024', '07'), ('2024', '08'),
        ('2025', '01'), ('2025', '02'), ('2025', '03'), ('2025', '04'),
        ('2025', '05'), ('2025', '06'), ('2025', '07'), ('2025', '08')
    ]

    all_conditional = []
    all_burst = []
    all_trading_zones = []

    for year, month in months:
        try:
            conditional, burst, trading_zones = analyze_month(year, month, hot_zones)

            if conditional is not None:
                all_conditional.append(conditional)
            if burst is not None:
                all_burst.append(burst)
            if trading_zones:
                for zone in trading_zones:
                    zone['month'] = f"{year}-{month}"
                    all_trading_zones.append(zone)

        except Exception as e:
            logger.error(f"Analysis failed for {year}-{month}: {e}")
            raise

    # Save results
    if all_conditional:
        conditional_df = pd.DataFrame(all_conditional)
        output_conditional = OUTPUT_DIR / "phase6c_conditional_intervals.csv"
        conditional_df.to_csv(output_conditional, index=False)
        logger.info(f"\n✓ Conditional intervals saved: {output_conditional}")

    if all_burst:
        burst_df = pd.DataFrame(all_burst)
        output_burst = OUTPUT_DIR / "phase6c_burst_statistics.csv"
        burst_df.to_csv(output_burst, index=False)
        logger.info(f"✓ Burst statistics saved: {output_burst}")

    if all_trading_zones:
        output_zones = OUTPUT_DIR / "phase6c_trading_zones.json"
        with open(output_zones, 'w') as f:
            json.dump(all_trading_zones, f, indent=2)
        logger.info(f"✓ Trading zones saved: {output_zones}")

    # =============================================================================
    # Overall Summary
    # =============================================================================

    logger.info("\n" + "=" * 80)
    logger.info("Phase 6C Complete - Combined Pattern Summary")
    logger.info("=" * 80)

    if all_conditional:
        sticky_rate = sum(c['sticky_zone_effect'] for c in all_conditional) / len(all_conditional)
        logger.info(f"\nSticky zone effect: {sticky_rate:.0%} of months")

        avg_ratio = np.mean([c['interval_ratio'] for c in all_conditional if not pd.isna(c['interval_ratio'])])
        logger.info(f"Average interval ratio (in/out): {avg_ratio:.2f}")

    if all_burst:
        burst_predict_rate = sum(b['bursts_predict_bursts'] for b in all_burst) / len(all_burst)
        logger.info(f"Burst prediction: {burst_predict_rate:.0%} of months")

        avg_persistence = np.mean([b['burst_persistence'] for b in all_burst if not pd.isna(b['burst_persistence'])])
        logger.info(f"Average burst persistence: {avg_persistence:.2f}×")

    if all_trading_zones:
        zones_df = pd.DataFrame(all_trading_zones)
        risk_counts = zones_df['risk_level'].value_counts()

        logger.info(f"\nTrading Zone Classification:")
        for level in ['RED', 'YELLOW', 'GREEN']:
            count = risk_counts.get(level, 0)
            logger.info(f"  {level}: {count} zones")

        # Recurring RED zones (appear in multiple months)
        if 'RED' in risk_counts:
            red_zones = zones_df[zones_df['risk_level'] == 'RED']
            # Group by price (round to 10 pips)
            red_zones['price_rounded'] = (red_zones['price_level'] * 100).round() / 100
            recurring_red = red_zones.groupby('price_rounded').size()
            recurring_red = recurring_red[recurring_red >= 3].sort_values(ascending=False)

            if len(recurring_red) > 0:
                logger.info(f"\nRecurring RED zones (≥3 months):")
                for price, freq in recurring_red.head(5).items():
                    logger.info(f"  {price:.4f}: {freq}/16 months")

    logger.info(f"\n✅ Phase 6C completed successfully")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error(f"Phase 6C execution failed: {e}")
        sys.exit(1)
