"""
Core processor for Exness forex tick data.

Architecture (v2.0.0 - Unified Single-File Multi-Year):
1. One DuckDB file per instrument (e.g., eurusd.duckdb)
2. Three tables: raw_spread_ticks, standard_ticks, ohlc_1m
3. Dual-variant downloads (Raw_Spread + Standard) for Phase7 compliance
4. Incremental updates with automatic gap detection
5. Metadata table for coverage tracking

Phase7 Schema (v1.2.0 - 13 columns):
- Timestamp, Open, High, Low, Close (BID-based from Raw_Spread)
- raw_spread_avg, standard_spread_avg (dual spread tracking)
- tick_count_raw_spread, tick_count_standard (dual tick counts)
- range_per_spread, range_per_tick, body_per_spread, body_per_tick (normalized metrics)

Storage: ~135 MB/year, ~405 MB for 3 years per instrument
"""

import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.error import URLError
from urllib.request import urlretrieve

import duckdb
import pandas as pd

from exness_data_preprocess.models import (
    CoverageInfo,
    PairType,
    TimeframeType,
    UpdateResult,
    VariantType,
)
from exness_data_preprocess.schema import OHLCSchema


class ExnessDataProcessor:
    """
    Process Exness forex tick data with unified multi-year architecture.

    Architecture (v2.0.0):
    - One DuckDB file per instrument (eurusd.duckdb not monthly files)
    - Dual-variant storage (Raw_Spread + Standard) for Phase7
    - Incremental updates with automatic gap detection
    - 13-column OHLC schema (v1.2.0) with dual spreads, tick counts, and normalized metrics
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

    def __init__(self, base_dir: Path = None):
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
        # Construct symbol name
        symbol = f"{pair}_{variant}" if variant else pair

        # Correct URL pattern: /ticks/{symbol}/{year}/{month}/
        url = f"https://ticks.ex2archive.com/ticks/{symbol}/{year}/{month:02d}/Exness_{symbol}_{year}_{month:02d}.zip"
        zip_path = self.temp_dir / f"Exness_{symbol}_{year}_{month:02d}.zip"

        if zip_path.exists():
            return zip_path

        try:
            print(f"Downloading: {url}")
            urlretrieve(url, zip_path)
            size_mb = zip_path.stat().st_size / 1024 / 1024
            print(f"✓ Downloaded: {size_mb:.2f} MB")
            return zip_path
        except URLError as e:
            print(f"✗ Download failed: {e}")
            return None

    def _get_or_create_db(self, pair: str) -> Path:
        """
        Get DuckDB path and ensure schema exists.

        Creates tables if they don't exist:
        - raw_spread_ticks (PRIMARY KEY on Timestamp)
        - standard_ticks (PRIMARY KEY on Timestamp)
        - ohlc_1m (Phase7 13-column schema v1.2.0)
        - metadata (coverage tracking)
        """
        duckdb_path = self.base_dir / f"{pair.lower()}.duckdb"
        conn = duckdb.connect(str(duckdb_path))

        # Create raw_spread_ticks table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS raw_spread_ticks (
                Timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
                Bid DOUBLE NOT NULL,
                Ask DOUBLE NOT NULL,
                PRIMARY KEY (Timestamp)
            )
        """)

        # Add table and column comments for raw_spread_ticks
        conn.execute("""
            COMMENT ON TABLE raw_spread_ticks IS
            'Exness Raw_Spread variant (execution prices, ~98% zero-spreads).
             Data source: https://ticks.ex2archive.com/ticks/{SYMBOL}_Raw_Spread/{YEAR}/{MONTH}/'
        """)
        conn.execute(
            "COMMENT ON COLUMN raw_spread_ticks.Timestamp IS 'Microsecond-precision tick timestamp (UTC)'"
        )
        conn.execute("COMMENT ON COLUMN raw_spread_ticks.Bid IS 'Bid price (execution price)'")
        conn.execute("COMMENT ON COLUMN raw_spread_ticks.Ask IS 'Ask price (execution price)'")

        # Create standard_ticks table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS standard_ticks (
                Timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
                Bid DOUBLE NOT NULL,
                Ask DOUBLE NOT NULL,
                PRIMARY KEY (Timestamp)
            )
        """)

        # Add table and column comments for standard_ticks
        conn.execute("""
            COMMENT ON TABLE standard_ticks IS
            'Exness Standard variant (traditional quotes, 0% zero-spreads, always Bid < Ask).
             Data source: https://ticks.ex2archive.com/ticks/{SYMBOL}/{YEAR}/{MONTH}/'
        """)
        conn.execute(
            "COMMENT ON COLUMN standard_ticks.Timestamp IS 'Microsecond-precision tick timestamp (UTC)'"
        )
        conn.execute("COMMENT ON COLUMN standard_ticks.Bid IS 'Bid price (always < Ask)'")
        conn.execute("COMMENT ON COLUMN standard_ticks.Ask IS 'Ask price (always > Bid)'")

        # Create metadata table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS metadata (
                key VARCHAR PRIMARY KEY,
                value VARCHAR NOT NULL,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
        """)

        # Add table and column comments for metadata
        conn.execute("""
            COMMENT ON TABLE metadata IS
            'Database coverage tracking and statistics (earliest/latest dates, tick counts, etc.)'
        """)
        conn.execute(
            "COMMENT ON COLUMN metadata.key IS 'Metadata key identifier (e.g., earliest_date, latest_date)'"
        )
        conn.execute("COMMENT ON COLUMN metadata.value IS 'Metadata value (string representation)'")
        conn.execute("COMMENT ON COLUMN metadata.updated_at IS 'Last update timestamp'")

        # Create ohlc_1m table using schema definition (includes 13 columns in v1.2.0)
        conn.execute(OHLCSchema.get_create_table_sql())

        # Add table and column comments
        conn.execute(OHLCSchema.get_table_comment_sql())
        for comment_sql in OHLCSchema.get_column_comment_sqls():
            conn.execute(comment_sql)

        conn.close()
        return duckdb_path

    def _load_ticks_from_zip(self, zip_path: Path) -> pd.DataFrame:
        """Load ticks from ZIP file into DataFrame."""
        with zipfile.ZipFile(zip_path, "r") as zf:
            csv_name = zip_path.stem + ".csv"
            with zf.open(csv_name) as csv_file:
                df = pd.read_csv(
                    csv_file, usecols=["Timestamp", "Bid", "Ask"], parse_dates=["Timestamp"]
                )

        # Convert to UTC timezone-aware
        df["Timestamp"] = pd.to_datetime(df["Timestamp"], utc=True)
        return df

    def _append_ticks_to_db(self, duckdb_path: Path, df: pd.DataFrame, table_name: str) -> int:
        """
        Append ticks to DuckDB table.

        PRIMARY KEY constraint automatically prevents duplicates.

        Returns:
            Number of rows inserted (may be less than df length if duplicates)
        """
        conn = duckdb.connect(str(duckdb_path))

        try:
            # Get count before insert
            count_before = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]

            # Use INSERT OR IGNORE to skip duplicates
            conn.register("df_temp", df)
            conn.execute(f"""
                INSERT OR IGNORE INTO {table_name}
                SELECT * FROM df_temp
            """)

            # Get count after insert
            count_after = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
            rows_inserted = count_after - count_before
        finally:
            conn.close()

        return rows_inserted

    def _discover_missing_months(self, pair: str, start_date: str) -> List[Tuple[int, int]]:
        """
        Discover which months need to be downloaded.

        Args:
            pair: Currency pair
            start_date: Earliest date to consider (YYYY-MM-DD)

        Returns:
            List of (year, month) tuples to download
        """
        duckdb_path = self.base_dir / f"{pair.lower()}.duckdb"

        if not duckdb_path.exists():
            # No database yet - need full historical download
            # From start_date to current month
            from datetime import datetime

            start = datetime.strptime(start_date, "%Y-%m-%d")
            today = datetime.now()

            months = []
            current = start
            while current <= today:
                months.append((current.year, current.month))
                # Next month
                if current.month == 12:
                    current = current.replace(year=current.year + 1, month=1)
                else:
                    current = current.replace(month=current.month + 1)

            return months

        # Query existing coverage
        conn = duckdb.connect(str(duckdb_path), read_only=True)
        try:
            result = conn.execute("""
                SELECT
                    DATE_TRUNC('month', MIN(Timestamp)) as earliest,
                    DATE_TRUNC('month', MAX(Timestamp)) as latest
                FROM raw_spread_ticks
            """).fetchone()

            if result and result[0]:
                # Find gaps in coverage
                # For now, simple approach: fill from earliest to current
                # TODO: Implement gap detection within range
                earliest = pd.to_datetime(result[0])
                latest = pd.to_datetime(result[1])

                # Need months before earliest or after latest
                from datetime import datetime

                start = datetime.strptime(start_date, "%Y-%m-%d")
                today = datetime.now()

                months = []

                # Before earliest
                current = start
                while current.year * 100 + current.month < earliest.year * 100 + earliest.month:
                    months.append((current.year, current.month))
                    if current.month == 12:
                        current = current.replace(year=current.year + 1, month=1)
                    else:
                        current = current.replace(month=current.month + 1)

                # After latest
                current = latest
                if current.month == 12:
                    current = current.replace(year=current.year + 1, month=1)
                else:
                    current = current.replace(month=current.month + 1)

                while current.year * 100 + current.month <= today.year * 100 + today.month:
                    months.append((current.year, current.month))
                    if current.month == 12:
                        current = current.replace(year=current.year + 1, month=1)
                    else:
                        current = current.replace(month=current.month + 1)

                return months
            else:
                # Empty database
                from datetime import datetime

                start = datetime.strptime(start_date, "%Y-%m-%d")
                today = datetime.now()

                months = []
                current = start
                while current <= today:
                    months.append((current.year, current.month))
                    if current.month == 12:
                        current = current.replace(year=current.year + 1, month=1)
                    else:
                        current = current.replace(month=current.month + 1)

                return months
        finally:
            conn.close()

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
            Dictionary with update results:
                - duckdb_path: Path to database file
                - months_added: Number of months downloaded
                - raw_ticks_added: Number of Raw_Spread ticks added
                - standard_ticks_added: Number of Standard ticks added
                - ohlc_bars: Total OHLC bars after update
                - duckdb_size_mb: Database file size

        Example:
            >>> processor = ExnessDataProcessor()
            >>> # Initial 3-year download
            >>> result = processor.update_data("EURUSD", start_date="2022-01-01")
            >>> print(f"Downloaded {result['months_added']} months")
            >>> # Incremental update (only new months)
            >>> result = processor.update_data("EURUSD")
            >>> print(f"Added {result['months_added']} new months")
        """
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

            # Delete ZIPs
            if delete_zip:
                raw_zip.unlink()
                std_zip.unlink()

        # Step 4: Regenerate OHLC for all new data
        if months_success > 0:
            print("\nRegenerating OHLC (Phase7 13-column schema v1.2.0)...")
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
        Regenerate OHLC table with Phase7 schema (v1.2.0: 13 columns).

        Uses LEFT JOIN to combine Raw_Spread and Standard variants.
        Includes normalized spread metrics (v1.2.0+).
        """
        conn = duckdb.connect(str(duckdb_path))

        # Delete existing OHLC data
        conn.execute("DELETE FROM ohlc_1m")

        # Generate Phase7 OHLC with normalized metrics (NULL-safe calculations)
        conn.execute("""
            INSERT INTO ohlc_1m
            SELECT
                DATE_TRUNC('minute', r.Timestamp) as Timestamp,
                FIRST(r.Bid ORDER BY r.Timestamp) as Open,
                MAX(r.Bid) as High,
                MIN(r.Bid) as Low,
                LAST(r.Bid ORDER BY r.Timestamp) as Close,
                AVG(r.Ask - r.Bid) as raw_spread_avg,
                AVG(s.Ask - s.Bid) as standard_spread_avg,
                COUNT(r.Timestamp) as tick_count_raw_spread,
                COUNT(s.Timestamp) as tick_count_standard,
                -- Normalized spread metrics (v1.2.0) - NULL-safe calculations
                CASE
                    WHEN AVG(s.Ask - s.Bid) > 0
                    THEN (MAX(r.Bid) - MIN(r.Bid)) / AVG(s.Ask - s.Bid)
                    ELSE NULL
                END as range_per_spread,
                CASE
                    WHEN COUNT(s.Timestamp) > 0
                    THEN (MAX(r.Bid) - MIN(r.Bid)) / COUNT(s.Timestamp)
                    ELSE NULL
                END as range_per_tick,
                CASE
                    WHEN AVG(s.Ask - s.Bid) > 0
                    THEN ABS(LAST(r.Bid ORDER BY r.Timestamp) - FIRST(r.Bid ORDER BY r.Timestamp)) / AVG(s.Ask - s.Bid)
                    ELSE NULL
                END as body_per_spread,
                CASE
                    WHEN COUNT(s.Timestamp) > 0
                    THEN ABS(LAST(r.Bid ORDER BY r.Timestamp) - FIRST(r.Bid ORDER BY r.Timestamp)) / COUNT(s.Timestamp)
                    ELSE NULL
                END as body_per_tick
            FROM raw_spread_ticks r
            LEFT JOIN standard_ticks s
                ON DATE_TRUNC('minute', r.Timestamp) = DATE_TRUNC('minute', s.Timestamp)
            GROUP BY DATE_TRUNC('minute', r.Timestamp)
            ORDER BY Timestamp
        """)

        conn.close()

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
            DataFrame with tick data

        Example:
            >>> processor = ExnessDataProcessor()
            >>> # Query all Raw_Spread ticks for 2024
            >>> df = processor.query_ticks("EURUSD", start_date="2024-01-01", end_date="2024-12-31")
            >>> # Query Standard ticks with custom filter
            >>> df = processor.query_ticks("EURUSD", variant="standard", filter_sql="Bid > 1.10")
        """
        duckdb_path = self.base_dir / f"{pair.lower()}.duckdb"
        if not duckdb_path.exists():
            raise FileNotFoundError(f"Database not found: {duckdb_path}")

        table_name = "raw_spread_ticks" if variant == "raw_spread" else "standard_ticks"

        where_clauses = []
        if start_date:
            where_clauses.append(f"Timestamp >= '{start_date}'")
        if end_date:
            where_clauses.append(f"Timestamp <= '{end_date}'")
        if filter_sql:
            where_clauses.append(f"({filter_sql})")

        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

        conn = duckdb.connect(str(duckdb_path), read_only=True)
        df = conn.execute(f"""
            SELECT * FROM {table_name}
            WHERE {where_sql}
            ORDER BY Timestamp
        """).df()
        conn.close()

        return df

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
            DataFrame with OHLC data (Phase7 13-column schema v1.2.0)

        Example:
            >>> processor = ExnessDataProcessor()
            >>> # Query 1m OHLC for January 2024
            >>> df = processor.query_ohlc("EURUSD", timeframe="1m", start_date="2024-01-01", end_date="2024-01-31")
            >>> # Query 1h OHLC (on-demand resampling)
            >>> df = processor.query_ohlc("EURUSD", timeframe="1h", start_date="2024-01-01")
        """
        duckdb_path = self.base_dir / f"{pair.lower()}.duckdb"

        if not duckdb_path.exists():
            raise FileNotFoundError(f"Database not found: {duckdb_path}")

        # Build WHERE clause for date filtering
        where_clauses = []
        if start_date:
            where_clauses.append(f"Timestamp >= '{start_date}'")
        if end_date:
            where_clauses.append(f"Timestamp <= '{end_date}'")
        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

        conn = duckdb.connect(str(duckdb_path), read_only=True)

        if timeframe == "1m":
            df = conn.execute(f"""
                SELECT * FROM ohlc_1m
                WHERE {where_sql}
                ORDER BY Timestamp
            """).df()
        else:
            # Resample to higher timeframes
            timeframe_config = {
                "5m": (5, "minute"),
                "15m": (15, "minute"),
                "30m": (30, "minute"),
                "1h": (60, "hour"),
                "4h": (240, "hour"),
                "1d": (1440, "day"),
            }

            if timeframe not in timeframe_config:
                raise ValueError(f"Unsupported timeframe: {timeframe}")

            minutes, trunc_unit = timeframe_config[timeframe]

            # For hour and day, use DATE_TRUNC directly
            if trunc_unit in ("hour", "day"):
                time_expr = f"DATE_TRUNC('{trunc_unit}', Timestamp)"
                select_clause = OHLCSchema.get_resampling_select_clause(time_expr)
                df = conn.execute(f"""
                    SELECT
                        {select_clause}
                    FROM ohlc_1m
                    WHERE {where_sql}
                    GROUP BY {time_expr}
                    ORDER BY Timestamp
                """).df()
            else:
                # For sub-hour intervals, use time bucketing
                time_expr = f"TIME_BUCKET(INTERVAL '{minutes} minutes', Timestamp)"
                select_clause = OHLCSchema.get_resampling_select_clause(time_expr)
                df = conn.execute(f"""
                    SELECT
                        {select_clause}
                    FROM ohlc_1m
                    WHERE {where_sql}
                    GROUP BY {time_expr}
                    ORDER BY Timestamp
                """).df()

        conn.close()
        return df

    def get_data_coverage(self, pair: PairType = "EURUSD") -> CoverageInfo:
        """
        Get data coverage information for an instrument.

        Args:
            pair: Currency pair

        Returns:
            Dictionary with coverage information:
                - database_exists: Whether database file exists
                - duckdb_path: Path to database file
                - duckdb_size_mb: Database file size
                - raw_spread_ticks: Number of Raw_Spread ticks
                - standard_ticks: Number of Standard ticks
                - ohlc_bars: Number of 1m OHLC bars
                - earliest_date: Earliest tick timestamp
                - latest_date: Latest tick timestamp
                - date_range_days: Number of days covered

        Example:
            >>> processor = ExnessDataProcessor()
            >>> coverage = processor.get_data_coverage("EURUSD")
            >>> print(f"Coverage: {coverage['earliest_date']} to {coverage['latest_date']}")
            >>> print(f"Total: {coverage['raw_spread_ticks']:,} ticks")
        """
        duckdb_path = self.base_dir / f"{pair.lower()}.duckdb"

        if not duckdb_path.exists():
            return CoverageInfo(
                database_exists=False,
                duckdb_path=str(duckdb_path),
                duckdb_size_mb=0,
                raw_spread_ticks=0,
                standard_ticks=0,
                ohlc_bars=0,
                earliest_date=None,
                latest_date=None,
                date_range_days=0,
            )

        conn = duckdb.connect(str(duckdb_path), read_only=True)

        # Get counts
        raw_count = conn.execute("SELECT COUNT(*) FROM raw_spread_ticks").fetchone()[0]
        std_count = conn.execute("SELECT COUNT(*) FROM standard_ticks").fetchone()[0]
        ohlc_count = conn.execute("SELECT COUNT(*) FROM ohlc_1m").fetchone()[0]

        # Get date range
        result = conn.execute("""
            SELECT
                MIN(Timestamp) as earliest,
                MAX(Timestamp) as latest
            FROM raw_spread_ticks
        """).fetchone()

        conn.close()

        if result and result[0]:
            earliest = pd.to_datetime(result[0])
            latest = pd.to_datetime(result[1])
            date_range_days = (latest - earliest).days
        else:
            earliest = None
            latest = None
            date_range_days = 0

        return CoverageInfo(
            database_exists=True,
            duckdb_path=str(duckdb_path),
            duckdb_size_mb=duckdb_path.stat().st_size / 1024 / 1024,
            raw_spread_ticks=raw_count,
            standard_ticks=std_count,
            ohlc_bars=ohlc_count,
            earliest_date=str(earliest) if earliest else None,
            latest_date=str(latest) if latest else None,
            date_range_days=date_range_days,
        )
