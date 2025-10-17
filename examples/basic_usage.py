"""
Basic usage examples for exness-data-preprocess v2.0.0.

This script demonstrates the unified single-file architecture:
1. Initial download and incremental updates
2. Querying OHLC data with date ranges
3. Querying raw tick data with filters
4. Getting data coverage information

Architecture v2.0.0:
- One DuckDB file per instrument (eurusd.duckdb, not monthly files)
- Dual-variant storage (Raw_Spread + Standard) for Phase7
- Automatic gap detection and incremental updates
- 30-column (v1.6.0) OHLC schema with dual spreads, normalized metrics, timezone/session tracking, holiday tracking, and 10 global exchange sessions with trading hour detection
"""

from pathlib import Path

import exness_data_preprocess as edp

# Optional: Configure base directory (defaults to ~/eon/exness-data/)
BASE_DIR = Path.home() / "eon" / "exness-data"

# ============================================================================
# Example 1: Initial Multi-Year Download
# ============================================================================
print("=" * 80)
print("Example 1: Initial Download (3-Year History)")
print("=" * 80)

# Download 3 years of EURUSD data (automatic gap detection)
# This will:
#   1. Create eurusd.duckdb (single file)
#   2. Download missing months from start_date to present
#   3. Store dual variants (Raw_Spread + Standard)
#   4. Generate Phase7 30-column (v1.6.0) OHLC
processor = edp.ExnessDataProcessor(base_dir=BASE_DIR)

result = processor.update_data(
    pair="EURUSD",
    start_date="2022-01-01",  # 3-year history
    delete_zip=True,
)

print("\n✅ Initial download completed:")
print(f"   Database:      {result['duckdb_path']}")
print(f"   Months added:  {result['months_added']}")
print(f"   Raw ticks:     {result['raw_ticks_added']:,}")
print(f"   Standard ticks: {result['standard_ticks_added']:,}")
print(f"   OHLC bars:     {result['ohlc_bars']:,}")
print(f"   Database size: {result['duckdb_size_mb']:.2f} MB")

# ============================================================================
# Example 2: Incremental Update (Only New Data)
# ============================================================================
print("\n" + "=" * 80)
print("Example 2: Incremental Update")
print("=" * 80)

# Run again - only downloads new months since last update
result = processor.update_data(
    pair="EURUSD",
    start_date="2022-01-01",
)

print("\n✅ Incremental update completed:")
print(f"   Months added:  {result['months_added']} (0 if up to date)")
print(f"   Database size: {result['duckdb_size_mb']:.2f} MB")

# ============================================================================
# Example 3: Check Data Coverage
# ============================================================================
print("\n" + "=" * 80)
print("Example 3: Check Data Coverage")
print("=" * 80)

coverage = processor.get_data_coverage("EURUSD")

print("\n📊 EURUSD Coverage:")
print(f"   Database exists: {coverage['database_exists']}")
print(f"   Raw_Spread ticks: {coverage['raw_spread_ticks']:,}")
print(f"   Standard ticks:  {coverage['standard_ticks']:,}")
print(f"   OHLC bars:       {coverage['ohlc_bars']:,}")
print(f"   Date range:      {coverage['earliest_date']} to {coverage['latest_date']}")
print(f"   Days covered:    {coverage['date_range_days']}")
print(f"   Database size:   {coverage['duckdb_size_mb']:.2f} MB")

# ============================================================================
# Example 4: Query OHLC Data (Multiple Timeframes)
# ============================================================================
print("\n" + "=" * 80)
print("Example 4: Query OHLC Data at Different Timeframes")
print("=" * 80)

# Query 1-minute bars for January 2024
df_1m = processor.query_ohlc(
    pair="EURUSD",
    timeframe="1m",
    start_date="2024-01-01",
    end_date="2024-01-31",
)
print(f"\n1-minute bars (Jan 2024):   {len(df_1m):,} rows")
print(f"Columns: {list(df_1m.columns)}")
print(df_1m.head(3))

# Query 1-hour bars for Q1 2024 (resampled on-demand)
df_1h = processor.query_ohlc(
    pair="EURUSD",
    timeframe="1h",
    start_date="2024-01-01",
    end_date="2024-03-31",
)
print(f"\n1-hour bars (Q1 2024):      {len(df_1h):,} rows")
print(df_1h.head(3))

# Query 1-day bars for entire 2024 (resampled on-demand)
df_1d = processor.query_ohlc(
    pair="EURUSD",
    timeframe="1d",
    start_date="2024-01-01",
    end_date="2024-12-31",
)
print(f"\n1-day bars (2024):          {len(df_1d):,} rows")
print(df_1d.head(3))

# ============================================================================
# Example 5: Query Raw Tick Data with Date Ranges
# ============================================================================
print("\n" + "=" * 80)
print("Example 5: Query Raw Tick Data")
print("=" * 80)

# Query Raw_Spread ticks for September 2024
df_raw = processor.query_ticks(
    pair="EURUSD",
    variant="raw_spread",
    start_date="2024-09-01",
    end_date="2024-09-30",
)

print(f"\nRaw_Spread ticks (Sep 2024): {len(df_raw):,} ticks")
print(f"Columns:                     {list(df_raw.columns)}")
print(f"Date range:                  {df_raw['Timestamp'].min()} to {df_raw['Timestamp'].max()}")
print("\nFirst 5 ticks:")
print(df_raw.head())

# Calculate spread statistics
df_raw["Spread"] = df_raw["Ask"] - df_raw["Bid"]
zero_spread_pct = (df_raw["Spread"] == 0).sum() / len(df_raw) * 100

print("\nRaw_Spread characteristics:")
print(f"   Zero-spreads:  {zero_spread_pct:.2f}%")
print(f"   Mean spread:   {df_raw['Spread'].mean() * 10000:.4f} pips")
print(f"   Max spread:    {df_raw['Spread'].max() * 10000:.2f} pips")

# Query Standard ticks for comparison
df_std = processor.query_ticks(
    pair="EURUSD",
    variant="standard",
    start_date="2024-09-01",
    end_date="2024-09-30",
)

df_std["Spread"] = df_std["Ask"] - df_std["Bid"]

print("\nStandard variant characteristics:")
print(f"   Ticks:         {len(df_std):,}")
print(f"   Zero-spreads:  {((df_std['Spread'] == 0).sum() / len(df_std) * 100):.2f}%")
print(f"   Mean spread:   {df_std['Spread'].mean() * 10000:.2f} pips")

# ============================================================================
# Example 6: Query with Custom SQL Filters
# ============================================================================
print("\n" + "=" * 80)
print("Example 6: Query with Custom Filters")
print("=" * 80)

# Query only zero-spread ticks
df_zero = processor.query_ticks(
    pair="EURUSD",
    variant="raw_spread",
    start_date="2024-09-01",
    end_date="2024-09-01",
    filter_sql="Bid = Ask",
)

print(f"\nZero-spread ticks (Sep 1, 2024): {len(df_zero):,}")
print(df_zero.head())

# Query high-price ticks
df_high = processor.query_ticks(
    pair="EURUSD",
    variant="raw_spread",
    start_date="2024-09-01",
    end_date="2024-09-30",
    filter_sql="Bid > 1.11",
)

print(f"\nHigh-price ticks (Bid > 1.11):   {len(df_high):,}")
print(f"Price range:                     {df_high['Bid'].min():.5f} to {df_high['Bid'].max():.5f}")

print("\n" + "=" * 80)
print("✅ All examples completed successfully!")
print("=" * 80)
print("\nKey Features of v2.0.0:")
print("   ✅ Single file per instrument (eurusd.duckdb)")
print("   ✅ Automatic incremental updates")
print("   ✅ Dual-variant storage (Phase7 compliant)")
print("   ✅ 30-column (v1.6.0) OHLC schema with trading hour detection")
print("   ✅ Date range queries")
print("   ✅ On-demand resampling (<15ms)")
print("   ✅ SQL filters on ticks")
print("\nNext steps:")
print("   - See batch_processing.py for processing multiple instruments")
print("   - See docs/UNIFIED_DUCKDB_PLAN_v2.md for architecture details")
print("   - See tests/ for unit tests and validation")
