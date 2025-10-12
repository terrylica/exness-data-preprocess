#!/usr/bin/env python3
"""
Phase 6 Visualization - Data Preparation
Version: 1.0.0
Date: 2025-10-06

Prepares tick data and zero-spread deviation events for interactive visualization.
Resamples to multiple timeframes (5s, 15s, 1m) for multi-granularity analysis.

SLOs:
- Availability: 100% (all data files loaded or fail explicitly)
- Correctness: Exact OHLC resampling, timestamp alignment ±1ms
- Observability: Progress logging per data processing stage
- Maintainability: Pandas resample() only, no custom aggregation

Dependencies:
- Exness EURUSD data (Standard + Raw_Spread variants)
- Phase 6B hot zones CSV
- Phase 6C trading zones JSON
- Phase 6C burst statistics CSV
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
DATA_DIR = Path("/tmp")
OUTPUT_DIR = Path("/tmp")

# Constants
DEVIATION_THRESHOLD = 0.02

class DataPreparationError(Exception):
    """Raised when data preparation fails"""
    pass

def load_month_data(year: str, month: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Load Standard, Raw_Spread data and compute zero-spread deviations.

    Returns:
        (std_df, raw_df, deviations_df)
    """
    month_str = f"{year}-{month}"
    logger.info(f"Loading data: {month_str}")

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
    std_df = std_df.sort_values('Timestamp').reset_index(drop=True)

    logger.info(f"  Standard: {len(std_df):,} ticks")

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
    rs_df = rs_df.sort_values('Timestamp').reset_index(drop=True)

    logger.info(f"  Raw_Spread: {len(rs_df):,} ticks")

    # ASOF merge to align execution prices with quotes
    merged = pd.merge_asof(
        rs_df,
        std_df,
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

    # Compute price (use std_mid for consistency with hot zones)
    deviations['price'] = deviations['std_mid']

    logger.info(f"  Deviations: {len(deviations):,} events")

    return std_df, rs_df, deviations

def resample_to_ohlc(df: pd.DataFrame, timeframe: str, price_col: str = 'std_mid') -> pd.DataFrame:
    """
    Resample tick data to OHLC bars.

    Args:
        df: DataFrame with Timestamp and price columns
        timeframe: Pandas frequency string ('5s', '15s', '1min')
        price_col: Column to use for OHLC (default: 'std_mid')

    Returns:
        DataFrame with OHLC columns
    """
    logger.info(f"  Resampling to {timeframe} bars...")

    df_indexed = df.set_index('Timestamp')

    ohlc = df_indexed[price_col].resample(timeframe).ohlc()
    volume = df_indexed[price_col].resample(timeframe).count()

    ohlc['volume'] = volume
    ohlc = ohlc.dropna().reset_index()

    logger.info(f"    {len(ohlc):,} {timeframe} bars created")

    return ohlc

def calculate_rolling_risk_levels(deviations: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate dynamic risk level (0-5) using rolling windows.

    Risk factors:
    - Rolling enrichment (1H window): Event frequency vs baseline
    - Rolling CV (30min window): Interval variability
    - Rolling burst intensity (15min window): Burst event percentage
    - Local cluster strength (2H window): Events within ±10 pips

    Returns:
        DataFrame with risk_level (0-5 int), rolling metrics columns
    """
    logger.info("\\nCalculating rolling risk levels...")

    # Ensure sorted by timestamp
    deviations = deviations.sort_values('Timestamp').reset_index(drop=True)

    # Calculate baseline event rate (events per hour)
    total_hours = (deviations['Timestamp'].max() - deviations['Timestamp'].min()).total_seconds() / 3600
    baseline_rate = len(deviations) / total_hours
    logger.info(f"  Baseline rate: {baseline_rate:.1f} events/hour")

    # 1H rolling enrichment
    logger.info("  Computing 1H rolling enrichment...")
    deviations_indexed = deviations.set_index('Timestamp')
    rolling_counts = deviations_indexed['price'].rolling('1h').count()
    deviations['rolling_enrichment'] = rolling_counts.values / baseline_rate

    # 30min rolling CV
    logger.info("  Computing 30min rolling CV...")
    rolling_std = deviations_indexed['interval'].rolling('30min').std()
    rolling_mean = deviations_indexed['interval'].rolling('30min').mean()
    deviations['rolling_cv'] = (rolling_std / rolling_mean).values

    # 15min rolling burst intensity
    logger.info("  Computing 15min rolling burst intensity...")
    rolling_burst = deviations_indexed['is_burst'].astype(int).rolling('15min').mean()
    deviations['rolling_burst_pct'] = rolling_burst.values * 100

    # 2H local cluster strength (events within ±10 pips)
    logger.info("  Computing 2H local cluster strength...")
    cluster_strengths = []
    lookback = pd.Timedelta('2H')
    price_threshold = 0.0010  # ±10 pips

    for idx in range(len(deviations)):
        if idx % 10000 == 0:
            logger.info(f"    Progress: {idx:,}/{len(deviations):,}")

        row = deviations.iloc[idx]
        window_start = row['Timestamp'] - lookback

        # Count events in time window within price range
        count = len(deviations[
            (deviations['Timestamp'] >= window_start) &
            (deviations['Timestamp'] <= row['Timestamp']) &
            (abs(deviations['price'] - row['price']) <= price_threshold)
        ])
        cluster_strengths.append(count)

    deviations['local_cluster_strength'] = cluster_strengths

    # Composite score calculation
    logger.info("  Computing composite risk scores...")
    enrichment_score = np.clip(deviations['rolling_enrichment'] / 5, 0, 1)
    cv_score = np.clip(deviations['rolling_cv'] / 200, 0, 1)
    burst_score = np.clip(deviations['rolling_burst_pct'] / 50, 0, 1)
    cluster_score = np.clip(deviations['local_cluster_strength'] / 100, 0, 1)

    composite_score = (enrichment_score + cv_score + burst_score + cluster_score) / 4 * 5

    # Map to risk levels 0-5
    # Handle NaN in composite_score (early events with insufficient rolling data)
    composite_score_filled = composite_score.fillna(0)  # Default to level 0 for cold-start events
    deviations['risk_level'] = pd.cut(
        composite_score_filled,
        bins=[-np.inf, 0.5, 1.0, 2.0, 3.0, 4.0, np.inf],
        labels=[0, 1, 2, 3, 4, 5]
    ).astype(int)

    # Log distribution
    logger.info("  Risk level distribution:")
    for level in range(6):
        count = (deviations['risk_level'] == level).sum()
        pct = count / len(deviations) * 100
        logger.info(f"    Level {level}: {count:,} ({pct:.1f}%)")

    return deviations

def prepare_visualization_data(year: str, month: str) -> Path:
    """
    Prepare all data needed for visualization of one month.

    Returns:
        Path to output parquet file
    """
    month_str = f"{year}-{month}"
    logger.info(f"\n{'='*80}")
    logger.info(f"Preparing Visualization Data: {month_str}")
    logger.info(f"{'='*80}")

    # Load raw data
    std_df, raw_df, deviations = load_month_data(year, month)

    # Resample to multiple timeframes
    logger.info("\nResampling tick data to multiple timeframes...")
    ohlc_5s = resample_to_ohlc(std_df, '5s')
    ohlc_15s = resample_to_ohlc(std_df, '15s')
    ohlc_1m = resample_to_ohlc(std_df, '1min')

    # Load hot zones for this month
    logger.info("\nLoading Phase 6 analysis results...")
    hot_zones_path = OUTPUT_DIR / "phase6b_hot_zones.csv"
    if not hot_zones_path.exists():
        raise FileNotFoundError(f"Missing hot zones: {hot_zones_path}")

    hot_zones_df = pd.read_csv(hot_zones_path)
    hot_zones_month = hot_zones_df[hot_zones_df['month'] == month_str].copy()
    logger.info(f"  Hot zones: {len(hot_zones_month)} for {month_str}")

    # Load trading zones (RED/YELLOW classification)
    trading_zones_path = OUTPUT_DIR / "phase6c_trading_zones.json"
    if not trading_zones_path.exists():
        raise FileNotFoundError(f"Missing trading zones: {trading_zones_path}")

    with open(trading_zones_path) as f:
        trading_zones = json.load(f)
    trading_zones_month = [z for z in trading_zones if z['month'] == month_str]
    logger.info(f"  Trading zones: {len(trading_zones_month)} for {month_str}")

    # Load burst statistics
    burst_stats_path = OUTPUT_DIR / "phase6c_burst_statistics.csv"
    if not burst_stats_path.exists():
        raise FileNotFoundError(f"Missing burst statistics: {burst_stats_path}")

    burst_stats_df = pd.read_csv(burst_stats_path)
    burst_stats_month = burst_stats_df[burst_stats_df['month'] == month_str].iloc[0]
    burst_threshold = burst_stats_month['burst_threshold']

    logger.info(f"  Burst threshold: {burst_threshold:.3f}s")

    # Identify burst periods in deviations (must be done before rolling risk calculation)
    deviations = deviations.sort_values('Timestamp').reset_index(drop=True)
    deviations['interval'] = deviations['Timestamp'].diff().dt.total_seconds()
    deviations['is_short'] = deviations['interval'] < burst_threshold
    deviations['is_burst'] = False

    # Mark bursts (3+ consecutive short intervals)
    for i in range(2, len(deviations)):
        if all(deviations['is_short'].iloc[i-2:i+1]):
            deviations.loc[deviations.index[i-2:i+1], 'is_burst'] = True

    # Calculate dynamic rolling risk levels (requires interval and is_burst columns)
    deviations = calculate_rolling_risk_levels(deviations)

    burst_count = deviations['is_burst'].sum()
    logger.info(f"  Burst events: {burst_count} ({burst_count/len(deviations)*100:.1f}%)")

    # Package all data into dictionary
    viz_data = {
        'metadata': {
            'year': year,
            'month': month,
            'month_str': month_str,
            'n_deviations': int(len(deviations)),
            'n_hot_zones': int(len(hot_zones_month)),
            'burst_threshold': float(burst_threshold),
            'burst_count': int(burst_count),
            'data_range': {
                'start': str(std_df['Timestamp'].min()),
                'end': str(std_df['Timestamp'].max())
            }
        },
        'ohlc_5s': ohlc_5s,
        'ohlc_15s': ohlc_15s,
        'ohlc_1m': ohlc_1m,
        'deviations': deviations[[
            'Timestamp', 'price', 'deviation', 'position_ratio',
            'risk_level', 'interval', 'is_burst',
            'rolling_enrichment', 'rolling_cv', 'rolling_burst_pct', 'local_cluster_strength'
        ]],
        'hot_zones': hot_zones_month,
        'trading_zones': pd.DataFrame(trading_zones_month)
    }

    # Save to parquet
    output_path = OUTPUT_DIR / f"viz_data_{year}_{month}.parquet"

    # Convert to parquet using pyarrow
    logger.info(f"\nSaving visualization data...")

    # Save each dataframe separately with naming convention
    ohlc_5s.to_parquet(OUTPUT_DIR / f"viz_{month_str}_ohlc_5s.parquet")
    ohlc_15s.to_parquet(OUTPUT_DIR / f"viz_{month_str}_ohlc_15s.parquet")
    ohlc_1m.to_parquet(OUTPUT_DIR / f"viz_{month_str}_ohlc_1m.parquet")
    deviations.to_parquet(OUTPUT_DIR / f"viz_{month_str}_deviations.parquet")
    hot_zones_month.to_parquet(OUTPUT_DIR / f"viz_{month_str}_hot_zones.parquet")
    pd.DataFrame(trading_zones_month).to_parquet(OUTPUT_DIR / f"viz_{month_str}_trading_zones.parquet")

    # Save metadata as JSON
    metadata_path = OUTPUT_DIR / f"viz_{month_str}_metadata.json"
    with open(metadata_path, 'w') as f:
        json.dump(viz_data['metadata'], f, indent=2)

    logger.info(f"  ✓ Saved: viz_{month_str}_*.parquet")
    logger.info(f"  ✓ Saved: {metadata_path}")

    logger.info(f"\n{'='*80}")
    logger.info(f"✅ Data preparation complete: {month_str}")
    logger.info(f"{'='*80}")

    return metadata_path

def main():
    """Execute data preparation for visualization"""

    import argparse
    parser = argparse.ArgumentParser(description='Prepare visualization data for zero-spread deviations')
    parser.add_argument('--year', type=str, required=True, help='Year (e.g., 2024)')
    parser.add_argument('--month', type=str, required=True, help='Month (01-12)')

    args = parser.parse_args()

    try:
        metadata_path = prepare_visualization_data(args.year, args.month)
        logger.info(f"\n✅ Success! Metadata saved to: {metadata_path}")
        logger.info(f"\nNext step: Run generate_interactive_dashboard.py --year {args.year} --month {args.month}")
    except Exception as e:
        logger.error(f"\n❌ Data preparation failed: {e}")
        raise

if __name__ == "__main__":
    main()
