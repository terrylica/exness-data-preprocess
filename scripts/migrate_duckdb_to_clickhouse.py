# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "duckdb>=1.0.0",
#     "pandas>=2.0.0",
#     "clickhouse-connect>=0.7.0",
#     "exness-data-preprocess",
# ]
# ///
"""
Migrate tick data from DuckDB to ClickHouse.

ADR: /docs/adr/2025-12-11-duckdb-removal-clickhouse.md

This script migrates historical tick data from DuckDB files (PDT/PST timezone)
to ClickHouse (UTC timezone) with the following transformations:

Source (DuckDB):
- Files: ~/eon/exness-data/{eurusd,xauusd}.duckdb
- Tables: raw_spread_ticks, standard_ticks
- Schema: Timestamp (TIMESTAMPTZ America/Vancouver), Bid (DOUBLE), Ask (DOUBLE)
- Total: ~271M records

Target (ClickHouse):
- Database: exness
- Tables: raw_spread_ticks, standard_ticks
- Schema: instrument (String), timestamp (DateTime64(6, 'UTC')), bid (Float64), ask (Float64)

Transformations:
1. Convert timezone from America/Vancouver (PST/PDT) to UTC
2. Add instrument column (EURUSD or XAUUSD)
3. Preserve microsecond precision

Prerequisites:
- Install exness-data-preprocess: cd ~/eon/exness-data-preprocess && uv pip install -e .
- Start ClickHouse: mise run clickhouse:start

Usage (from project root):
    uv run scripts/migrate_duckdb_to_clickhouse.py
    uv run scripts/migrate_duckdb_to_clickhouse.py --dry-run
    uv run scripts/migrate_duckdb_to_clickhouse.py --batch-size 1000000
    uv run scripts/migrate_duckdb_to_clickhouse.py --instrument EURUSD --table raw_spread_ticks
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import duckdb
import pandas as pd

if TYPE_CHECKING:
    from clickhouse_connect.driver import Client

    from exness_data_preprocess.clickhouse_manager import ClickHouseManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Migration configuration
DUCKDB_DIR = Path.home() / "eon" / "exness-data"
INSTRUMENTS = {
    "eurusd.duckdb": "EURUSD",
    "xauusd.duckdb": "XAUUSD",
}
TABLES = ["raw_spread_ticks", "standard_ticks"]
DEFAULT_BATCH_SIZE = 500_000


@dataclass
class MigrationStats:
    """Track migration statistics."""

    total_rows: int = 0
    rows_migrated: int = 0
    batches_processed: int = 0
    errors: int = 0
    start_time: float = 0.0

    def elapsed_seconds(self) -> float:
        """Get elapsed time in seconds."""
        return time.time() - self.start_time

    def rows_per_second(self) -> float:
        """Calculate migration rate."""
        elapsed = self.elapsed_seconds()
        if elapsed > 0:
            return self.rows_migrated / elapsed
        return 0.0

    def progress_percent(self) -> float:
        """Calculate progress percentage."""
        if self.total_rows > 0:
            return (self.rows_migrated / self.total_rows) * 100
        return 0.0

    def eta_seconds(self) -> float:
        """Estimate time remaining in seconds."""
        rate = self.rows_per_second()
        if rate > 0:
            remaining = self.total_rows - self.rows_migrated
            return remaining / rate
        return 0.0


def get_clickhouse_manager() -> "ClickHouseManager":
    """
    Get ClickHouseManager instance from exness_data_preprocess package.

    Returns:
        Configured ClickHouseManager instance

    Raises:
        ImportError: If exness_data_preprocess is not installed
    """
    try:
        from exness_data_preprocess.clickhouse_manager import ClickHouseManager

        return ClickHouseManager()
    except ImportError as e:
        logger.error(
            "Failed to import exness_data_preprocess. "
            "Ensure the package is installed: uv pip install -e ."
        )
        raise ImportError(
            "exness_data_preprocess not found. Run from project root with: "
            "uv run scripts/migrate_duckdb_to_clickhouse.py"
        ) from e


def get_clickhouse_client() -> "Client":
    """
    Get raw ClickHouse client for direct inserts.

    Returns:
        Connected ClickHouse client

    Raises:
        ImportError: If exness_data_preprocess is not installed
    """
    try:
        from exness_data_preprocess.clickhouse_client import get_client

        return get_client()
    except ImportError as e:
        logger.error(
            "Failed to import exness_data_preprocess. "
            "Ensure the package is installed: uv pip install -e ."
        )
        raise ImportError(
            "exness_data_preprocess not found. Run from project root with: "
            "uv run scripts/migrate_duckdb_to_clickhouse.py"
        ) from e


def count_duckdb_rows(duckdb_path: Path, table: str) -> int:
    """
    Count rows in a DuckDB table.

    Args:
        duckdb_path: Path to DuckDB file
        table: Table name

    Returns:
        Row count
    """
    con = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        result = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
        return result[0] if result else 0
    finally:
        con.close()


def read_duckdb_batch(
    duckdb_path: Path,
    table: str,
    offset: int,
    limit: int,
) -> pd.DataFrame:
    """
    Read a batch of rows from DuckDB with timezone conversion.

    DuckDB stores timestamps in America/Vancouver timezone (PST/PDT).
    This function converts them to UTC for ClickHouse.

    Args:
        duckdb_path: Path to DuckDB file
        table: Table name
        offset: Row offset for pagination
        limit: Maximum rows to read

    Returns:
        DataFrame with columns: timestamp (UTC), bid, ask
    """
    con = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        # DuckDB query with UTC conversion
        # The Timestamp column is TIMESTAMPTZ with America/Vancouver timezone
        # We convert to UTC using timezone() function for proper offset handling
        query = f"""
            SELECT
                timezone('UTC', Timestamp) AS timestamp,
                Bid AS bid,
                Ask AS ask
            FROM {table}
            ORDER BY Timestamp
            LIMIT {limit} OFFSET {offset}
        """
        df = con.execute(query).fetchdf()
        return df
    finally:
        con.close()


def insert_clickhouse_batch(
    client: "Client",
    df: pd.DataFrame,
    instrument: str,
    table: str,
) -> int:
    """
    Insert a batch of rows into ClickHouse.

    Args:
        client: ClickHouse client
        df: DataFrame with timestamp, bid, ask columns
        instrument: Instrument symbol (e.g., "EURUSD")
        table: Target table name (raw_spread_ticks or standard_ticks)

    Returns:
        Number of rows inserted
    """
    if df.empty:
        return 0

    # Add instrument column
    df = df.copy()
    df["instrument"] = instrument

    # Ensure timestamp is timezone-aware UTC
    if df["timestamp"].dt.tz is None:
        df["timestamp"] = df["timestamp"].dt.tz_localize("UTC")
    else:
        df["timestamp"] = df["timestamp"].dt.tz_convert("UTC")

    # Reorder columns to match ClickHouse schema
    df = df[["instrument", "timestamp", "bid", "ask"]]

    # Insert into ClickHouse
    client.insert(
        table=table,
        data=df,
        database="exness",
        column_names=["instrument", "timestamp", "bid", "ask"],
    )
    return len(df)


def migrate_table(
    duckdb_path: Path,
    instrument: str,
    table: str,
    client: "Client",
    batch_size: int,
    dry_run: bool,
    stats: MigrationStats,
) -> None:
    """
    Migrate a single table from DuckDB to ClickHouse.

    Args:
        duckdb_path: Path to DuckDB file
        instrument: Instrument symbol
        table: Table name
        client: ClickHouse client
        batch_size: Rows per batch
        dry_run: If True, don't actually insert
        stats: Statistics tracker
    """
    logger.info(f"Migrating {instrument} {table} from {duckdb_path.name}")

    # Count total rows
    total = count_duckdb_rows(duckdb_path, table)
    logger.info(f"  Total rows: {total:,}")

    if total == 0:
        logger.info("  Skipping empty table")
        return

    offset = 0
    table_rows = 0

    while offset < total:
        # Read batch from DuckDB
        df = read_duckdb_batch(duckdb_path, table, offset, batch_size)

        if df.empty:
            break

        batch_rows = len(df)

        if dry_run:
            logger.info(
                f"  [DRY RUN] Would insert batch {stats.batches_processed + 1}: "
                f"{batch_rows:,} rows (offset {offset:,})"
            )
        else:
            # Insert into ClickHouse
            inserted = insert_clickhouse_batch(client, df, instrument, table)
            stats.rows_migrated += inserted
            table_rows += inserted

        stats.batches_processed += 1
        offset += batch_size

        # Progress logging every 10 batches
        if stats.batches_processed % 10 == 0:
            rate = stats.rows_per_second()
            eta = stats.eta_seconds()
            eta_min = eta / 60

            logger.info(
                f"  Progress: {stats.rows_migrated:,}/{stats.total_rows:,} "
                f"({stats.progress_percent():.1f}%) | "
                f"Rate: {rate:,.0f} rows/s | "
                f"ETA: {eta_min:.1f} min"
            )

    logger.info(f"  Completed {table}: {table_rows:,} rows migrated")


def check_clickhouse_existing_data(client: "Client") -> dict[str, int]:
    """
    Check for existing data in ClickHouse tables.

    Args:
        client: ClickHouse client

    Returns:
        Dict mapping table names to row counts
    """
    counts = {}
    for table in TABLES:
        try:
            result = client.query(f"SELECT count() FROM exness.{table}")
            counts[table] = result.first_row[0]
        except Exception:
            counts[table] = 0
    return counts


def main() -> int:
    """
    Main entry point for the migration script.

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    parser = argparse.ArgumentParser(
        description="Migrate DuckDB tick data to ClickHouse",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview migration without inserting data",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help=f"Rows per batch (default: {DEFAULT_BATCH_SIZE:,})",
    )
    parser.add_argument(
        "--table",
        choices=TABLES,
        help="Migrate only this table (default: both tables)",
    )
    parser.add_argument(
        "--instrument",
        choices=list(INSTRUMENTS.values()),
        help="Migrate only this instrument (default: all instruments)",
    )
    parser.add_argument(
        "--skip-existing-check",
        action="store_true",
        help="Skip checking for existing data in ClickHouse",
    )
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("DuckDB to ClickHouse Migration")
    logger.info("=" * 60)

    if args.dry_run:
        logger.info("[DRY RUN MODE] No data will be inserted")

    logger.info(f"Batch size: {args.batch_size:,}")

    # Validate DuckDB files exist
    missing_files = []
    for filename in INSTRUMENTS:
        path = DUCKDB_DIR / filename
        if not path.exists():
            missing_files.append(path)

    if missing_files:
        logger.error("Missing DuckDB files:")
        for f in missing_files:
            logger.error(f"  - {f}")
        return 1

    # Initialize ClickHouse
    logger.info("Connecting to ClickHouse...")
    try:
        manager = get_clickhouse_manager()
        client = manager.client

        # Ensure schema exists
        logger.info("Ensuring ClickHouse schema exists...")
        manager.ensure_schema()
        logger.info("Schema verified")

    except Exception as e:
        logger.error(f"Failed to connect to ClickHouse: {e}")
        logger.error("Ensure ClickHouse is running: mise run clickhouse:start")
        return 1

    # Check for existing data
    if not args.skip_existing_check:
        logger.info("Checking for existing data in ClickHouse...")
        existing = check_clickhouse_existing_data(client)
        has_existing = any(count > 0 for count in existing.values())

        if has_existing:
            logger.warning("Existing data found in ClickHouse:")
            for table, count in existing.items():
                logger.warning(f"  {table}: {count:,} rows")
            logger.warning(
                "ReplacingMergeTree will deduplicate duplicates at merge time, "
                "but this may lead to temporary duplicate data until OPTIMIZE is run."
            )
            if not args.dry_run:
                response = input("Continue with migration? [y/N] ")
                if response.lower() != "y":
                    logger.info("Migration cancelled")
                    return 0

    # Calculate total rows to migrate
    logger.info("Calculating total rows to migrate...")
    stats = MigrationStats()

    tables_to_migrate = [args.table] if args.table else TABLES

    for filename, instrument in INSTRUMENTS.items():
        if args.instrument and instrument != args.instrument:
            continue

        path = DUCKDB_DIR / filename
        for table in tables_to_migrate:
            count = count_duckdb_rows(path, table)
            stats.total_rows += count
            logger.info(f"  {instrument} {table}: {count:,}")

    logger.info(f"Total rows to migrate: {stats.total_rows:,}")

    # Start migration
    logger.info("-" * 60)
    logger.info("Starting migration...")
    stats.start_time = time.time()

    try:
        for filename, instrument in INSTRUMENTS.items():
            if args.instrument and instrument != args.instrument:
                continue

            path = DUCKDB_DIR / filename
            for table in tables_to_migrate:
                migrate_table(
                    duckdb_path=path,
                    instrument=instrument,
                    table=table,
                    client=client,
                    batch_size=args.batch_size,
                    dry_run=args.dry_run,
                    stats=stats,
                )

    except KeyboardInterrupt:
        logger.warning("Migration interrupted by user")
        logger.info(f"Rows migrated before interrupt: {stats.rows_migrated:,}")
        return 1

    except Exception as e:
        logger.error(f"Migration failed: {e}")
        stats.errors += 1
        return 1

    finally:
        # Close ClickHouse connection
        try:
            client.close()
        except Exception:
            pass

    # Summary
    elapsed = stats.elapsed_seconds()
    logger.info("-" * 60)
    logger.info("Migration Summary")
    logger.info("-" * 60)
    logger.info(f"Total rows: {stats.total_rows:,}")
    logger.info(f"Rows migrated: {stats.rows_migrated:,}")
    logger.info(f"Batches processed: {stats.batches_processed:,}")
    logger.info(f"Elapsed time: {elapsed / 60:.1f} minutes")
    logger.info(f"Average rate: {stats.rows_per_second():,.0f} rows/s")
    logger.info(f"Errors: {stats.errors}")

    if args.dry_run:
        logger.info("[DRY RUN] No data was actually inserted")

    if stats.errors > 0:
        logger.error("Migration completed with errors")
        return 1

    logger.info("Migration completed successfully")
    return 0


if __name__ == "__main__":
    sys.exit(main())
