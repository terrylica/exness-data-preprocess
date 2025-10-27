"""
Core processor for Exness forex tick data.

Architecture (v2.0.0 - Unified Single-File Multi-Year):
1. One DuckDB file per instrument (e.g., eurusd.duckdb)
2. Three tables: raw_spread_ticks, standard_ticks, ohlc_1m
3. Dual-variant downloads (Raw_Spread + Standard) for Phase7 compliance
4. Incremental updates with automatic gap detection
5. Metadata table for coverage tracking

Phase7 Schema (v1.6.0 - 30 columns):
- Timestamp, Open, High, Low, Close (BID-based from Raw_Spread)
- raw_spread_avg, standard_spread_avg (dual spread tracking)
- tick_count_raw_spread, tick_count_standard (dual tick counts)
- range_per_spread, range_per_tick, body_per_spread, body_per_tick (normalized metrics)
- ny_hour, london_hour, ny_session, london_session (timezone/session tracking)
- is_us_holiday, is_uk_holiday, is_major_holiday (official holidays only)
- is_{exchange}_session for 10 exchanges with trading hour detection (nyse, lse, xswx, xfra, xtse, xnze, xtks, xasx, xhkg, xses)

Storage: ~135 MB/year, ~405 MB for 3 years per instrument
"""

from pathlib import Path
from typing import List, Optional, Tuple

import duckdb
import pandas as pd

from exness_data_preprocess.database_manager import DatabaseManager
from exness_data_preprocess.downloader import ExnessDownloader
from exness_data_preprocess.gap_detector import GapDetector
from exness_data_preprocess.models import (
    CoverageInfo,
    PairType,
    TimeframeType,
    UpdateResult,
    VariantType,
    supported_pairs,
    supported_timeframes,
    supported_variants,
)
from exness_data_preprocess.ohlc_generator import OHLCGenerator
from exness_data_preprocess.query_engine import QueryEngine
from exness_data_preprocess.session_detector import SessionDetector
from exness_data_preprocess.tick_loader import TickLoader


class ExnessDataProcessor:
    """
    Process Exness forex tick data with unified multi-year architecture.

    Architecture (v2.0.0):
    - One DuckDB file per instrument (eurusd.duckdb not monthly files)
    - Dual-variant storage (Raw_Spread + Standard) for Phase7
    - Incremental updates with automatic gap detection
    - 30-column OHLC schema (v1.6.0) with dual spreads, tick counts, normalized metrics, timezone/session tracking, holiday detection, and 10 global exchange session flags with trading hour detection
    - 3-year minimum historical coverage

    Features:
    - Downloads from ticks.ex2archive.com with correct URL pattern
    - PRIMARY KEY constraints prevent duplicates during updates
    - Metadata table tracks earliest/latest dates
    - Direct SQL queries on ticks without loading into memory
    - On-demand OHLC resampling for any timeframe

    Example:
        >>> processor = ExnessDataProcessor()
        >>> # Initial 3-year download
        >>> result = processor.update_data("EURUSD", start_date="2022-01-01")
        >>> print(f"Downloaded {result['months_added']} months")
        >>> # Query ticks for date range
        >>> df_ticks = processor.query_ticks("EURUSD", start_date="2024-01-01")
        >>> # Query OHLC
        >>> df_ohlc = processor.query_ohlc("EURUSD", timeframe="1h")
    """

    def __init__(self, base_dir: Optional[Path] = None):
        """
        Initialize processor.

        Args:
            base_dir: Base directory for data storage. Defaults to ~/eon/exness-data/
        """
        if base_dir is None:
            base_dir = Path.home() / "eon" / "exness-data"

        self.base_dir = base_dir
        self.temp_dir = base_dir / "temp"

        # Create directories
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)

        # Initialize downloader module
        self.downloader = ExnessDownloader(self.temp_dir)

        # Initialize database manager module
        self.db_manager = DatabaseManager(self.base_dir)

        # Initialize gap detector module for incremental update logic
        self.gap_detector = GapDetector(self.base_dir)

        # Initialize session detector module for holiday and session detection (v1.6.0)
        self.session_detector = SessionDetector()

        # Initialize OHLC generator module with session detector dependency
        self.ohlc_generator = OHLCGenerator(self.session_detector)

        # Initialize query engine module for tick and OHLC queries
        self.query_engine = QueryEngine(self.base_dir)

    def __enter__(self):
        """
        Enter context manager.

        Enables usage with 'with' statement for automatic resource cleanup.

        Example:
            >>> with ExnessDataProcessor() as processor:
            ...     df = processor.query_ticks("EURUSD")
            ...     # Resources automatically cleaned up on exit
        """
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Exit context manager.

        Performs cleanup operations when exiting 'with' block.
        Currently handles graceful cleanup of temporary files.

        Args:
            exc_type: Exception type if an error occurred
            exc_val: Exception value if an error occurred
            exc_tb: Exception traceback if an error occurred

        Returns:
            False to propagate exceptions (standard behavior)
        """
        # Clean up any temporary files
        import shutil
        if self.temp_dir.exists():
            try:
                # Remove old temp files (keep directory structure)
                for item in self.temp_dir.glob("*.zip"):
                    try:
                        item.unlink()
                    except Exception:
                        pass  # Ignore cleanup errors
            except Exception:
                pass  # Ignore cleanup errors

        # Don't suppress exceptions
        return False

    @staticmethod
    def _validate_pair(pair: str) -> None:
        """
        Validate currency pair input.

        Args:
            pair: Currency pair to validate

        Raises:
            ValueError: If pair is not supported
        """
        valid_pairs = supported_pairs()
        if pair not in valid_pairs:
            raise ValueError(
                f"Invalid pair '{pair}'. Must be one of: {', '.join(valid_pairs)}"
            )

    @staticmethod
    def _validate_variant(variant: str) -> None:
        """
        Validate data variant input.

        Args:
            variant: Data variant to validate

        Raises:
            ValueError: If variant is not supported
        """
        valid_variants = supported_variants()
        if variant not in valid_variants:
            raise ValueError(
                f"Invalid variant '{variant}'. Must be one of: {', '.join(valid_variants)}"
            )

    @staticmethod
    def _validate_timeframe(timeframe: str) -> None:
        """
        Validate OHLC timeframe input.

        Args:
            timeframe: Timeframe to validate

        Raises:
            ValueError: If timeframe is not supported
        """
        valid_timeframes = supported_timeframes()
        if timeframe not in valid_timeframes:
            raise ValueError(
                f"Invalid timeframe '{timeframe}'. Must be one of: {', '.join(valid_timeframes)}"
            )

    @staticmethod
    def _validate_date_format(date_str: Optional[str], param_name: str) -> None:
        """
        Validate date string format.

        Args:
            date_str: Date string to validate (YYYY-MM-DD)
            param_name: Parameter name for error messages

        Raises:
            ValueError: If date format is invalid
        """
        if date_str is None:
            return

        import re
        if not re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
            raise ValueError(
                f"Invalid {param_name} '{date_str}'. Must be in YYYY-MM-DD format (e.g., '2024-01-15')"
            )

        # Validate date values
        try:
            from datetime import datetime
            datetime.strptime(date_str, '%Y-%m-%d')
        except ValueError as e:
            raise ValueError(
                f"Invalid {param_name} '{date_str}': {str(e)}"
            )

    def download_exness_zip(
        self, year: int, month: int, pair: str = "EURUSD", variant: str = "Raw_Spread"
    ) -> Optional[Path]:
        """
        Download Exness ZIP file for specific month and variant.

        Args:
            year: Year (e.g., 2024)
            month: Month (1-12)
            pair: Currency pair (default: EURUSD)
            variant: Data variant ("Raw_Spread" or "" for Standard)

        Returns:
            Path to downloaded ZIP file, or None if download failed

        Example:
            >>> processor = ExnessDataProcessor()
            >>> raw_zip = processor.download_exness_zip(2024, 9, variant="Raw_Spread")
            >>> std_zip = processor.download_exness_zip(2024, 9, variant="")
        """
        # Delegate to downloader module
        return self.downloader.download_zip(year=year, month=month, pair=pair, variant=variant)

    def _get_or_create_db(self, pair: str) -> Path:
        """
        Get DuckDB path and ensure schema exists.

        Creates tables if they don't exist:
        - raw_spread_ticks (PRIMARY KEY on Timestamp)
        - standard_ticks (PRIMARY KEY on Timestamp)
        - ohlc_1m (Phase7 30-column schema v1.6.0)
        - metadata (coverage tracking)
        """
        # Delegate to database_manager module
        return self.db_manager.get_or_create_db(pair)

    def _load_ticks_from_zip(self, zip_path: Path) -> pd.DataFrame:
        """Load ticks from ZIP file into DataFrame."""
        # Delegate to tick_loader module
        return TickLoader.load_from_zip(zip_path)

    def _append_ticks_to_db(self, duckdb_path: Path, df: pd.DataFrame, table_name: str) -> int:
        """
        Append ticks to DuckDB table.

        PRIMARY KEY constraint automatically prevents duplicates.

        Returns:
            Number of rows inserted (may be less than df length if duplicates)
        """
        # Delegate to database_manager module
        return self.db_manager.append_ticks(duckdb_path, df, table_name)

    def _discover_missing_months(self, pair: str, start_date: str) -> List[Tuple[int, int]]:
        """
        Discover which months need to be downloaded.

        Args:
            pair: Currency pair
            start_date: Earliest date to consider (YYYY-MM-DD)

        Returns:
            List of (year, month) tuples to download
        """
        # Delegate to gap_detector module
        return self.gap_detector.discover_missing_months(pair, start_date)

    def update_data(
        self,
        pair: PairType = "EURUSD",
        start_date: str = "2022-01-01",
        force_redownload: bool = False,
        delete_zip: bool = True,
    ) -> UpdateResult:
        """
        Update instrument database with latest data from Exness.

        Workflow:
        1. Ensure database and schema exist
        2. Discover missing months
        3. Download missing months (Raw_Spread + Standard)
        4. Append ticks to tables (PRIMARY KEY prevents duplicates)
        5. Regenerate OHLC for new data
        6. Update metadata

        Args:
            pair: Currency pair (e.g., "EURUSD")
            start_date: Earliest date to download (YYYY-MM-DD)
            force_redownload: Force re-download even if data exists
            delete_zip: Delete ZIP files after processing

        Returns:
            UpdateResult: Update results with:
                - duckdb_path: Path to database file
                - months_added: Number of months downloaded
                - raw_ticks_added: Number of Raw_Spread ticks added
                - standard_ticks_added: Number of Standard ticks added
                - ohlc_bars: Total OHLC bars after update
                - duckdb_size_mb: Database file size

        Raises:
            ValueError: If pair is not supported or start_date format is invalid
            FileNotFoundError: If database directory cannot be created
            ConnectionError: If Exness repository is unreachable
            pd.errors.EmptyDataError: If downloaded ZIP files are corrupted or empty

        Example:
            >>> processor = ExnessDataProcessor()
            >>> # Initial 3-year download
            >>> result = processor.update_data("EURUSD", start_date="2022-01-01")
            >>> print(f"Downloaded {result['months_added']} months")
            >>> # Incremental update (only new months)
            >>> result = processor.update_data("EURUSD")
            >>> print(f"Added {result['months_added']} new months")
        """
        # Validate inputs before any file operations
        self._validate_pair(pair)
        self._validate_date_format(start_date, "start_date")

        print(f"\n{'=' * 70}")
        print(f"Updating {pair} database")
        print(f"{'=' * 70}")

        # Step 1: Get or create database
        duckdb_path = self._get_or_create_db(pair)
        print(f"Database: {duckdb_path}")

        # Step 2: Discover missing months
        print(f"\nDiscovering missing months (from {start_date})...")
        missing_months = self._discover_missing_months(pair, start_date)
        print(f"Found {len(missing_months)} months to download")

        if not missing_months:
            print("\n✓ Database is up to date")
            return UpdateResult(
                duckdb_path=duckdb_path,
                months_added=0,
                raw_ticks_added=0,
                standard_ticks_added=0,
                ohlc_bars=0,
                duckdb_size_mb=duckdb_path.stat().st_size / 1024 / 1024,
            )

        # Step 3: Download and append ticks
        raw_ticks_total = 0
        standard_ticks_total = 0
        months_success = 0
        earliest_added_month = None  # Track earliest month for incremental OHLC

        for year, month in missing_months:
            print(f"\n--- Processing {year}-{month:02d} ---")

            # Download Raw_Spread variant
            raw_zip = self.download_exness_zip(year, month, pair, variant="Raw_Spread")
            if raw_zip is None:
                print(f"⚠️  Skipping {year}-{month:02d} (Raw_Spread not available)")
                continue

            # Download Standard variant
            std_zip = self.download_exness_zip(year, month, pair, variant="")
            if std_zip is None:
                print(f"⚠️  Skipping {year}-{month:02d} (Standard not available)")
                if delete_zip and raw_zip.exists():
                    raw_zip.unlink()
                continue

            # Load ticks
            df_raw = self._load_ticks_from_zip(raw_zip)
            df_std = self._load_ticks_from_zip(std_zip)

            # Append to database
            raw_added = self._append_ticks_to_db(duckdb_path, df_raw, "raw_spread_ticks")
            std_added = self._append_ticks_to_db(duckdb_path, df_std, "standard_ticks")

            print(f"✓ Added {raw_added:,} Raw_Spread ticks")
            print(f"✓ Added {std_added:,} Standard ticks")

            raw_ticks_total += raw_added
            standard_ticks_total += std_added
            months_success += 1

            # Track earliest added month for incremental OHLC generation
            if earliest_added_month is None:
                earliest_added_month = f"{year}-{month:02d}-01"

            # Delete ZIPs
            if delete_zip:
                raw_zip.unlink()
                std_zip.unlink()

        # Step 4: Generate OHLC for new data (incremental if possible)
        if months_success > 0:
            if earliest_added_month:
                print(f"\nGenerating OHLC for new data starting from {earliest_added_month} (Phase7 30-column schema v1.6.0)...")
                self._regenerate_ohlc(duckdb_path, start_date=earliest_added_month)
                print(f"✓ OHLC generated incrementally from {earliest_added_month}")
            else:
                print("\nRegenerating OHLC (Phase7 30-column schema v1.6.0)...")
                self._regenerate_ohlc(duckdb_path)
                print("✓ OHLC regenerated")

        # Step 5: Get final stats
        conn = duckdb.connect(str(duckdb_path), read_only=True)
        ohlc_bars = conn.execute("SELECT COUNT(*) FROM ohlc_1m").fetchone()[0]
        conn.close()

        duckdb_size_mb = duckdb_path.stat().st_size / 1024 / 1024

        print(f"\n{'=' * 70}")
        print("Update Summary")
        print(f"{'=' * 70}")
        print(f"Months added:     {months_success}")
        print(f"Raw_Spread ticks: {raw_ticks_total:,}")
        print(f"Standard ticks:   {standard_ticks_total:,}")
        print(f"OHLC bars:        {ohlc_bars:,}")
        print(f"Database size:    {duckdb_size_mb:.2f} MB")

        return UpdateResult(
            duckdb_path=duckdb_path,
            months_added=months_success,
            raw_ticks_added=raw_ticks_total,
            standard_ticks_added=standard_ticks_total,
            ohlc_bars=ohlc_bars,
            duckdb_size_mb=duckdb_size_mb,
        )

    def _regenerate_ohlc(self, duckdb_path: Path) -> None:
        """
        Regenerate OHLC table with Phase7 schema (v1.6.0: 30 columns).

        Uses LEFT JOIN to combine Raw_Spread and Standard variants.
        Includes normalized spread metrics (v1.2.0+), timezone/session tracking (v1.3.0+),
        holiday detection (v1.4.0+), and 10 global exchange session flags with trading hour detection (v1.6.0+).
        """
        # Delegate to ohlc_generator module
        self.ohlc_generator.regenerate_ohlc(duckdb_path)

    def query_ticks(
        self,
        pair: PairType = "EURUSD",
        variant: VariantType = "raw_spread",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        filter_sql: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Query tick data with optional date range filtering.

        Args:
            pair: Currency pair
            variant: "raw_spread" or "standard"
            start_date: Start date (YYYY-MM-DD), inclusive
            end_date: End date (YYYY-MM-DD), inclusive
            filter_sql: Additional SQL WHERE clause

        Returns:
            DataFrame with tick data (columns: Timestamp, Bid, Ask)

        Raises:
            ValueError: If pair/variant is invalid or date format is wrong
            FileNotFoundError: If database file doesn't exist
            duckdb.Error: If SQL query fails (e.g., invalid filter_sql)
            pd.errors.EmptyDataError: If date range contains no data

        Example:
            >>> processor = ExnessDataProcessor()
            >>> # Query all Raw_Spread ticks for 2024
            >>> df = processor.query_ticks("EURUSD", start_date="2024-01-01", end_date="2024-12-31")
            >>> # Query Standard ticks with custom filter
            >>> df = processor.query_ticks("EURUSD", variant="standard", filter_sql="Bid > 1.10")
        """
        # Validate inputs before any file operations
        self._validate_pair(pair)
        self._validate_variant(variant)
        self._validate_date_format(start_date, "start_date")
        self._validate_date_format(end_date, "end_date")

        # Delegate to query_engine module
        return self.query_engine.query_ticks(pair, variant, start_date, end_date, filter_sql)

    def query_ohlc(
        self,
        pair: PairType = "EURUSD",
        timeframe: TimeframeType = "1m",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Query OHLC data with optional date range filtering and resampling.

        Args:
            pair: Currency pair
            timeframe: Timeframe (1m, 5m, 15m, 1h, 4h, 1d)
            start_date: Start date (YYYY-MM-DD), inclusive
            end_date: End date (YYYY-MM-DD), inclusive

        Returns:
            DataFrame with OHLC data (Phase7 30-column schema v1.6.0)

        Raises:
            ValueError: If pair/timeframe is invalid or date format is wrong
            FileNotFoundError: If database file doesn't exist
            duckdb.Error: If SQL query fails or OHLC table is missing
            pd.errors.EmptyDataError: If date range contains no data

        Example:
            >>> processor = ExnessDataProcessor()
            >>> # Query 1m OHLC for January 2024
            >>> df = processor.query_ohlc("EURUSD", timeframe="1m", start_date="2024-01-01", end_date="2024-01-31")
            >>> # Query 1h OHLC (on-demand resampling)
            >>> df = processor.query_ohlc("EURUSD", timeframe="1h", start_date="2024-01-01")
        """
        # Validate inputs before any file operations
        self._validate_pair(pair)
        self._validate_timeframe(timeframe)
        self._validate_date_format(start_date, "start_date")
        self._validate_date_format(end_date, "end_date")

        # Delegate to query_engine module
        return self.query_engine.query_ohlc(pair, timeframe, start_date, end_date)

    def get_data_coverage(self, pair: PairType = "EURUSD") -> CoverageInfo:
        """
        Get data coverage information for an instrument.

        Args:
            pair: Currency pair

        Returns:
            CoverageInfo: Coverage information with:
                - database_exists: Whether database file exists
                - duckdb_path: Path to database file
                - duckdb_size_mb: Database file size
                - raw_spread_ticks: Number of Raw_Spread ticks
                - standard_ticks: Number of Standard ticks
                - ohlc_bars: Number of 1m OHLC bars
                - earliest_date: Earliest tick timestamp
                - latest_date: Latest tick timestamp
                - date_range_days: Number of days covered

        Raises:
            ValueError: If pair is not supported
            duckdb.Error: If database connection fails (rare)

        Example:
            >>> processor = ExnessDataProcessor()
            >>> coverage = processor.get_data_coverage("EURUSD")
            >>> print(f"Coverage: {coverage['earliest_date']} to {coverage['latest_date']}")
            >>> print(f"Total: {coverage['raw_spread_ticks']:,} ticks")
        """
        # Validate inputs before any file operations
        self._validate_pair(pair)

        # Delegate to query_engine module
        return self.query_engine.get_data_coverage(pair)

    def get_available_dates(self, pair: PairType = "EURUSD") -> tuple[Optional[str], Optional[str]]:
        """
        Get earliest and latest dates with actual data.

        Unlike get_data_coverage(), this provides a quick way to check the
        actual date boundaries without fetching full coverage statistics.

        Args:
            pair: Currency pair

        Returns:
            Tuple of (earliest_date, latest_date) as ISO 8601 strings.
            Returns (None, None) if database doesn't exist or has no data.

        Raises:
            ValueError: If pair is not supported

        Example:
            >>> processor = ExnessDataProcessor()
            >>> earliest, latest = processor.get_available_dates("EURUSD")
            >>> if earliest:
            ...     print(f"Data available from {earliest} to {latest}")
        """
        self._validate_pair(pair)
        coverage = self.query_engine.get_data_coverage(pair)
        return (coverage.earliest_date, coverage.latest_date)

    def validate_date_range(
        self,
        start_date: str,
        end_date: str
    ) -> tuple[bool, Optional[str]]:
        """
        Validate date range before querying.

        Pre-flight check to validate date formats and logical ordering without
        performing database operations. Helps AI agents avoid failed queries.

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            Tuple of (is_valid, error_message).
            Returns (True, None) if valid, (False, error_message) if invalid.

        Example:
            >>> processor = ExnessDataProcessor()
            >>> is_valid, error = processor.validate_date_range("2024-01-01", "2024-12-31")
            >>> if not is_valid:
            ...     print(f"Invalid date range: {error}")
        """
        # Validate formats
        try:
            self._validate_date_format(start_date, "start_date")
            self._validate_date_format(end_date, "end_date")
        except ValueError as e:
            return (False, str(e))

        # Validate logical ordering
        from datetime import datetime
        try:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            end_dt = datetime.strptime(end_date, '%Y-%m-%d')

            if start_dt > end_dt:
                return (False, f"start_date '{start_date}' is after end_date '{end_date}'")

        except ValueError as e:
            return (False, str(e))

        return (True, None)

    def estimate_download_size(
        self,
        pair: PairType,
        start_date: str,
        end_date: str
    ) -> float:
        """
        Estimate download size in MB for date range.

        Provides rough estimate based on typical data density (approximately
        1.5M ticks per month = ~11 MB per month for dual-variant storage).

        Args:
            pair: Currency pair
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            Estimated download size in megabytes

        Raises:
            ValueError: If pair is invalid or date format is wrong

        Example:
            >>> processor = ExnessDataProcessor()
            >>> size_mb = processor.estimate_download_size("EURUSD", "2024-01-01", "2024-12-31")
            >>> print(f"Estimated download: {size_mb:.1f} MB")
        """
        self._validate_pair(pair)
        self._validate_date_format(start_date, "start_date")
        self._validate_date_format(end_date, "end_date")

        from datetime import datetime
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(end_date, '%Y-%m-%d')

        # Calculate months
        months = (end_dt.year - start_dt.year) * 12 + (end_dt.month - start_dt.month) + 1

        # Estimate: ~11 MB per month (dual-variant storage)
        estimated_mb = months * 11.0

        return estimated_mb
