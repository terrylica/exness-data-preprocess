"""
Command-line interface for Exness data preprocessing.
"""

import argparse
import importlib.metadata
import sys
from pathlib import Path

from exness_data_preprocess import api
from exness_data_preprocess.config import load_config


def process_command(args):
    """Handle 'process' command."""
    if args.range:
        # Process date range
        start_year, start_month = map(int, args.range[0].split("-"))
        end_year, end_month = map(int, args.range[1].split("-"))

        results = api.process_date_range(
            start_year=start_year,
            start_month=start_month,
            end_year=end_year,
            end_month=end_month,
            pair=args.pair,
            delete_zip=not args.keep_zip,
            base_dir=Path(args.base_dir) if args.base_dir else None,
        )

        print(f"\n{'=' * 70}")
        print(f"Processed {len(results)} months")
        total_ticks = sum(r["tick_count"] for r in results)
        total_size = sum(r["parquet_size_mb"] + r["duckdb_size_mb"] for r in results)
        print(f"Total ticks: {total_ticks:,}")
        print(f"Total storage: {total_size:.2f} MB")
        print(f"{'=' * 70}")
    else:
        # Process single month
        result = api.process_month(
            year=args.year,
            month=args.month,
            pair=args.pair,
            delete_zip=not args.keep_zip,
            base_dir=Path(args.base_dir) if args.base_dir else None,
            dry_run=args.dry_run,
        )
        if args.dry_run:
            print(f"\n✓ Dry-run completed for {args.pair} {args.year}-{args.month:02d}")
        else:
            print(f"\n✓ Successfully processed {args.pair} {args.year}-{args.month:02d}")


def query_command(args):
    """Handle 'query' command."""
    df = api.query_ohlc(
        year=args.year,
        month=args.month,
        pair=args.pair,
        timeframe=args.timeframe,
        base_dir=Path(args.base_dir) if args.base_dir else None,
    )

    if args.output:
        df.to_csv(args.output, index=False)
        print(f"✓ Saved {len(df)} bars to {args.output}")
    else:
        print(df.head(args.head))
        print(f"\nTotal bars: {len(df)}")


def analyze_command(args):
    """Handle 'analyze' command."""
    df = api.analyze_ticks(
        year=args.year,
        month=args.month,
        pair=args.pair,
        base_dir=Path(args.base_dir) if args.base_dir else None,
    )

    # Calculate spread statistics
    spreads = df["Ask"] - df["Bid"]

    print(f"\n{'=' * 70}")
    print(f"Tick Analysis: {args.pair} {args.year}-{args.month:02d}")
    print(f"{'=' * 70}")
    print(f"Total ticks:      {len(df):,}")
    print("\nSpread Statistics (base units):")
    print(f"  Mean:           {spreads.mean():.5f}")
    print(f"  Median:         {spreads.median():.5f}")
    print(f"  Std Dev:        {spreads.std():.5f}")
    print(f"  Min:            {spreads.min():.5f}")
    print(f"  Max:            {spreads.max():.5f}")
    print(f"  25th percentile: {spreads.quantile(0.25):.5f}")
    print(f"  75th percentile: {spreads.quantile(0.75):.5f}")
    print(f"  95th percentile: {spreads.quantile(0.95):.5f}")

    if args.output:
        df.to_csv(args.output, index=False)
        print(f"\n✓ Saved {len(df)} ticks to {args.output}")


def stats_command(args):
    """Handle 'stats' command."""
    stats = api.get_storage_stats(base_dir=Path(args.base_dir) if args.base_dir else None)

    print(f"\n{'=' * 70}")
    print("Storage Statistics")
    print(f"{'=' * 70}")
    print(f"Parquet files:    {stats['parquet_count']}")
    print(f"Parquet storage:  {stats['parquet_total_mb']:.2f} MB")
    print(f"DuckDB files:     {stats['duckdb_count']}")
    print(f"DuckDB storage:   {stats['duckdb_total_mb']:.2f} MB")
    print(f"{'=' * 70}")
    print(f"Total storage:    {stats['total_mb']:.2f} MB")


def main():
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(
        description="Exness Forex Tick Data Preprocessing Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process single month
  exness-preprocess process --year 2024 --month 8

  # Process date range
  exness-preprocess process --range 2024-01 2024-12

  # Query 1-hour OHLC
  exness-preprocess query --year 2024 --month 8 --timeframe 1h

  # Analyze tick data
  exness-preprocess analyze --year 2024 --month 8

  # Show storage statistics
  exness-preprocess stats
        """,
    )

    # Add version flag
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {importlib.metadata.version('exness-data-preprocess')}",
    )

    # Add config file flag (global)
    parser.add_argument(
        "--config",
        type=str,
        help="Path to config file (default: ~/.exness-preprocess.yaml)",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Process command
    process_parser = subparsers.add_parser("process", help="Process Exness tick data")
    process_parser.add_argument("--year", type=int, help="Year to process")
    process_parser.add_argument("--month", type=int, help="Month to process (1-12)")
    process_parser.add_argument(
        "--range", nargs=2, metavar=("START", "END"), help="Date range (YYYY-MM YYYY-MM)"
    )
    process_parser.add_argument("--pair", default="EURUSD", help="Currency pair (default: EURUSD)")
    process_parser.add_argument(
        "--keep-zip", action="store_true", help="Keep ZIP files after processing"
    )
    process_parser.add_argument("--base-dir", help="Base directory for data storage")
    process_parser.add_argument(
        "--dry-run", action="store_true", help="Preview operation without downloading"
    )
    process_parser.set_defaults(func=process_command)

    # Query command
    query_parser = subparsers.add_parser("query", help="Query OHLC data")
    query_parser.add_argument("--year", type=int, required=True, help="Year")
    query_parser.add_argument("--month", type=int, required=True, help="Month (1-12)")
    query_parser.add_argument("--pair", default="EURUSD", help="Currency pair (default: EURUSD)")
    query_parser.add_argument(
        "--timeframe",
        default="1m",
        choices=["1m", "5m", "15m", "30m", "1h", "4h", "1d"],
        help="Timeframe (default: 1m)",
    )
    query_parser.add_argument("--output", help="Output CSV file")
    query_parser.add_argument(
        "--head", type=int, default=10, help="Number of rows to display (default: 10)"
    )
    query_parser.add_argument("--base-dir", help="Base directory for data storage")
    query_parser.set_defaults(func=query_command)

    # Analyze command
    analyze_parser = subparsers.add_parser("analyze", help="Analyze tick data")
    analyze_parser.add_argument("--year", type=int, required=True, help="Year")
    analyze_parser.add_argument("--month", type=int, required=True, help="Month (1-12)")
    analyze_parser.add_argument("--pair", default="EURUSD", help="Currency pair (default: EURUSD)")
    analyze_parser.add_argument("--output", help="Output CSV file")
    analyze_parser.add_argument("--base-dir", help="Base directory for data storage")
    analyze_parser.set_defaults(func=analyze_command)

    # Stats command
    stats_parser = subparsers.add_parser("stats", help="Show storage statistics")
    stats_parser.add_argument("--base-dir", help="Base directory for data storage")
    stats_parser.set_defaults(func=stats_command)

    # Parse and execute
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Load config file (if provided or default exists)
    config = None
    if args.config:
        # Custom config path provided
        try:
            config = load_config(Path(args.config))
            if config is None:
                print(f"✗ Config file not found: {args.config}", file=sys.stderr)
                sys.exit(1)
        except Exception as e:
            print(f"✗ Config file error: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        # Try default config path (don't error if missing)
        try:
            config = load_config()
        except Exception as e:
            print(f"✗ Config file error: {e}", file=sys.stderr)
            sys.exit(1)

    # Apply config defaults (CLI flags override config)
    if config:
        if hasattr(args, 'base_dir') and not args.base_dir and config.base_dir:
            args.base_dir = str(config.base_dir)
        if hasattr(args, 'pair') and args.pair == "EURUSD" and config.default_pair:
            args.pair = config.default_pair
        if hasattr(args, 'timeframe') and args.timeframe == "1m" and config.default_timeframe:
            args.timeframe = config.default_timeframe

    try:
        args.func(args)
    except Exception as e:
        print(f"✗ Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
