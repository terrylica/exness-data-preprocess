#!/usr/bin/env python3
"""
Properly test Delta Encoding with:
1. Reconstruction time
2. Precision loss measurement
3. Real-world usability
"""

import zipfile
from pathlib import Path
import pandas as pd
import numpy as np
import time
import pyarrow as pa
import pyarrow.parquet as pq


def load_exness_data():
    """Load actual Exness data."""
    zip_path = Path('/tmp/Exness_EURUSD_Raw_Spread_2024_08.zip')

    with zipfile.ZipFile(zip_path, 'r') as zf:
        csv_name = zip_path.stem + '.csv'
        with zf.open(csv_name) as csv_file:
            df = pd.read_csv(
                csv_file,
                usecols=['Timestamp', 'Bid', 'Ask'],
                parse_dates=['Timestamp']
            )

    df['Timestamp'] = pd.to_datetime(df['Timestamp'], utc=True)
    return df


def test_delta_encoding_full_cycle():
    """Test complete delta encoding cycle including reconstruction."""

    print("="*70)
    print("DELTA ENCODING: COMPLETE FAIRNESS TEST")
    print("="*70)

    df_original = load_exness_data()
    test_dir = Path('/tmp/delta_test')
    test_dir.mkdir(exist_ok=True)

    print(f"\nOriginal data: {len(df_original):,} ticks")

    # Step 1: Encode
    print("\n1. ENCODING (Write)")
    print("-"*70)

    df_delta = df_original.copy()
    df_delta['Timestamp'] = df_delta['Timestamp'].astype('int64')

    start = time.time()

    # Store first values for reconstruction
    first_timestamp = df_delta['Timestamp'].iloc[0]
    first_bid = df_delta['Bid'].iloc[0]
    first_ask = df_delta['Ask'].iloc[0]

    # Delta encoding
    df_delta['Timestamp_delta'] = df_delta['Timestamp'].diff().fillna(0).astype('int32')
    df_delta['Bid_delta'] = (df_delta['Bid'].diff().fillna(0) * 100000).astype('int16')
    df_delta['Ask_delta'] = (df_delta['Ask'].diff().fillna(0) * 100000).astype('int16')

    # Keep only deltas
    df_delta = df_delta[['Timestamp_delta', 'Bid_delta', 'Ask_delta']]

    # Write to Parquet
    path = test_dir / 'delta_zstd22.parquet'
    table = pa.Table.from_pandas(df_delta)
    pq.write_table(table, path, compression='zstd', compression_level=22)

    encode_time = time.time() - start
    size_mb = path.stat().st_size / 1024 / 1024

    print(f"Encode + Write time: {encode_time:.3f}s")
    print(f"Size: {size_mb:.2f} MB")

    # Step 2: Decode (THIS IS WHAT I MISSED!)
    print("\n2. DECODING (Read + Reconstruct)")
    print("-"*70)

    start = time.time()

    # Read compressed file
    df_read = pq.read_table(path).to_pandas()
    read_time = time.time() - start

    start = time.time()

    # Reconstruct original values from deltas
    df_reconstructed = pd.DataFrame()

    # Reconstruct Timestamp
    df_reconstructed['Timestamp'] = df_read['Timestamp_delta'].cumsum() + first_timestamp
    df_reconstructed['Timestamp'] = pd.to_datetime(df_reconstructed['Timestamp'], unit='ns', utc=True)

    # Reconstruct Bid (convert back from int16 to float)
    bid_deltas_float = df_read['Bid_delta'].astype('float64') / 100000
    df_reconstructed['Bid'] = bid_deltas_float.cumsum() + first_bid

    # Reconstruct Ask
    ask_deltas_float = df_read['Ask_delta'].astype('float64') / 100000
    df_reconstructed['Ask'] = ask_deltas_float.cumsum() + first_ask

    decode_time = time.time() - start

    print(f"Read time: {read_time:.3f}s")
    print(f"Decode time: {decode_time:.3f}s")
    print(f"Total read+decode: {read_time + decode_time:.3f}s")

    # Step 3: Measure precision loss
    print("\n3. PRECISION LOSS ANALYSIS")
    print("-"*70)

    # Compare reconstructed vs original
    bid_diff = (df_reconstructed['Bid'] - df_original['Bid']).abs()
    ask_diff = (df_reconstructed['Ask'] - df_original['Ask']).abs()

    print(f"\nBid errors:")
    print(f"  Mean error:   {bid_diff.mean():.10f} ({bid_diff.mean() * 10000:.4f} pips)")
    print(f"  Max error:    {bid_diff.max():.10f} ({bid_diff.max() * 10000:.4f} pips)")
    print(f"  Median error: {bid_diff.median():.10f}")
    print(f"  95th %ile:    {bid_diff.quantile(0.95):.10f}")

    print(f"\nAsk errors:")
    print(f"  Mean error:   {ask_diff.mean():.10f} ({ask_diff.mean() * 10000:.4f} pips)")
    print(f"  Max error:    {ask_diff.max():.10f} ({ask_diff.max() * 10000:.4f} pips)")

    # Show examples of errors
    print(f"\nSample errors (first 10 rows):")
    comparison = pd.DataFrame({
        'Original_Bid': df_original['Bid'].head(10),
        'Reconstructed_Bid': df_reconstructed['Bid'].head(10),
        'Error': bid_diff.head(10)
    })
    print(comparison.to_string(index=False))

    # Step 4: Queryability test
    print("\n4. QUERYABILITY TEST")
    print("-"*70)

    print("\nCan DuckDB query delta-encoded Parquet directly?")

    import duckdb
    conn = duckdb.connect()

    try:
        # Try to query delta file
        result = conn.execute(f"""
            SELECT AVG(Bid_delta) FROM '{path}'
        """).fetchone()
        print(f"✓ Can query delta columns: {result}")
        print("✗ But this is meaningless! Bid_delta are deltas, not prices!")
        print("✗ Can't do: SELECT * WHERE Bid > 1.08 (need reconstruction first)")
    except Exception as e:
        print(f"✗ Query failed: {e}")

    # Compare with normal Parquet
    normal_path = test_dir / 'normal_zstd22.parquet'
    table = pa.Table.from_pandas(df_original)
    pq.write_table(table, normal_path, compression='zstd', compression_level=22)

    print(f"\nCan DuckDB query normal Parquet directly?")
    result = conn.execute(f"""
        SELECT AVG(Bid), COUNT(*) FROM '{normal_path}' WHERE Bid > 1.08
    """).fetchone()
    print(f"✓ Yes! Average Bid where > 1.08: {result[0]:.5f}, Count: {result[1]}")

    conn.close()

    # Step 5: Fair comparison
    print("\n5. FAIR COMPARISON")
    print("="*70)

    normal_size = normal_path.stat().st_size / 1024 / 1024
    delta_size = path.stat().st_size / 1024 / 1024

    # Total time for delta includes encoding + reconstruction
    delta_total_time = encode_time + read_time + decode_time

    # Normal Parquet: just read time
    start = time.time()
    _ = pq.read_table(normal_path).to_pandas()
    normal_read_time = time.time() - start

    print(f"\n{'Method':<25} {'Size':<12} {'Write':<12} {'Read':<12} {'Usable?':<12}")
    print("-"*70)
    print(f"{'Delta (lossy)':<25} {delta_size:>10.2f}MB {encode_time:>10.3f}s {read_time+decode_time:>10.3f}s {'No (decode)':<12}")
    print(f"{'Normal Parquet':<25} {normal_size:>10.2f}MB {'—':>10} {normal_read_time:>10.3f}s {'Yes':<12}")

    print(f"\nDelta is {normal_size / delta_size:.1f}x smaller")
    print(f"But has {bid_diff.mean() * 10000:.4f} pips average error")
    print(f"And {(read_time + decode_time) / normal_read_time:.1f}x slower to read+decode")

    # Final verdict
    print("\n" + "="*70)
    print("VERDICT")
    print("="*70)

    print(f"\n❌ Delta encoding is NOT a fair comparison because:")
    print(f"   1. LOSSY: {bid_diff.mean() * 10000:.4f} pips avg error (max {bid_diff.max() * 10000:.2f} pips)")
    print(f"   2. Not directly queryable (needs Python decode step)")
    print(f"   3. {(read_time + decode_time) / normal_read_time:.1f}x slower when including decode time")
    print(f"   4. Can't use with DuckDB directly")

    print(f"\n✓ For fair comparison, should compare:")
    print(f"   - Lossless Parquet (zstd-22): {normal_size:.2f} MB")
    print(f"   - Can query directly with DuckDB")
    print(f"   - No precision loss")


if __name__ == '__main__':
    test_delta_encoding_full_cycle()
