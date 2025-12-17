"""
Core processor for Exness forex tick data with ClickHouse backend.

ADR: 2025-12-11-duckdb-removal-clickhouse

Architecture (v2.0.0 - ClickHouse-Only):
1. Single ClickHouse database (exness) with instrument column
2. Three tables: raw_spread_ticks, standard_ticks, ohlc_1m
3. Dual-variant downloads (Raw_Spread + Standard) for Phase7 compliance
4. Incremental updates with automatic gap detection
5. ReplacingMergeTree for deduplication

Phase7 Schema (v1.6.0 - 26 columns):
- Timestamp, Open, High, Low, Close (BID-based from Raw_Spread)
- raw_spread_avg, standard_spread_avg (dual spread tracking)
- tick_count_raw_spread, tick_count_standard (dual tick counts)
- ny_hour, london_hour, ny_session, london_session (timezone/session tracking)
- is_us_holiday, is_uk_holiday, is_major_holiday (official holidays only)
- is_{exchange}_session for 10 exchanges with trading hour detection

BREAKING CHANGES (v2.0.0):
- Backend: ClickHouse is now the only supported backend
- Renamed: duckdb_path -> database (str, ClickHouse database name)
- Renamed: duckdb_size_mb -> storage_bytes (int, from system.tables)
- Removed: All DuckDB file path references
"""

from pathlib import Path
from typing import Optional

import pandas as pd

from exness_data_preprocess.clickhouse_client import get_client
from exness_data_preprocess.clickhouse_gap_detector import ClickHouseGapDetector
from exness_data_preprocess.clickhouse_manager import ClickHouseManager
from exness_data_preprocess.clickhouse_ohlc_generator import ClickHouseOHLCGenerator
from exness_data_preprocess.clickhouse_query_engine import ClickHouseQueryEngine
from exness_data_preprocess.config import ConfigModel
from exness_data_preprocess.downloader import ExnessDownloader
from exness_data_preprocess.models import (
    CoverageInfo,
    DryRunResult,
    PairType,
    TimeframeType,
    UpdateResult,
    VariantType,
    supported_pairs,
    supported_timeframes,
    supported_variants,
)
from exness_data_preprocess.session_detector import SessionDetector
from exness_data_preprocess.tick_loader import TickLoader


class ExnessDataProcessor:
    """
    Process Exness forex tick data with ClickHouse backend.

    ADR: 2025-12-11-duckdb-removal-clickhouse

    Architecture (v2.0.0 - ClickHouse-Only):
    - Single ClickHouse database (exness) with instrument column
    - Dual-variant storage (Raw_Spread + Standard) for Phase7
    - Incremental updates with automatic gap detection
    - 26-column OHLC schema with dual spreads, tick counts, timezone/session tracking,
      holiday detection, and 10 global exchange session flags

    Features:
    - Downloads from ticks.ex2archive.com with correct URL pattern
    - ReplacingMergeTree provides deduplication at merge time
    - Direct SQL queries on ticks without loading into memory
    - On-demand OHLC resampling for any timeframe (<15ms)

    Example:
        >>> processor = ExnessDataProcessor()
        >>> # Initial 3-year download
        >>> result = processor.update_data("EURUSD", start_date="2022-01-01")
        >>> print(f"Downloaded {result.months_added} months")
        >>> # Query ticks for date range
        >>> df_ticks = processor.query_ticks("EURUSD", start_date="2024-01-01")
        >>> # Query OHLC
        >>> df_ohlc = processor.query_ohlc("EURUSD", timeframe="1h")
    """

    # ClickHouse database name
    DATABASE = "exness"

    def __init__(self, config: Optional[ConfigModel] = None):
        """
        Initialize processor with ClickHouse backend.

        Args:
            config: Optional user configuration

        Note:
            ClickHouse connection configured via environment variables:
            - CLICKHOUSE_MODE: "local" or "cloud"
            - CLICKHOUSE_HOST: hostname (default: localhost)
            - CLICKHOUSE_PORT: port (default: 8123 local, 8443 cloud)
            - CLICKHOUSE_USER: username (default: default)
            - CLICKHOUSE_PASSWORD: password (default: empty)
        """
        self.config = config

        # Temp dir for downloads only
        self.temp_dir = Path.home() / "eon" / "exness-data" / "temp"
        self.temp_dir.mkdir(parents=True, exist_ok=True)

        # Initialize ClickHouse client (shared across modules)
        self._ch_client = get_client()

        # Initialize ClickHouse modules
        self.ch_manager = ClickHouseManager(self._ch_client)
        self.ch_gap_detector = ClickHouseGapDetector(self._ch_client)
        self.session_detector = SessionDetector()
        self.ch_ohlc_generator = ClickHouseOHLCGenerator(self.session_detector, self._ch_client)
        self.ch_query_engine = ClickHouseQueryEngine(self._ch_client)

        # Ensure schema exists
        self.ch_manager.ensure_schema()

        # Initialize downloader module
        self.downloader = ExnessDownloader(self.temp_dir)

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
        Closes ClickHouse connection and cleans up temporary files.

        Args:
            exc_type: Exception type if an error occurred
            exc_val: Exception value if an error occurred
            exc_tb: Exception traceback if an error occurred

        Returns:
            False to propagate exceptions (standard behavior)
        """
        # Close ClickHouse connection
        if hasattr(self, "_ch_client") and self._ch_client:
            try:
                self._ch_client.close()
            except Exception:
                pass

        # Clean up temporary files
        if self.temp_dir.exists():
            try:
                for item in self.temp_dir.glob("*.zip"):
                    try:
                        item.unlink()
                    except Exception:
                        pass
            except Exception:
                pass

        return False

    def close(self):
        """
        Explicitly close ClickHouse connection.

        Call this when not using context manager.
        """
        if hasattr(self, "_ch_client") and self._ch_client:
            try:
                self._ch_client.close()
            except Exception:
                pass

    @staticmethod
    def _validate_pair(pair: str) -> None:
        """Validate currency pair input."""
        valid_pairs = supported_pairs()
        if pair not in valid_pairs:
            raise ValueError(f"Invalid pair '{pair}'. Must be one of: {', '.join(valid_pairs)}")

    @staticmethod
    def _validate_variant(variant: str) -> None:
        """Validate data variant input."""
        valid_variants = supported_variants()
        if variant not in valid_variants:
            raise ValueError(
                f"Invalid variant '{variant}'. Must be one of: {', '.join(valid_variants)}"
            )

    @staticmethod
    def _validate_timeframe(timeframe: str) -> None:
        """Validate OHLC timeframe input."""
        valid_timeframes = supported_timeframes()
        if timeframe not in valid_timeframes:
            raise ValueError(
                f"Invalid timeframe '{timeframe}'. Must be one of: {', '.join(valid_timeframes)}"
            )

    @staticmethod
    def _validate_date_format(date_str: Optional[str], param_name: str) -> None:
        """Validate date string format."""
        if date_str is None:
            return

        import re

        if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
            raise ValueError(f"Invalid {param_name} '{date_str}'. Must be in YYYY-MM-DD format")

        try:
            from datetime import datetime

            datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError as e:
            raise ValueError(f"Invalid {param_name} '{date_str}': {e!s}") from e

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
        """
        return self.downloader.download_zip(year=year, month=month, pair=pair, variant=variant)

    def _load_ticks_from_zip(self, zip_path: Path) -> pd.DataFrame:
        """Load ticks from ZIP file into DataFrame."""
        return TickLoader.load_from_zip(zip_path)

    def update_data(
        self,
        pair: PairType = "EURUSD",
        start_date: str = "2022-01-01",
        force_redownload: bool = False,
        delete_zip: bool = True,
        dry_run: bool = False,
    ) -> UpdateResult | DryRunResult:
        """
        Update instrument database with latest data from Exness.

        Workflow:
        1. Ensure ClickHouse schema exists
        2. Discover missing months via gap detection
        3. Download missing months (Raw_Spread + Standard)
        4. Insert ticks to ClickHouse (ReplacingMergeTree handles deduplication)
        5. Regenerate OHLC for new data
        6. Return update statistics

        Args:
            pair: Currency pair (e.g., "EURUSD")
            start_date: Earliest date to download (YYYY-MM-DD)
            force_redownload: Force re-download even if data exists
            delete_zip: Delete ZIP files after processing
            dry_run: Preview operation without downloading

        Returns:
            UpdateResult: Update results with database metrics (if dry_run=False)
            DryRunResult: Estimated operation plan (if dry_run=True)

        Raises:
            ValueError: If pair is not supported or start_date format is invalid
            ClickHouseConnectionError: If ClickHouse is not reachable
            ClickHouseQueryError: If database operations fail

        Example:
            >>> processor = ExnessDataProcessor()
            >>> result = processor.update_data("EURUSD", start_date="2022-01-01")
            >>> print(f"Downloaded {result.months_added} months")
        """
        self._validate_pair(pair)
        self._validate_date_format(start_date, "start_date")

        print(f"\n{'=' * 70}")
        print(f"Updating {pair} in ClickHouse ({self.DATABASE})")
        print(f"{'=' * 70}")

        # Discover missing months
        print(f"\nDiscovering missing months (from {start_date})...")
        missing_months = self.ch_gap_detector.discover_missing_months(pair, start_date)
        print(f"Found {len(missing_months)} months to download")

        if not missing_months:
            print("\n✓ Database is up to date")
            if dry_run:
                return DryRunResult(
                    would_download_months=0,
                    estimated_raw_ticks=0,
                    estimated_standard_ticks=0,
                    estimated_size_mb=0.0,
                    gap_months=[],
                )
            return UpdateResult(
                database=self.DATABASE,
                months_added=0,
                raw_ticks_added=0,
                standard_ticks_added=0,
                ohlc_bars=self.ch_manager.get_tick_count(pair) // 1000,  # Approximate
                storage_bytes=0,
            )

        # Dry-run mode
        if dry_run:
            num_months = len(missing_months)
            ticks_per_month = 9_500_000
            mb_per_month = 11.0

            gap_month_strings = [f"{year}-{month:02d}" for year, month in missing_months]

            print(f"\n{'=' * 70}")
            print("Dry-Run Summary")
            print(f"{'=' * 70}")
            print(f"Would download:    {num_months} months")
            print(f"Estimated ticks:   {num_months * ticks_per_month * 2:,} total")
            print(f"{'=' * 70}\n")

            return DryRunResult(
                would_download_months=num_months,
                estimated_raw_ticks=num_months * ticks_per_month,
                estimated_standard_ticks=num_months * ticks_per_month,
                estimated_size_mb=num_months * mb_per_month,
                gap_months=gap_month_strings,
            )

        # Download and insert ticks
        raw_ticks_total = 0
        standard_ticks_total = 0
        months_success = 0
        earliest_added_month = None

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

            # Insert to ClickHouse
            raw_added = self.ch_manager.insert_ticks(df_raw, pair, "raw_spread")
            std_added = self.ch_manager.insert_ticks(df_std, pair, "standard")

            print(f"✓ Added {raw_added:,} Raw_Spread ticks")
            print(f"✓ Added {std_added:,} Standard ticks")

            raw_ticks_total += raw_added
            standard_ticks_total += std_added
            months_success += 1

            if earliest_added_month is None:
                earliest_added_month = f"{year}-{month:02d}-01"

            # Delete ZIPs
            if delete_zip:
                raw_zip.unlink()
                std_zip.unlink()

        # Generate OHLC for new data
        ohlc_bars = 0
        if months_success > 0:
            if earliest_added_month:
                print(f"\nGenerating OHLC for new data starting from {earliest_added_month}...")
                ohlc_bars = self.ch_ohlc_generator.regenerate_ohlc(
                    pair, start_date=earliest_added_month
                )
                print(f"✓ OHLC generated: {ohlc_bars:,} bars")
            else:
                print("\nRegenerating OHLC...")
                ohlc_bars = self.ch_ohlc_generator.regenerate_ohlc(pair)
                print(f"✓ OHLC regenerated: {ohlc_bars:,} bars")

        print(f"\n{'=' * 70}")
        print("Update Summary")
        print(f"{'=' * 70}")
        print(f"Months added:     {months_success}")
        print(f"Raw_Spread ticks: {raw_ticks_total:,}")
        print(f"Standard ticks:   {standard_ticks_total:,}")
        print(f"OHLC bars:        {ohlc_bars:,}")

        return UpdateResult(
            database=self.DATABASE,
            months_added=months_success,
            raw_ticks_added=raw_ticks_total,
            standard_ticks_added=standard_ticks_total,
            ohlc_bars=ohlc_bars,
            storage_bytes=0,  # TODO: Query system.tables for size
        )

    def query_ticks(
        self,
        pair: PairType = "EURUSD",
        variant: VariantType = "raw_spread",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> pd.DataFrame:
        """
        Query tick data with optional date range filtering.

        Args:
            pair: Currency pair
            variant: "raw_spread" or "standard"
            start_date: Start date (YYYY-MM-DD), inclusive
            end_date: End date (YYYY-MM-DD), inclusive
            limit: Maximum rows to return

        Returns:
            DataFrame with tick data (columns: timestamp, bid, ask)

        Example:
            >>> processor = ExnessDataProcessor()
            >>> df = processor.query_ticks("EURUSD", start_date="2024-01-01")
        """
        self._validate_pair(pair)
        self._validate_variant(variant)
        self._validate_date_format(start_date, "start_date")
        self._validate_date_format(end_date, "end_date")

        return self.ch_query_engine.query_ticks(
            instrument=pair,
            variant=variant,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
        )

    def query_ohlc(
        self,
        pair: PairType = "EURUSD",
        timeframe: TimeframeType = "1m",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> pd.DataFrame:
        """
        Query OHLC data with optional date range filtering and resampling.

        Args:
            pair: Currency pair
            timeframe: Timeframe (1m, 5m, 15m, 30m, 1h, 4h, 1d)
            start_date: Start date (YYYY-MM-DD), inclusive
            end_date: End date (YYYY-MM-DD), inclusive
            limit: Maximum rows to return

        Returns:
            DataFrame with OHLC data (26-column Phase7 schema)

        Example:
            >>> processor = ExnessDataProcessor()
            >>> df = processor.query_ohlc("EURUSD", timeframe="1h", start_date="2024-01-01")
        """
        self._validate_pair(pair)
        self._validate_timeframe(timeframe)
        self._validate_date_format(start_date, "start_date")
        self._validate_date_format(end_date, "end_date")

        return self.ch_query_engine.query_ohlc(
            instrument=pair,
            timeframe=timeframe,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
        )

    def get_data_coverage(self, pair: PairType = "EURUSD") -> CoverageInfo:
        """
        Get data coverage information for an instrument.

        Args:
            pair: Currency pair

        Returns:
            CoverageInfo with coverage statistics

        Example:
            >>> processor = ExnessDataProcessor()
            >>> coverage = processor.get_data_coverage("EURUSD")
            >>> print(f"Coverage: {coverage.earliest_date} to {coverage.latest_date}")
        """
        self._validate_pair(pair)
        return self.ch_query_engine.get_data_coverage(pair)

    def get_available_dates(self, pair: PairType = "EURUSD") -> tuple[Optional[str], Optional[str]]:
        """
        Get earliest and latest dates with actual data.

        Args:
            pair: Currency pair

        Returns:
            Tuple of (earliest_date, latest_date) as ISO 8601 strings.
            Returns (None, None) if no data exists.
        """
        self._validate_pair(pair)
        coverage = self.ch_query_engine.get_data_coverage(pair)
        return (coverage.earliest_date, coverage.latest_date)

    def validate_date_range(self, start_date: str, end_date: str) -> tuple[bool, Optional[str]]:
        """
        Validate date range before querying.

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            Tuple of (is_valid, error_message).
        """
        try:
            self._validate_date_format(start_date, "start_date")
            self._validate_date_format(end_date, "end_date")
        except ValueError as e:
            return (False, str(e))

        from datetime import datetime

        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")

            if start_dt > end_dt:
                return (False, f"start_date '{start_date}' is after end_date '{end_date}'")

        except ValueError as e:
            return (False, str(e))

        return (True, None)

    def estimate_download_size(self, pair: PairType, start_date: str, end_date: str) -> float:
        """
        Estimate download size in MB for date range.

        Args:
            pair: Currency pair
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            Estimated download size in megabytes
        """
        self._validate_pair(pair)
        self._validate_date_format(start_date, "start_date")
        self._validate_date_format(end_date, "end_date")

        from datetime import datetime

        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")

        months = (end_dt.year - start_dt.year) * 12 + (end_dt.month - start_dt.month) + 1
        return months * 11.0
