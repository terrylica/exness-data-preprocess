# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pandas>=2.0.0",
#     "requests>=2.31.0",
#     "clickhouse-connect>=0.7.0",
#     "exness-data-preprocess",
# ]
# ///
"""
Validate ClickHouse data against original Exness source.

ADR: /docs/adr/2025-12-11-duckdb-removal-clickhouse.md

This script validates data integrity by comparing ClickHouse data against
the original Exness tick data source. It downloads a sample of data from
the online source, queries ClickHouse for the same date range, and performs
comprehensive validation checks.

Validation Checks:
1. Row counts match (within tolerance for deduplication)
2. Timestamp ranges match
3. Bid/Ask values are identical (within floating point tolerance)
4. No data corruption during migration

Data Sources:
- Online: https://ticks.ex2archive.com/ticks/{SYMBOL}/{YYYY}/{MM}/Exness_{SYMBOL}_{YYYY}_{MM}.zip
- ClickHouse: exness.raw_spread_ticks, exness.standard_ticks

Usage (from project root):
    uv run scripts/validate_migration_data.py
    uv run scripts/validate_migration_data.py --symbol EURUSD --date 2024-06-15
    uv run scripts/validate_migration_data.py --symbol XAUUSD --date 2024-03-01
    uv run scripts/validate_migration_data.py --variant standard
"""

from __future__ import annotations

import argparse
import io
import logging
import sys
import zipfile
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import TYPE_CHECKING

import pandas as pd
import requests

if TYPE_CHECKING:
    from clickhouse_connect.driver import Client

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Validation configuration
DEFAULT_SYMBOL = "EURUSD"
DEFAULT_DATE = "2024-06-15"  # Mid-year date likely to have data
DEFAULT_VARIANT = "raw_spread"  # raw_spread or standard

# Floating point comparison tolerance (for bid/ask prices)
PRICE_TOLERANCE = 1e-10

# Row count tolerance for deduplication differences
ROW_COUNT_TOLERANCE_PERCENT = 0.1  # 0.1% tolerance


@dataclass
class ValidationResult:
    """Track validation results."""

    symbol: str
    date: str
    variant: str
    online_row_count: int = 0
    clickhouse_row_count: int = 0
    matching_rows: int = 0
    mismatched_rows: int = 0
    online_min_timestamp: pd.Timestamp | None = None
    online_max_timestamp: pd.Timestamp | None = None
    clickhouse_min_timestamp: pd.Timestamp | None = None
    clickhouse_max_timestamp: pd.Timestamp | None = None
    bid_mismatches: list[dict] = field(default_factory=list)
    ask_mismatches: list[dict] = field(default_factory=list)
    timestamp_mismatches: list[dict] = field(default_factory=list)
    passed: bool = False
    error_message: str = ""

    def summary(self) -> str:
        """Generate validation summary."""
        lines = [
            "=" * 60,
            "VALIDATION SUMMARY",
            "=" * 60,
            f"Symbol: {self.symbol}",
            f"Date: {self.date}",
            f"Variant: {self.variant}",
            "-" * 60,
            "ROW COUNTS:",
            f"  Online source: {self.online_row_count:,}",
            f"  ClickHouse:    {self.clickhouse_row_count:,}",
            f"  Difference:    {abs(self.online_row_count - self.clickhouse_row_count):,} "
            f"({self._row_count_diff_percent():.2f}%)",
            "-" * 60,
            "TIMESTAMP RANGES:",
            f"  Online:     {self.online_min_timestamp} to {self.online_max_timestamp}",
            f"  ClickHouse: {self.clickhouse_min_timestamp} to {self.clickhouse_max_timestamp}",
            "-" * 60,
            "DATA INTEGRITY:",
            f"  Matching rows:    {self.matching_rows:,}",
            f"  Mismatched rows:  {self.mismatched_rows:,}",
            f"  Bid mismatches:   {len(self.bid_mismatches):,}",
            f"  Ask mismatches:   {len(self.ask_mismatches):,}",
            "-" * 60,
        ]

        if self.passed:
            lines.append("RESULT: PASSED")
        else:
            lines.append(f"RESULT: FAILED - {self.error_message}")

        lines.append("=" * 60)
        return "\n".join(lines)

    def _row_count_diff_percent(self) -> float:
        """Calculate row count difference as percentage."""
        if self.online_row_count == 0:
            return 0.0
        return abs(self.online_row_count - self.clickhouse_row_count) / self.online_row_count * 100


def get_clickhouse_client() -> "Client":
    """
    Get ClickHouse client from exness_data_preprocess package.

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
            "uv run scripts/validate_migration_data.py"
        ) from e


def build_exness_url(symbol: str, year: int, month: int, variant: str) -> str:
    """
    Build Exness download URL for given parameters.

    Args:
        symbol: Instrument symbol (e.g., "EURUSD")
        year: Year (e.g., 2024)
        month: Month (1-12)
        variant: "raw_spread" or "standard"

    Returns:
        Full download URL
    """
    if variant == "raw_spread":
        path_symbol = f"{symbol}_Raw_Spread"
        file_symbol = f"{symbol}_Raw_Spread"
    else:
        # Standard variant uses plain symbol
        path_symbol = symbol
        file_symbol = symbol

    url = (
        f"https://ticks.ex2archive.com/ticks/{path_symbol}/"
        f"{year}/{month:02d}/Exness_{file_symbol}_{year}_{month:02d}.zip"
    )
    return url


def download_and_parse_exness_data(
    symbol: str, year: int, month: int, variant: str
) -> pd.DataFrame:
    """
    Download and parse Exness tick data from online source.

    Args:
        symbol: Instrument symbol (e.g., "EURUSD")
        year: Year (e.g., 2024)
        month: Month (1-12)
        variant: "raw_spread" or "standard"

    Returns:
        DataFrame with columns: timestamp, bid, ask (UTC)

    Raises:
        requests.HTTPError: If download fails
        zipfile.BadZipFile: If file is not a valid ZIP
    """
    url = build_exness_url(symbol, year, month, variant)
    logger.info(f"Downloading from: {url}")

    response = requests.get(url, timeout=120, stream=True)
    response.raise_for_status()

    # Get file size from headers if available
    content_length = response.headers.get("content-length")
    if content_length:
        logger.info(f"Download size: {int(content_length) / 1024 / 1024:.2f} MB")

    # Read into memory
    zip_data = io.BytesIO(response.content)
    logger.info(f"Downloaded {len(response.content) / 1024 / 1024:.2f} MB")

    # Build expected CSV filename inside ZIP
    if variant == "raw_spread":
        csv_name = f"Exness_{symbol}_Raw_Spread_{year}_{month:02d}.csv"
    else:
        csv_name = f"Exness_{symbol}_{year}_{month:02d}.csv"

    # Extract and parse CSV
    with zipfile.ZipFile(zip_data, "r") as zf:
        logger.info(f"Extracting: {csv_name}")
        with zf.open(csv_name) as csv_file:
            df = pd.read_csv(
                csv_file,
                usecols=["Timestamp", "Bid", "Ask"],
                parse_dates=["Timestamp"],
            )

    # Normalize column names to lowercase
    df = df.rename(columns={"Timestamp": "timestamp", "Bid": "bid", "Ask": "ask"})

    # Convert to UTC timezone-aware
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)

    logger.info(f"Parsed {len(df):,} ticks from online source")
    return df


def filter_dataframe_by_date(df: pd.DataFrame, target_date: date) -> pd.DataFrame:
    """
    Filter DataFrame to only include ticks from a specific date.

    Args:
        df: DataFrame with timestamp column
        target_date: Date to filter for

    Returns:
        Filtered DataFrame
    """
    # Create start and end of day in UTC
    start = pd.Timestamp(target_date, tz="UTC")
    end = start + pd.Timedelta(days=1)

    mask = (df["timestamp"] >= start) & (df["timestamp"] < end)
    filtered = df[mask].copy()

    logger.info(f"Filtered to {len(filtered):,} ticks for date {target_date}")
    return filtered


def query_clickhouse_for_date(
    client: "Client",
    symbol: str,
    target_date: date,
    variant: str,
) -> pd.DataFrame:
    """
    Query ClickHouse for ticks on a specific date.

    Args:
        client: ClickHouse client
        symbol: Instrument symbol (e.g., "EURUSD")
        target_date: Date to query
        variant: "raw_spread" or "standard"

    Returns:
        DataFrame with columns: timestamp, bid, ask
    """
    table = f"{variant}_ticks"

    query = f"""
        SELECT
            timestamp,
            bid,
            ask
        FROM exness.{table}
        WHERE instrument = {{symbol:String}}
          AND toDate(timestamp) = {{date:Date}}
        ORDER BY timestamp
    """

    logger.info(f"Querying ClickHouse {table} for {symbol} on {target_date}")

    result = client.query(
        query,
        parameters={"symbol": symbol.upper(), "date": str(target_date)},
    )

    # Convert to DataFrame
    df = pd.DataFrame(
        result.result_rows,
        columns=["timestamp", "bid", "ask"],
    )

    # Ensure timestamp is timezone-aware UTC
    if len(df) > 0:
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)

    logger.info(f"Retrieved {len(df):,} ticks from ClickHouse")
    return df


def compare_dataframes(
    df_online: pd.DataFrame,
    df_clickhouse: pd.DataFrame,
    result: ValidationResult,
) -> None:
    """
    Compare two DataFrames and update validation result.

    Args:
        df_online: DataFrame from online source
        df_clickhouse: DataFrame from ClickHouse
        result: ValidationResult to update
    """
    # Update row counts
    result.online_row_count = len(df_online)
    result.clickhouse_row_count = len(df_clickhouse)

    # Update timestamp ranges
    if len(df_online) > 0:
        result.online_min_timestamp = df_online["timestamp"].min()
        result.online_max_timestamp = df_online["timestamp"].max()

    if len(df_clickhouse) > 0:
        result.clickhouse_min_timestamp = df_clickhouse["timestamp"].min()
        result.clickhouse_max_timestamp = df_clickhouse["timestamp"].max()

    # If either is empty, mark as failed
    if len(df_online) == 0:
        result.error_message = "No data found in online source"
        return

    if len(df_clickhouse) == 0:
        result.error_message = "No data found in ClickHouse"
        return

    # Merge on timestamp to compare values
    # Use outer merge to capture all differences
    merged = pd.merge(
        df_online,
        df_clickhouse,
        on="timestamp",
        how="outer",
        suffixes=("_online", "_clickhouse"),
        indicator=True,
    )

    # Count matches and mismatches
    both_present = merged[merged["_merge"] == "both"]
    only_online = merged[merged["_merge"] == "left_only"]
    only_clickhouse = merged[merged["_merge"] == "right_only"]

    result.matching_rows = len(both_present)
    result.mismatched_rows = len(only_online) + len(only_clickhouse)

    # Check bid/ask values for rows present in both
    if len(both_present) > 0:
        bid_diff = (both_present["bid_online"] - both_present["bid_clickhouse"]).abs()
        ask_diff = (both_present["ask_online"] - both_present["ask_clickhouse"]).abs()

        bid_mismatch_mask = bid_diff > PRICE_TOLERANCE
        ask_mismatch_mask = ask_diff > PRICE_TOLERANCE

        bid_mismatches = both_present[bid_mismatch_mask]
        ask_mismatches = both_present[ask_mismatch_mask]

        # Store sample mismatches (first 5)
        for _, row in bid_mismatches.head(5).iterrows():
            result.bid_mismatches.append(
                {
                    "timestamp": row["timestamp"],
                    "online_bid": row["bid_online"],
                    "clickhouse_bid": row["bid_clickhouse"],
                    "diff": row["bid_online"] - row["bid_clickhouse"],
                }
            )

        for _, row in ask_mismatches.head(5).iterrows():
            result.ask_mismatches.append(
                {
                    "timestamp": row["timestamp"],
                    "online_ask": row["ask_online"],
                    "clickhouse_ask": row["ask_clickhouse"],
                    "diff": row["ask_online"] - row["ask_clickhouse"],
                }
            )

    # Log timestamp mismatches (sample)
    if len(only_online) > 0:
        logger.warning(
            f"Found {len(only_online)} timestamps only in online source (sample): "
            f"{only_online['timestamp'].head(3).tolist()}"
        )

    if len(only_clickhouse) > 0:
        logger.warning(
            f"Found {len(only_clickhouse)} timestamps only in ClickHouse (sample): "
            f"{only_clickhouse['timestamp'].head(3).tolist()}"
        )


def validate_results(result: ValidationResult) -> None:
    """
    Validate results and set pass/fail status.

    Args:
        result: ValidationResult to validate
    """
    # Already has an error message from comparison
    if result.error_message:
        return

    errors = []

    # Check row count difference
    if result.online_row_count > 0:
        diff_percent = result._row_count_diff_percent()
        if diff_percent > ROW_COUNT_TOLERANCE_PERCENT:
            errors.append(
                f"Row count difference ({diff_percent:.2f}%) exceeds "
                f"tolerance ({ROW_COUNT_TOLERANCE_PERCENT}%)"
            )

    # Check for bid/ask mismatches
    if len(result.bid_mismatches) > 0:
        errors.append(f"{len(result.bid_mismatches)} bid price mismatches")

    if len(result.ask_mismatches) > 0:
        errors.append(f"{len(result.ask_mismatches)} ask price mismatches")

    # Check timestamp range alignment
    if result.online_min_timestamp and result.clickhouse_min_timestamp:
        if result.online_min_timestamp != result.clickhouse_min_timestamp:
            errors.append(
                f"Min timestamp mismatch: online={result.online_min_timestamp}, "
                f"clickhouse={result.clickhouse_min_timestamp}"
            )

    if result.online_max_timestamp and result.clickhouse_max_timestamp:
        if result.online_max_timestamp != result.clickhouse_max_timestamp:
            errors.append(
                f"Max timestamp mismatch: online={result.online_max_timestamp}, "
                f"clickhouse={result.clickhouse_max_timestamp}"
            )

    if errors:
        result.error_message = "; ".join(errors)
        result.passed = False
    else:
        result.passed = True


def run_validation(
    symbol: str,
    target_date: date,
    variant: str,
) -> ValidationResult:
    """
    Run full validation workflow.

    Args:
        symbol: Instrument symbol (e.g., "EURUSD")
        target_date: Date to validate
        variant: "raw_spread" or "standard"

    Returns:
        ValidationResult with all validation data
    """
    result = ValidationResult(
        symbol=symbol,
        date=str(target_date),
        variant=variant,
    )

    try:
        # Step 1: Download and parse online data
        logger.info("-" * 60)
        logger.info("STEP 1: Downloading online data")
        df_online_full = download_and_parse_exness_data(
            symbol=symbol,
            year=target_date.year,
            month=target_date.month,
            variant=variant,
        )

        # Filter to specific date
        df_online = filter_dataframe_by_date(df_online_full, target_date)

        # Step 2: Query ClickHouse
        logger.info("-" * 60)
        logger.info("STEP 2: Querying ClickHouse")
        client = get_clickhouse_client()
        try:
            df_clickhouse = query_clickhouse_for_date(
                client=client,
                symbol=symbol,
                target_date=target_date,
                variant=variant,
            )
        finally:
            client.close()

        # Step 3: Compare data
        logger.info("-" * 60)
        logger.info("STEP 3: Comparing data")
        compare_dataframes(df_online, df_clickhouse, result)

        # Step 4: Validate results
        logger.info("-" * 60)
        logger.info("STEP 4: Validating results")
        validate_results(result)

    except requests.HTTPError as e:
        result.error_message = f"Failed to download online data: {e}"
        logger.error(result.error_message)

    except Exception as e:
        result.error_message = f"Validation error: {e}"
        logger.exception("Validation failed with exception")

    return result


def main() -> int:
    """
    Main entry point for validation script.

    Returns:
        Exit code (0 for success/pass, 1 for failure)
    """
    parser = argparse.ArgumentParser(
        description="Validate ClickHouse data against Exness online source",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--symbol",
        default=DEFAULT_SYMBOL,
        help=f"Instrument symbol (default: {DEFAULT_SYMBOL})",
    )
    parser.add_argument(
        "--date",
        default=DEFAULT_DATE,
        help=f"Date to validate (YYYY-MM-DD, default: {DEFAULT_DATE})",
    )
    parser.add_argument(
        "--variant",
        choices=["raw_spread", "standard"],
        default=DEFAULT_VARIANT,
        help=f"Data variant (default: {DEFAULT_VARIANT})",
    )
    args = parser.parse_args()

    # Parse date
    try:
        target_date = datetime.strptime(args.date, "%Y-%m-%d").date()
    except ValueError:
        logger.error(f"Invalid date format: {args.date}. Use YYYY-MM-DD")
        return 1

    logger.info("=" * 60)
    logger.info("DATA VALIDATION: Exness Online vs ClickHouse")
    logger.info("=" * 60)
    logger.info(f"Symbol:  {args.symbol}")
    logger.info(f"Date:    {target_date}")
    logger.info(f"Variant: {args.variant}")
    logger.info("=" * 60)

    # Run validation
    result = run_validation(
        symbol=args.symbol,
        target_date=target_date,
        variant=args.variant,
    )

    # Print summary
    print("\n")
    print(result.summary())

    # Print sample mismatches if any
    if result.bid_mismatches:
        print("\nSample Bid Mismatches:")
        for mismatch in result.bid_mismatches:
            print(
                f"  {mismatch['timestamp']}: "
                f"online={mismatch['online_bid']:.6f}, "
                f"clickhouse={mismatch['clickhouse_bid']:.6f}, "
                f"diff={mismatch['diff']:.10f}"
            )

    if result.ask_mismatches:
        print("\nSample Ask Mismatches:")
        for mismatch in result.ask_mismatches:
            print(
                f"  {mismatch['timestamp']}: "
                f"online={mismatch['online_ask']:.6f}, "
                f"clickhouse={mismatch['clickhouse_ask']:.6f}, "
                f"diff={mismatch['diff']:.10f}"
            )

    return 0 if result.passed else 1


if __name__ == "__main__":
    sys.exit(main())
