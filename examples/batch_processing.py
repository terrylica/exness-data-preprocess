"""
Batch processing examples for exness-data-preprocess v2.0.0.

This script demonstrates how to:
1. Process multiple instruments in parallel or sequentially
2. Implement incremental updates for multiple pairs
3. Handle errors and implement retry logic
4. Monitor progress with progress bars
5. Validate data quality across instruments
6. Optimize storage and manage database sizes

For basic usage examples, see basic_usage.py.

Architecture v2.0.0:
- One DuckDB file per instrument (eurusd.duckdb, xauusd.duckdb)
- Incremental updates with automatic gap detection
- Dual-variant storage (Raw_Spread + Standard)
- 9-column Phase7 OHLC schema
"""

from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Any
import exness_data_preprocess as edp

# Optional: Configure base directory (defaults to ~/eon/exness-data/)
BASE_DIR = Path.home() / "eon" / "exness-data"

# ============================================================================
# Example 1: Process Multiple Instruments Sequentially
# ============================================================================
print("=" * 80)
print("Example 1: Process Multiple Instruments Sequentially")
print("=" * 80)

# Process multiple pairs with 3-year history
pairs_to_process = ["EURUSD", "GBPUSD", "XAUUSD"]

processor = edp.ExnessDataProcessor(base_dir=BASE_DIR)
results = {}

for pair in pairs_to_process:
    print(f"\n📥 Processing {pair} (3-year history)...")
    try:
        result = processor.update_data(
            pair=pair,
            start_date="2022-01-01",
            delete_zip=True,
        )
        results[pair] = result
        print(f"   ✅ Success:")
        print(f"      Months added:  {result['months_added']}")
        print(f"      Raw ticks:     {result['raw_ticks_added']:,}")
        print(f"      Standard ticks: {result['standard_ticks_added']:,}")
        print(f"      OHLC bars:     {result['ohlc_bars']:,}")
        print(f"      Database size: {result['duckdb_size_mb']:.2f} MB")
    except Exception as e:
        print(f"   ❌ Failed: {e}")

print(f"\n✅ Processed {len(results)}/{len(pairs_to_process)} instruments successfully")

# ============================================================================
# Example 2: Parallel Processing with ThreadPoolExecutor
# ============================================================================
print("\n" + "=" * 80)
print("Example 2: Parallel Processing (Multiple Instruments)")
print("=" * 80)


def process_instrument_worker(pair: str, start_date: str) -> tuple:
    """Worker function for parallel instrument processing."""
    try:
        processor = edp.ExnessDataProcessor(base_dir=BASE_DIR)
        result = processor.update_data(
            pair=pair,
            start_date=start_date,
            delete_zip=True,
        )
        return (pair, result, None)
    except Exception as e:
        return (pair, None, str(e))


# Process 4 instruments in parallel
instruments = [
    ("EURUSD", "2023-01-01"),
    ("GBPUSD", "2023-01-01"),
    ("XAUUSD", "2023-01-01"),
    ("USDJPY", "2023-01-01"),
]

print("\n🚀 Starting parallel processing (4 workers)...")

with ThreadPoolExecutor(max_workers=4) as executor:
    futures = {
        executor.submit(process_instrument_worker, pair, start_date): pair
        for pair, start_date in instruments
    }

    for future in as_completed(futures):
        pair = futures[future]
        pair_result, result, error = future.result()

        if error:
            print(f"❌ {pair_result}: {error}")
        else:
            print(f"✅ {pair_result}:")
            print(f"   Months added:  {result['months_added']}")
            print(f"   Database size: {result['duckdb_size_mb']:.2f} MB")

# ============================================================================
# Example 3: Incremental Updates for All Instruments
# ============================================================================
print("\n" + "=" * 80)
print("Example 3: Incremental Updates (Keep Data Current)")
print("=" * 80)

# Update all instruments that already exist
processor = edp.ExnessDataProcessor(base_dir=BASE_DIR)

# Find all existing databases
existing_pairs = []
for db_file in BASE_DIR.glob("*.duckdb"):
    pair_name = db_file.stem.upper()
    existing_pairs.append(pair_name)

print(f"\nFound {len(existing_pairs)} existing databases: {', '.join(existing_pairs)}")

# Run incremental updates
for pair in existing_pairs:
    print(f"\n🔄 Checking {pair} for updates...")
    try:
        result = processor.update_data(
            pair=pair,
            start_date="2022-01-01",  # Same start date - will only add new months
            delete_zip=True,
        )

        if result['months_added'] > 0:
            print(f"   ✅ Added {result['months_added']} new months")
            print(f"      Raw ticks:     {result['raw_ticks_added']:,}")
            print(f"      Database size: {result['duckdb_size_mb']:.2f} MB")
        else:
            print(f"   ✅ Already up to date")
            print(f"      Database size: {result['duckdb_size_mb']:.2f} MB")

    except Exception as e:
        print(f"   ❌ Failed: {e}")

# ============================================================================
# Example 4: Error Handling and Retry Logic
# ============================================================================
print("\n" + "=" * 80)
print("Example 4: Error Handling and Retry Logic")
print("=" * 80)


def update_with_retry(pair: str, start_date: str, max_retries: int = 3) -> Dict[str, Any]:
    """Update instrument with retry logic."""
    processor = edp.ExnessDataProcessor(base_dir=BASE_DIR)

    for attempt in range(max_retries):
        try:
            print(f"   Attempt {attempt + 1}/{max_retries} for {pair}...")
            result = processor.update_data(
                pair=pair,
                start_date=start_date,
                delete_zip=True,
            )
            print(f"   ✅ Success on attempt {attempt + 1}")
            return result
        except Exception as e:
            print(f"   ⚠️  Attempt {attempt + 1} failed: {e}")
            if attempt == max_retries - 1:
                print(f"   ❌ All {max_retries} attempts failed")
                raise
            print(f"   🔄 Retrying...")


# Try processing EURUSD with retry logic
try:
    result = update_with_retry("EURUSD", "2024-01-01")
    print(f"\n✅ Successfully updated EURUSD: {result['months_added']} months added")
except Exception as e:
    print(f"\n❌ Failed to update EURUSD after retries: {e}")

# ============================================================================
# Example 5: Progress Monitoring with tqdm
# ============================================================================
print("\n" + "=" * 80)
print("Example 5: Progress Monitoring with tqdm")
print("=" * 80)

try:
    from tqdm import tqdm

    # Process multiple major pairs with progress bar
    major_pairs = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "NZDUSD"]

    processor = edp.ExnessDataProcessor(base_dir=BASE_DIR)
    results = []

    with tqdm(total=len(major_pairs), desc="Processing pairs", unit="pair") as pbar:
        for pair in major_pairs:
            try:
                result = processor.update_data(
                    pair=pair,
                    start_date="2024-01-01",
                    delete_zip=True,
                )
                results.append(result)
                pbar.set_postfix(
                    pair=pair,
                    months=result['months_added'],
                    size_mb=f"{result['duckdb_size_mb']:.1f}",
                )
            except Exception as e:
                pbar.set_postfix(pair=pair, status=f"FAILED: {str(e)[:30]}")
            finally:
                pbar.update(1)

    print(f"\n✅ Processed {len(results)}/{len(major_pairs)} pairs successfully")

except ImportError:
    print("\n⚠️  tqdm not installed. Install with: pip install tqdm")
    print("   Skipping progress bar example...")

# ============================================================================
# Example 6: Data Quality Validation
# ============================================================================
print("\n" + "=" * 80)
print("Example 6: Data Quality Validation")
print("=" * 80)


def validate_instrument_data(pair: str) -> Dict[str, Any]:
    """Validate data quality for an instrument."""
    processor = edp.ExnessDataProcessor(base_dir=BASE_DIR)

    print(f"\n🔍 Validating {pair}...")

    # Step 1: Check coverage
    coverage = processor.get_data_coverage(pair)

    if not coverage['database_exists']:
        print(f"   ❌ Database does not exist")
        return {'valid': False, 'reason': 'database_missing'}

    print(f"   📊 Coverage:")
    print(f"      Raw_Spread ticks: {coverage['raw_spread_ticks']:,}")
    print(f"      Standard ticks:   {coverage['standard_ticks']:,}")
    print(f"      OHLC bars:        {coverage['ohlc_bars']:,}")
    print(f"      Date range:       {coverage['earliest_date']} to {coverage['latest_date']}")

    # Step 2: Query recent data for validation
    try:
        df_ticks = processor.query_ticks(
            pair=pair,
            variant="raw_spread",
            start_date=coverage['latest_date'],  # Get most recent day
        )

        # Validate tick data
        if len(df_ticks) == 0:
            print(f"   ⚠️  No ticks found for latest date")
            return {'valid': False, 'reason': 'no_recent_ticks'}

        # Check for invalid prices
        invalid_bids = (df_ticks['Bid'] <= 0).sum()
        invalid_asks = (df_ticks['Ask'] <= 0).sum()

        if invalid_bids > 0 or invalid_asks > 0:
            print(f"   ⚠️  Found {invalid_bids} invalid bids, {invalid_asks} invalid asks")

        # Check spread
        df_ticks['Spread'] = df_ticks['Ask'] - df_ticks['Bid']
        negative_spreads = (df_ticks['Spread'] < 0).sum()

        if negative_spreads > 0:
            print(f"   ⚠️  Found {negative_spreads} negative spreads")

        # Calculate spread statistics
        mean_spread = df_ticks['Spread'].mean() * 10000  # in pips
        zero_spread_pct = (df_ticks['Spread'] == 0).sum() / len(df_ticks) * 100

        print(f"   📈 Spread Statistics:")
        print(f"      Mean spread:   {mean_spread:.2f} pips")
        print(f"      Zero-spreads:  {zero_spread_pct:.2f}%")

        print(f"   ✅ Validation passed")
        return {'valid': True}

    except Exception as e:
        print(f"   ❌ Validation failed: {e}")
        return {'valid': False, 'reason': str(e)}


# Validate all existing instruments
for db_file in BASE_DIR.glob("*.duckdb"):
    pair_name = db_file.stem.upper()
    validate_instrument_data(pair_name)

# ============================================================================
# Example 7: Storage Management and Optimization
# ============================================================================
print("\n" + "=" * 80)
print("Example 7: Storage Management and Optimization")
print("=" * 80)

# Check storage usage across all databases
print("\n💾 Database Storage Summary:")
print("-" * 80)

total_size_mb = 0
databases = []

for db_file in sorted(BASE_DIR.glob("*.duckdb")):
    pair_name = db_file.stem.upper()
    size_mb = db_file.stat().st_size / (1024 * 1024)
    total_size_mb += size_mb

    processor = edp.ExnessDataProcessor(base_dir=BASE_DIR)
    coverage = processor.get_data_coverage(pair_name)

    databases.append({
        'pair': pair_name,
        'size_mb': size_mb,
        'raw_ticks': coverage['raw_spread_ticks'],
        'ohlc_bars': coverage['ohlc_bars'],
        'date_range_days': coverage['date_range_days'],
    })

# Print sorted by size
for db in sorted(databases, key=lambda x: x['size_mb'], reverse=True):
    print(f"{db['pair']:10s} | {db['size_mb']:8.2f} MB | "
          f"{db['raw_ticks']:12,} ticks | {db['ohlc_bars']:8,} bars | "
          f"{db['date_range_days']:4d} days")

print("-" * 80)
print(f"{'TOTAL':10s} | {total_size_mb:8.2f} MB")

# Optional: Clean up ZIP files if any remain
zip_dir = BASE_DIR / "temp"
if zip_dir.exists():
    zip_files = list(zip_dir.glob("*.zip"))
    if zip_files:
        zip_size_mb = sum(f.stat().st_size for f in zip_files) / (1024 * 1024)
        print(f"\n🧹 Found {len(zip_files)} ZIP files ({zip_size_mb:.2f} MB)")
        print("   Consider deleting with: rm -rf ~/eon/exness-data/temp/*.zip")

# ============================================================================
# Example 8: Advanced - Custom Multi-Instrument Pipeline
# ============================================================================
print("\n" + "=" * 80)
print("Example 8: Custom Multi-Instrument Pipeline")
print("=" * 80)


class MultiInstrumentPipeline:
    """Custom pipeline for processing multiple instruments."""

    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.processor = edp.ExnessDataProcessor(base_dir=base_dir)

    def sync_all_instruments(
        self,
        pairs: List[str],
        start_date: str = "2022-01-01",
        validate: bool = True,
    ) -> Dict[str, Any]:
        """Sync all instruments and optionally validate."""
        results = {}

        print(f"\n🔄 Syncing {len(pairs)} instruments...")

        for pair in pairs:
            print(f"\n📥 {pair}...")
            try:
                # Update data
                result = self.processor.update_data(
                    pair=pair,
                    start_date=start_date,
                    delete_zip=True,
                )

                # Validate if requested
                if validate and result['months_added'] > 0:
                    coverage = self.processor.get_data_coverage(pair)
                    result['validated'] = coverage['database_exists']

                results[pair] = result
                print(f"   ✅ Synced: {result['months_added']} months added")

            except Exception as e:
                print(f"   ❌ Failed: {e}")
                results[pair] = {'error': str(e)}

        return results

    def generate_coverage_report(self) -> str:
        """Generate coverage report for all instruments."""
        report_lines = []
        report_lines.append("\n" + "=" * 80)
        report_lines.append("Multi-Instrument Coverage Report")
        report_lines.append("=" * 80)

        for db_file in sorted(self.base_dir.glob("*.duckdb")):
            pair_name = db_file.stem.upper()
            coverage = self.processor.get_data_coverage(pair_name)

            report_lines.append(f"\n{pair_name}:")
            report_lines.append(f"  Database:      {coverage['duckdb_path']}")
            report_lines.append(f"  Size:          {coverage['duckdb_size_mb']:.2f} MB")
            report_lines.append(f"  Raw ticks:     {coverage['raw_spread_ticks']:,}")
            report_lines.append(f"  Standard ticks: {coverage['standard_ticks']:,}")
            report_lines.append(f"  OHLC bars:     {coverage['ohlc_bars']:,}")
            report_lines.append(f"  Coverage:      {coverage['earliest_date']} to {coverage['latest_date']}")
            report_lines.append(f"  Range:         {coverage['date_range_days']} days")

        return "\n".join(report_lines)


# Use custom pipeline
pipeline = MultiInstrumentPipeline(base_dir=BASE_DIR)

# Sync major FX pairs
major_fx_pairs = ["EURUSD", "GBPUSD", "USDJPY"]
sync_results = pipeline.sync_all_instruments(
    pairs=major_fx_pairs,
    start_date="2024-01-01",
    validate=True,
)

# Generate coverage report
coverage_report = pipeline.generate_coverage_report()
print(coverage_report)

print("\n" + "=" * 80)
print("✅ All batch processing examples completed!")
print("=" * 80)
print("\nKey Features of v2.0.0 Batch Processing:")
print("   ✅ Single file per instrument (eurusd.duckdb)")
print("   ✅ Automatic incremental updates")
print("   ✅ Parallel processing support")
print("   ✅ Error handling and retry logic")
print("   ✅ Progress monitoring with tqdm")
print("   ✅ Data quality validation")
print("   ✅ Storage management and reporting")
print("\nBest Practices:")
print("   - Use parallel processing for multiple instruments (4-8 workers)")
print("   - Implement retry logic for network failures")
print("   - Monitor progress with tqdm for long-running jobs")
print("   - Validate data quality after processing")
print("   - Use delete_zip=True to save disk space")
print("   - Run incremental updates regularly to keep data current")
print("\nNext steps:")
print("   - See basic_usage.py for single-instrument examples")
print("   - See docs/UNIFIED_DUCKDB_PLAN_v2.md for architecture details")
print("   - See tests/ for unit tests and validation")
