#!/usr/bin/env python3
"""
Phase 1: Data Loading & Validation
==================================
Load 32 files (16 months × 2 variants), validate format, check ASOF merge rates

SLOs:
- Availability: ≥99% load success (max 1 failed file)
- Correctness: Exact format match, merge rate ≥99%
- Observability: Per-file logging, error propagation with context
"""

import glob
import logging
import zipfile
from pathlib import Path

import pandas as pd

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


# Custom exceptions (error propagation contract)
class MultiPeriodValidationError(Exception):
    """Base exception for multi-period validation"""

    pass


class DataLoadError(MultiPeriodValidationError):
    """Failed to load data file"""

    def __init__(self, filepath, cause):
        self.filepath = filepath
        self.cause = cause
        super().__init__(f"Failed to load {filepath}: {cause}")


class FormatValidationError(MultiPeriodValidationError):
    """CSV format validation failed"""

    def __init__(self, filepath, expected, actual):
        self.filepath = filepath
        self.expected = expected
        self.actual = actual
        super().__init__(f"Format error in {filepath}: expected {expected}, got {actual}")


class MergeError(MultiPeriodValidationError):
    """ASOF merge failed"""

    def __init__(self, std_file, raw_file, merge_rate):
        self.std_file = std_file
        self.raw_file = raw_file
        self.merge_rate = merge_rate
        super().__init__(
            f"Merge failed: {std_file} + {raw_file} → {merge_rate:.1%} success (target: ≥99%)"
        )


# Constants
DATA_DIR = "/tmp"
ZERO_SPREAD_THRESHOLD = 0.00001
MERGE_TOLERANCE_SEC = 10
MIN_MERGE_RATE = 0.99


def load_exness_zip(zip_path):
    """
    Load Exness tick data from ZIP file

    Raises:
        DataLoadError: If file cannot be loaded
        FormatValidationError: If CSV format is invalid
    """
    try:
        with zipfile.ZipFile(zip_path) as zf:
            csv_files = [f for f in zf.namelist() if f.endswith(".csv")]

            if len(csv_files) != 1:
                raise FormatValidationError(zip_path, "1 CSV file", f"{len(csv_files)} CSV files")

            csv_file = csv_files[0]

            with zf.open(csv_file) as f:
                df = pd.read_csv(f)  # Has header row

            # Validate format
            expected_cols = ["Exness", "Symbol", "Timestamp", "Bid", "Ask"]
            if list(df.columns) != expected_cols:
                raise FormatValidationError(
                    zip_path, f"columns {expected_cols}", f"columns {list(df.columns)}"
                )

            # Extract only needed columns and convert types
            df = df[["Timestamp", "Bid", "Ask"]].copy()
            df.columns = ["timestamp_str", "bid", "ask"]

            # Convert types
            df["bid"] = pd.to_numeric(df["bid"], errors="coerce")
            df["ask"] = pd.to_numeric(df["ask"], errors="coerce")

            # Check for NaN
            if df.isnull().any().any():
                nan_count = df.isnull().sum().sum()
                raise FormatValidationError(
                    zip_path, "no NaN values", f"{nan_count} NaN values found"
                )

            # Parse timestamp (ISO 8601 format)
            df["timestamp"] = pd.to_datetime(df["timestamp_str"], utc=True)

            # Add derived columns
            df["spread"] = df["ask"] - df["bid"]
            df["mid"] = (df["bid"] + df["ask"]) / 2

            # Drop temporary column
            df = df.drop(columns=["timestamp_str"])

            return df.sort_values("timestamp").reset_index(drop=True)

    except zipfile.BadZipFile as e:
        raise DataLoadError(zip_path, f"Corrupt ZIP file: {e}") from e
    except pd.errors.EmptyDataError as e:
        raise DataLoadError(zip_path, f"Empty CSV: {e}") from e
    except Exception as e:
        raise DataLoadError(zip_path, str(e)) from e


def validate_asof_merge(std_df, raw_df, std_file, raw_file):
    """
    Validate ASOF merge between Standard and Raw_Spread

    Raises:
        MergeError: If merge rate < 99%
    """
    # Filter to zero-spread events
    zero_spread_df = raw_df[raw_df["spread"] <= ZERO_SPREAD_THRESHOLD].copy()

    if len(zero_spread_df) == 0:
        raise MergeError(std_file, raw_file, 0.0)

    # ASOF merge
    merged = pd.merge_asof(
        zero_spread_df[["timestamp", "mid"]].rename(columns={"mid": "raw_mid"}),
        std_df[["timestamp", "bid", "ask"]].rename(columns={"bid": "std_bid", "ask": "std_ask"}),
        on="timestamp",
        direction="backward",
        tolerance=pd.Timedelta(seconds=MERGE_TOLERANCE_SEC),
    )

    # Calculate merge success rate
    merge_rate = merged.dropna().shape[0] / len(zero_spread_df)

    if merge_rate < MIN_MERGE_RATE:
        raise MergeError(std_file, raw_file, merge_rate)

    return merge_rate, len(zero_spread_df), merged.dropna().shape[0]


def analyze_file_pair(std_zip, raw_zip):
    """
    Analyze a Standard + Raw_Spread file pair

    Returns:
        dict: Validation metrics for the pair
    """
    std_file = Path(std_zip).name
    raw_file = Path(raw_zip).name

    # Extract month from filename
    # Format: Exness_EURUSD_2024_09.zip
    parts = std_file.replace(".zip", "").split("_")
    year = parts[2]
    month = parts[3]
    month_str = f"{year}-{month}"

    logger.info(f"Loading {month_str}...")

    # Load data
    try:
        std_df = load_exness_zip(std_zip)
        raw_df = load_exness_zip(raw_zip)
    except (DataLoadError, FormatValidationError) as e:
        logger.error(f"Load failed for {month_str}: {e}")
        raise

    # Validate merge
    try:
        merge_rate, zero_spread_count, merged_count = validate_asof_merge(
            std_df, raw_df, std_file, raw_file
        )
    except MergeError as e:
        logger.error(f"Merge validation failed for {month_str}: {e}")
        raise

    # Calculate statistics
    result = {
        "month": month_str,
        "std_file": std_file,
        "raw_file": raw_file,
        "std_ticks": len(std_df),
        "raw_ticks": len(raw_df),
        "zero_spread_ticks": zero_spread_count,
        "merged_ticks": merged_count,
        "merge_rate_pct": merge_rate * 100,
        "std_mean_spread_bps": std_df["spread"].mean() * 10000,
        "raw_zero_pct": (raw_df["spread"] <= ZERO_SPREAD_THRESHOLD).sum() / len(raw_df) * 100,
        "validation_status": "PASS",
    }

    logger.info(
        f"  {month_str}: {len(std_df):,} std ticks, "
        f"{zero_spread_count:,} zero-spread, "
        f"{merge_rate * 100:.1f}% merged"
    )

    return result


def main():
    """
    Phase 1: Data Loading & Validation
    """
    logger.info("=" * 80)
    logger.info("PHASE 1: DATA LOADING & VALIDATION")
    logger.info("=" * 80)

    # Find all file pairs
    std_files = sorted(glob.glob(f"{DATA_DIR}/Exness_EURUSD_20*.zip"))
    raw_files = sorted(glob.glob(f"{DATA_DIR}/Exness_EURUSD_Raw_Spread_20*.zip"))

    if len(std_files) != 16:
        raise DataLoadError(DATA_DIR, f"Expected 16 EURUSD files, found {len(std_files)}")

    if len(raw_files) != 16:
        raise DataLoadError(
            DATA_DIR, f"Expected 16 EURUSD_Raw_Spread files, found {len(raw_files)}"
        )

    logger.info(f"Found {len(std_files)} EURUSD + {len(raw_files)} Raw_Spread files")
    logger.info("")

    # Process all file pairs
    results = []
    failed_count = 0

    for std_file, raw_file in zip(std_files, raw_files):
        try:
            result = analyze_file_pair(std_file, raw_file)
            results.append(result)
        except MultiPeriodValidationError as e:
            # Log error but continue (to see all failures)
            result = {
                "month": "ERROR",
                "std_file": Path(std_file).name,
                "raw_file": Path(raw_file).name,
                "validation_status": "FAIL",
                "error": str(e),
            }
            results.append(result)
            failed_count += 1

    # Create results DataFrame
    results_df = pd.DataFrame(results)

    # Calculate SLO metrics
    total_files = len(results_df)
    pass_count = (results_df["validation_status"] == "PASS").sum()
    availability_pct = pass_count / total_files * 100

    logger.info("")
    logger.info("=" * 80)
    logger.info("VALIDATION SUMMARY")
    logger.info("=" * 80)
    logger.info(f"Total file pairs: {total_files}")
    logger.info(f"Passed: {pass_count}")
    logger.info(f"Failed: {failed_count}")
    logger.info(f"Availability SLO: {availability_pct:.1f}% (target: ≥99%)")

    # Check availability SLO
    if availability_pct < 99.0:
        logger.error(f"❌ Availability SLO FAILED: {availability_pct:.1f}% < 99%")
        slo_status = "FAIL"
    else:
        logger.info(f"✅ Availability SLO PASSED: {availability_pct:.1f}% ≥ 99%")
        slo_status = "PASS"

    # Check correctness SLO (Sep 2024 baseline comparison)
    sep_2024 = results_df[results_df["month"] == "2024-09"]
    if len(sep_2024) == 1:
        sep_merge_rate = sep_2024["merge_rate_pct"].values[0]
        logger.info("")
        logger.info("Baseline Reproduction Check (Sep 2024):")
        logger.info(f"  Merge rate: {sep_merge_rate:.1f}% (expected: ≥99%)")

        if sep_merge_rate >= 99.0:
            logger.info("  ✅ Correctness SLO PASSED")
        else:
            logger.error(f"  ❌ Correctness SLO FAILED: {sep_merge_rate:.1f}% < 99%")
            slo_status = "FAIL"

    # Save results
    output_file = f"{DATA_DIR}/multiperiod_data_validation.csv"
    results_df.to_csv(output_file, index=False)
    logger.info("")
    logger.info(f"✅ Saved: {output_file}")

    # Summary statistics
    if pass_count > 0:
        passed_df = results_df[results_df["validation_status"] == "PASS"]

        logger.info("")
        logger.info("Dataset Statistics (Passed Files Only):")
        logger.info(f"  Total ticks (std): {passed_df['std_ticks'].sum():,}")
        logger.info(f"  Total zero-spread: {passed_df['zero_spread_ticks'].sum():,}")
        logger.info(f"  Total merged: {passed_df['merged_ticks'].sum():,}")
        logger.info(f"  Mean merge rate: {passed_df['merge_rate_pct'].mean():.2f}%")
        logger.info(f"  Mean spread (std): {passed_df['std_mean_spread_bps'].mean():.3f} bps")
        logger.info(f"  Mean zero-spread %: {passed_df['raw_zero_pct'].mean():.2f}%")

    logger.info("")
    logger.info("=" * 80)
    logger.info(f"PHASE 1 COMPLETE - Status: {slo_status}")
    logger.info("=" * 80)

    # Raise exception if SLO failed (strict error propagation)
    if slo_status == "FAIL":
        raise MultiPeriodValidationError(
            f"Phase 1 failed: {failed_count} files failed, availability {availability_pct:.1f}% < 99%"
        )


if __name__ == "__main__":
    try:
        main()
    except MultiPeriodValidationError as e:
        logger.error(f"FATAL: {e}")
        exit(1)
