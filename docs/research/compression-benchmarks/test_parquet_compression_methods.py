#!/usr/bin/env python3
"""
Test all Parquet compression methods to find the smallest file size.

Compression codecs available in Parquet:
- snappy: Default, fast but not best compression
- gzip: Good compression, slower
- brotli: Good compression (Google)
- zstd: Zstandard (Facebook/Meta) - best balance
- lz4: Very fast but less compression
- none: No compression

ZSTD levels: 1 (fastest) to 22 (best compression), default is 3
"""

import zipfile
from pathlib import Path
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq


def test_compression_methods():
    """Test all Parquet compression methods and levels."""

    zip_path = Path('/tmp/Exness_EURUSD_Raw_Spread_2024_08.zip')

    if not zip_path.exists():
        print(f"✗ ZIP not found: {zip_path}")
        print("  Run parquet_primary_architecture.py first to download the data")
        return

    print("╔═══════════════════════════════════════════════════════════════╗")
    print("║     Parquet Compression Method Comparison (August 2024)      ║")
    print("╚═══════════════════════════════════════════════════════════════╝")

    # Load data from ZIP
    print("\n1. Loading tick data from ZIP...")
    with zipfile.ZipFile(zip_path, 'r') as zf:
        csv_name = zip_path.stem + '.csv'
        with zf.open(csv_name) as csv_file:
            df = pd.read_csv(
                csv_file,
                usecols=['Timestamp', 'Bid', 'Ask'],
                parse_dates=['Timestamp']
            )

    df['Timestamp'] = pd.to_datetime(df['Timestamp'], utc=True)
    print(f"   Loaded {len(df):,} ticks")

    # Get ZIP size for comparison
    zip_size_mb = zip_path.stat().st_size / 1024 / 1024
    print(f"\n2. Baseline: ZIP size = {zip_size_mb:.2f} MB")

    # Test directory
    test_dir = Path('/tmp/parquet_compression_tests')
    test_dir.mkdir(exist_ok=True)

    results = []

    print(f"\n3. Testing compression methods...")
    print(f"{'─'*70}")

    # Test basic compression methods
    compression_methods = ['snappy', 'gzip', 'brotli', 'zstd', 'lz4', 'none']

    for method in compression_methods:
        try:
            parquet_path = test_dir / f'test_{method}.parquet'

            print(f"\n   Testing: {method}...", end=' ')

            df.to_parquet(parquet_path, index=False, compression=method)

            size_mb = parquet_path.stat().st_size / 1024 / 1024
            ratio = size_mb / zip_size_mb

            results.append({
                'method': method,
                'level': 'default',
                'size_mb': size_mb,
                'vs_zip': ratio,
                'savings_vs_zip': (1 - ratio) * 100
            })

            print(f"{size_mb:.2f} MB ({ratio:.2f}x vs ZIP)")

        except Exception as e:
            print(f"FAILED: {e}")

    # Test ZSTD with different compression levels
    print(f"\n4. Testing ZSTD compression levels (Facebook/Meta algorithm)...")
    print(f"{'─'*70}")

    zstd_levels = [1, 3, 5, 9, 15, 22]  # 1=fastest, 22=best compression

    for level in zstd_levels:
        try:
            parquet_path = test_dir / f'test_zstd_level{level}.parquet'

            print(f"\n   ZSTD level {level:2d}...", end=' ')

            # Use PyArrow directly for compression level control
            table = pa.Table.from_pandas(df)
            pq.write_table(
                table,
                parquet_path,
                compression='zstd',
                compression_level=level
            )

            size_mb = parquet_path.stat().st_size / 1024 / 1024
            ratio = size_mb / zip_size_mb

            results.append({
                'method': 'zstd',
                'level': str(level),
                'size_mb': size_mb,
                'vs_zip': ratio,
                'savings_vs_zip': (1 - ratio) * 100
            })

            print(f"{size_mb:.2f} MB ({ratio:.2f}x vs ZIP)")

        except Exception as e:
            print(f"FAILED: {e}")

    # Test Brotli with different levels
    print(f"\n5. Testing Brotli compression levels (Google algorithm)...")
    print(f"{'─'*70}")

    brotli_levels = [1, 6, 11]  # 1=fastest, 11=best compression

    for level in brotli_levels:
        try:
            parquet_path = test_dir / f'test_brotli_level{level}.parquet'

            print(f"\n   Brotli level {level:2d}...", end=' ')

            table = pa.Table.from_pandas(df)
            pq.write_table(
                table,
                parquet_path,
                compression='brotli',
                compression_level=level
            )

            size_mb = parquet_path.stat().st_size / 1024 / 1024
            ratio = size_mb / zip_size_mb

            results.append({
                'method': 'brotli',
                'level': str(level),
                'size_mb': size_mb,
                'vs_zip': ratio,
                'savings_vs_zip': (1 - ratio) * 100
            })

            print(f"{size_mb:.2f} MB ({ratio:.2f}x vs ZIP)")

        except Exception as e:
            print(f"FAILED: {e}")

    # Create results DataFrame
    df_results = pd.DataFrame(results)
    df_results = df_results.sort_values('size_mb')

    # Print summary
    print(f"\n{'═'*70}")
    print("SUMMARY: All Compression Methods (Sorted by Size)")
    print(f"{'═'*70}")
    print(f"\nBaseline: ZIP = {zip_size_mb:.2f} MB")
    print(f"\n{'Method':<15} {'Level':<10} {'Size (MB)':<12} {'vs ZIP':<10} {'Savings':<10}")
    print(f"{'─'*70}")

    for _, row in df_results.iterrows():
        savings_str = f"{row['savings_vs_zip']:+.1f}%" if row['savings_vs_zip'] != 0 else "0.0%"
        print(f"{row['method']:<15} {row['level']:<10} {row['size_mb']:<12.2f} {row['vs_zip']:<10.2f} {savings_str:<10}")

    # Find best method
    best = df_results.iloc[0]
    worst = df_results.iloc[-1]

    print(f"\n{'═'*70}")
    print("WINNER")
    print(f"{'═'*70}")
    print(f"\n✓ Best compression: {best['method']} (level {best['level']})")
    print(f"  Size: {best['size_mb']:.2f} MB")
    print(f"  vs ZIP: {best['vs_zip']:.2f}x")

    if best['vs_zip'] < 1.0:
        print(f"  ✓ SMALLER than ZIP by {(1 - best['vs_zip']) * 100:.1f}%")
    else:
        print(f"  ✗ LARGER than ZIP by {(best['vs_zip'] - 1) * 100:.1f}%")

    print(f"\n✗ Worst compression: {worst['method']} (level {worst['level']})")
    print(f"  Size: {worst['size_mb']:.2f} MB")
    print(f"  vs ZIP: {worst['vs_zip']:.2f}x ({(worst['vs_zip'] - 1) * 100:.1f}% larger)")

    # Show 3-year extrapolation with best method
    print(f"\n{'═'*70}")
    print("3-YEAR STORAGE EXTRAPOLATION")
    print(f"{'═'*70}")

    months = 36
    zip_total = zip_size_mb * months
    parquet_total = best['size_mb'] * months

    print(f"\nZIP (baseline):              {zip_total:>8.1f} MB ({zip_total/1024:.2f} GB)")
    print(f"Parquet ({best['method']}, level {best['level']}):  {parquet_total:>8.1f} MB ({parquet_total/1024:.2f} GB)")
    print(f"                             {'─'*30}")

    if parquet_total < zip_total:
        savings = zip_total - parquet_total
        print(f"Savings:                     {savings:>8.1f} MB ({100 * savings / zip_total:.1f}%)")
        print(f"\n✓ Parquet with {best['method']} level {best['level']} IS smaller than ZIP!")
    else:
        overhead = parquet_total - zip_total
        print(f"Overhead:                    {overhead:>8.1f} MB ({100 * overhead / zip_total:.1f}%)")
        print(f"\n✗ Even best Parquet compression is larger than ZIP")

    # Recommendation
    print(f"\n{'═'*70}")
    print("RECOMMENDATION")
    print(f"{'═'*70}")

    if parquet_total < zip_total:
        print(f"\n✓ Use Parquet with {best['method']} compression level {best['level']}")
        print(f"✓ Delete ZIPs after conversion")
        print(f"✓ Save {(zip_total - parquet_total)/1024:.2f} GB for 3 years")
    else:
        print(f"\n✗ Keep Option A (DuckDB only, 28 MB)")
        print(f"✗ Don't store Parquet permanently (larger than ZIPs)")
        print(f"✓ Use on-demand tick analysis (download → analyze → delete)")


if __name__ == '__main__':
    test_compression_methods()
