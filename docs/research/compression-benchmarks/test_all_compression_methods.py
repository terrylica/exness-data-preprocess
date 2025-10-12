#!/usr/bin/env python3
"""
Comprehensive compression test for EURUSD tick data.

Tests:
1. Parquet with all compression methods (Zstd level 22, Brotli level 11)
2. Apache Arrow/Feather format
3. Lance format (if available)
4. Time-series specific compression techniques
"""

import zipfile
from pathlib import Path
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pyarrow.feather as feather
import time


def load_tick_data():
    """Load EURUSD tick data from ZIP."""
    zip_path = Path('/tmp/Exness_EURUSD_Raw_Spread_2024_08.zip')

    if not zip_path.exists():
        print(f"✗ ZIP not found: {zip_path}")
        return None, None

    with zipfile.ZipFile(zip_path, 'r') as zf:
        csv_name = zip_path.stem + '.csv'
        with zf.open(csv_name) as csv_file:
            df = pd.read_csv(
                csv_file,
                usecols=['Timestamp', 'Bid', 'Ask'],
                parse_dates=['Timestamp']
            )

    df['Timestamp'] = pd.to_datetime(df['Timestamp'], utc=True)
    zip_size_mb = zip_path.stat().st_size / 1024 / 1024

    return df, zip_size_mb


def test_parquet_compression(df: pd.DataFrame, test_dir: Path):
    """Test Parquet with various compression methods."""
    results = []

    print("\n1. Testing Parquet Compression Methods")
    print("="*70)

    # Test Zstd at maximum level (this is what time-series DBs use)
    for level in [1, 9, 15, 22]:
        try:
            path = test_dir / f'parquet_zstd_{level}.parquet'

            print(f"   Zstd level {level:2d}...", end=' ', flush=True)

            start = time.time()
            table = pa.Table.from_pandas(df)
            pq.write_table(table, path, compression='zstd', compression_level=level)
            write_time = time.time() - start

            size_mb = path.stat().st_size / 1024 / 1024

            # Test read speed
            start = time.time()
            _ = pq.read_table(path)
            read_time = time.time() - start

            results.append({
                'format': 'Parquet',
                'compression': f'zstd-{level}',
                'size_mb': size_mb,
                'write_time': write_time,
                'read_time': read_time
            })

            print(f"{size_mb:.2f} MB (write: {write_time:.2f}s, read: {read_time:.2f}s)")

        except Exception as e:
            print(f"FAILED: {e}")

    # Test Brotli for comparison (but we know it's slow)
    for level in [1, 11]:
        try:
            path = test_dir / f'parquet_brotli_{level}.parquet'

            print(f"   Brotli level {level:2d}...", end=' ', flush=True)

            start = time.time()
            table = pa.Table.from_pandas(df)
            pq.write_table(table, path, compression='brotli', compression_level=level)
            write_time = time.time() - start

            # Timeout if write takes > 60 seconds
            if write_time > 60:
                print(f"TIMEOUT after {write_time:.1f}s (too slow for production use)")
                path.unlink()
                continue

            size_mb = path.stat().st_size / 1024 / 1024

            start = time.time()
            _ = pq.read_table(path)
            read_time = time.time() - start

            results.append({
                'format': 'Parquet',
                'compression': f'brotli-{level}',
                'size_mb': size_mb,
                'write_time': write_time,
                'read_time': read_time
            })

            print(f"{size_mb:.2f} MB (write: {write_time:.2f}s, read: {read_time:.2f}s)")

        except Exception as e:
            print(f"FAILED: {e}")

    return results


def test_arrow_feather(df: pd.DataFrame, test_dir: Path):
    """Test Apache Arrow/Feather format (IPC format)."""
    results = []

    print("\n2. Testing Apache Arrow/Feather Format")
    print("="*70)

    # Feather V2 supports compression
    for compression in ['uncompressed', 'lz4', 'zstd']:
        try:
            path = test_dir / f'feather_{compression}.arrow'

            print(f"   Feather {compression}...", end=' ', flush=True)

            start = time.time()
            feather.write_feather(df, path, compression=compression)
            write_time = time.time() - start

            size_mb = path.stat().st_size / 1024 / 1024

            start = time.time()
            _ = feather.read_feather(path)
            read_time = time.time() - start

            results.append({
                'format': 'Feather',
                'compression': compression,
                'size_mb': size_mb,
                'write_time': write_time,
                'read_time': read_time
            })

            print(f"{size_mb:.2f} MB (write: {write_time:.2f}s, read: {read_time:.2f}s)")

        except Exception as e:
            print(f"FAILED: {e}")

    return results


def test_lance_format(df: pd.DataFrame, test_dir: Path):
    """Test Lance format if available."""
    results = []

    print("\n3. Testing Lance Format (100x faster random access)")
    print("="*70)

    try:
        import lance

        path = test_dir / 'lance_test.lance'

        print(f"   Lance format...", end=' ', flush=True)

        start = time.time()
        lance.write_dataset(df, path)
        write_time = time.time() - start

        # Calculate directory size
        size_bytes = sum(f.stat().st_size for f in path.rglob('*') if f.is_file())
        size_mb = size_bytes / 1024 / 1024

        start = time.time()
        _ = lance.dataset(path).to_table()
        read_time = time.time() - start

        results.append({
            'format': 'Lance',
            'compression': 'default',
            'size_mb': size_mb,
            'write_time': write_time,
            'read_time': read_time
        })

        print(f"{size_mb:.2f} MB (write: {write_time:.2f}s, read: {read_time:.2f}s)")

    except ImportError:
        print("   Lance not installed (pip install pylance)")
    except Exception as e:
        print(f"   FAILED: {e}")

    return results


def test_delta_encoding(df: pd.DataFrame, test_dir: Path):
    """Test time-series specific delta encoding."""
    results = []

    print("\n4. Testing Time-Series Specific: Delta Encoding")
    print("="*70)

    try:
        # Convert timestamp to int64 (nanoseconds since epoch)
        df_delta = df.copy()
        df_delta['Timestamp'] = df_delta['Timestamp'].astype('int64')

        # Apply delta encoding to timestamp (huge compression for sequential data)
        df_delta['Timestamp_delta'] = df_delta['Timestamp'].diff().fillna(0).astype('int32')

        # Apply delta encoding to Bid/Ask (financial data has small changes)
        df_delta['Bid_delta'] = (df_delta['Bid'].diff().fillna(0) * 100000).astype('int16')
        df_delta['Ask_delta'] = (df_delta['Ask'].diff().fillna(0) * 100000).astype('int16')

        # Drop original columns, keep only deltas and first values
        first_timestamp = df_delta['Timestamp'].iloc[0]
        first_bid = df_delta['Bid'].iloc[0]
        first_ask = df_delta['Ask'].iloc[0]

        df_delta = df_delta[['Timestamp_delta', 'Bid_delta', 'Ask_delta']]

        # Save with Zstd compression
        path = test_dir / 'delta_encoded_zstd.parquet'

        print(f"   Delta + Zstd-22...", end=' ', flush=True)

        start = time.time()
        table = pa.Table.from_pandas(df_delta)
        pq.write_table(table, path, compression='zstd', compression_level=22)
        write_time = time.time() - start

        size_mb = path.stat().st_size / 1024 / 1024

        start = time.time()
        _ = pq.read_table(path)
        read_time = time.time() - start

        results.append({
            'format': 'Parquet+Delta',
            'compression': 'zstd-22',
            'size_mb': size_mb,
            'write_time': write_time,
            'read_time': read_time
        })

        print(f"{size_mb:.2f} MB (write: {write_time:.2f}s, read: {read_time:.2f}s)")
        print(f"   Note: Requires decoding (reconstruct from deltas + initial values)")

    except Exception as e:
        print(f"   FAILED: {e}")

    return results


def main():
    """Run comprehensive compression tests."""

    print("╔═══════════════════════════════════════════════════════════════╗")
    print("║   Comprehensive Compression Test for Time Series Data        ║")
    print("╚═══════════════════════════════════════════════════════════════╝")

    # Load data
    print("\nLoading EURUSD tick data...")
    df, zip_size_mb = load_tick_data()

    if df is None:
        return

    print(f"✓ Loaded {len(df):,} ticks")
    print(f"✓ ZIP baseline: {zip_size_mb:.2f} MB")

    # Test directory
    test_dir = Path('/tmp/compression_tests')
    test_dir.mkdir(exist_ok=True)

    # Run all tests
    all_results = []

    all_results.extend(test_parquet_compression(df, test_dir))
    all_results.extend(test_arrow_feather(df, test_dir))
    all_results.extend(test_lance_format(df, test_dir))
    all_results.extend(test_delta_encoding(df, test_dir))

    # Create summary
    if not all_results:
        print("\n✗ No results to display")
        return

    df_results = pd.DataFrame(all_results)
    df_results['vs_zip'] = df_results['size_mb'] / zip_size_mb
    df_results['savings_pct'] = (1 - df_results['vs_zip']) * 100
    df_results = df_results.sort_values('size_mb')

    # Print summary
    print("\n" + "="*70)
    print("COMPREHENSIVE SUMMARY (Sorted by Size)")
    print("="*70)
    print(f"\nBaseline: ZIP = {zip_size_mb:.2f} MB\n")

    print(f"{'Format':<18} {'Compression':<12} {'Size':<8} {'vs ZIP':<8} {'Write':<8} {'Read':<8}")
    print("-"*70)

    for _, row in df_results.iterrows():
        savings = f"{row['savings_pct']:+.1f}%" if row['savings_pct'] != 0 else "0.0%"
        print(f"{row['format']:<18} {row['compression']:<12} {row['size_mb']:>6.2f}MB {row['vs_zip']:>6.2f}x {row['write_time']:>6.2f}s {row['read_time']:>6.2f}s")

    # Find winner
    best = df_results.iloc[0]
    fastest_write = df_results.loc[df_results['write_time'].idxmin()]
    fastest_read = df_results.loc[df_results['read_time'].idxmin()]

    print("\n" + "="*70)
    print("WINNERS")
    print("="*70)

    print(f"\n✓ Best Compression: {best['format']} ({best['compression']})")
    print(f"  Size: {best['size_mb']:.2f} MB")
    print(f"  vs ZIP: {best['vs_zip']:.2f}x ({abs(best['savings_pct']):.1f}% {'smaller' if best['vs_zip'] < 1 else 'larger'})")

    print(f"\n⚡ Fastest Write: {fastest_write['format']} ({fastest_write['compression']})")
    print(f"  Time: {fastest_write['write_time']:.2f}s")

    print(f"\n⚡ Fastest Read: {fastest_read['format']} ({fastest_read['compression']})")
    print(f"  Time: {fastest_read['read_time']:.2f}s")

    # 3-year extrapolation
    print("\n" + "="*70)
    print("3-YEAR STORAGE EXTRAPOLATION")
    print("="*70)

    months = 36
    zip_total = zip_size_mb * months
    best_total = best['size_mb'] * months

    print(f"\nZIP baseline:              {zip_total:>8.1f} MB ({zip_total/1024:.2f} GB)")
    print(f"{best['format']} ({best['compression']}):  {best_total:>8.1f} MB ({best_total/1024:.2f} GB)")
    print(f"{'─'*40}")

    if best_total < zip_total:
        savings = zip_total - best_total
        print(f"Savings:                   {savings:>8.1f} MB ({100*savings/zip_total:.1f}%)")
    else:
        overhead = best_total - zip_total
        print(f"Overhead:                  {overhead:>8.1f} MB ({100*overhead/zip_total:.1f}%)")

    # Final recommendation
    print("\n" + "="*70)
    print("RECOMMENDATION")
    print("="*70)

    if best_total < zip_total and best['write_time'] < 10:
        print(f"\n✓ Use {best['format']} with {best['compression']} compression")
        print(f"✓ {abs(best['savings_pct']):.1f}% smaller than ZIP")
        print(f"✓ Write time: {best['write_time']:.2f}s per month (acceptable)")
        print(f"✓ Read time: {best['read_time']:.2f}s per month")
        print(f"\nWorkflow: Download ZIP → Convert to {best['format']} → Delete ZIP")
        print(f"Total 3-year storage: {best_total:.0f} MB + 28 MB DuckDB = {best_total + 28:.0f} MB")
    else:
        print(f"\n✓ Stick with Option A (DuckDB only, 28 MB)")
        print(f"✗ Best compression ({best['format']} {best['compression']}) is still:")
        if best_total >= zip_total:
            print(f"  - {(best_total/zip_total - 1)*100:.1f}% larger than ZIP")
        if best['write_time'] >= 10:
            print(f"  - Too slow ({best['write_time']:.1f}s write time)")
        print(f"\n✓ Use on-demand tick analysis (30s download penalty is acceptable)")


if __name__ == '__main__':
    main()
