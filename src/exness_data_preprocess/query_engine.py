"""
Query engine for tick and OHLC data retrieval.

SLOs:
- Availability: Queries must succeed or raise exception (no silent failures)
- Correctness: SQL queries must be accurate, date filtering must be inclusive
- Observability: All query operations use DuckDB native logging
- Maintainability: Single module for all query operations, off-the-shelf DuckDB

Handles:
- Tick data queries with date range and SQL filtering
- OHLC queries with on-demand resampling (1m, 5m, 15m, 30m, 1h, 4h, 1d)
- Data coverage statistics and metadata
- Read-only database connections for safe concurrent queries
"""

from pathlib import Path
from typing import Optional

import duckdb
import pandas as pd

from exness_data_preprocess.models import CoverageInfo, PairType, TimeframeType, VariantType
from exness_data_preprocess.schema import OHLCSchema


class QueryEngine:
    """
    Query tick and OHLC data from DuckDB databases.

    Responsibilities:
    - Query tick data with optional date range and SQL filtering
    - Query OHLC data with optional resampling to higher timeframes
    - Calculate data coverage statistics
    - Use read-only connections for safe concurrent access

    Example:
        >>> engine = QueryEngine(base_dir=Path("~/eon/exness-data/"))
        >>> df_ticks = engine.query_ticks("EURUSD", start_date="2024-01-01")
        >>> df_ohlc = engine.query_ohlc("EURUSD", timeframe="1h")
        >>> coverage = engine.get_data_coverage("EURUSD")
    """

    def __init__(self, base_dir: Path):
        """
        Initialize query engine.

        Args:
            base_dir: Base directory for DuckDB files

        Raises:
            Exception: If base_dir initialization fails
        """
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

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

        Raises:
            FileNotFoundError: If database does not exist
            Exception: If query execution fails

        Example:
            >>> engine = QueryEngine(base_dir=Path("~/eon/exness-data/"))
            >>> # Query all Raw_Spread ticks for 2024
            >>> df = engine.query_ticks("EURUSD", start_date="2024-01-01", end_date="2024-12-31")
            >>> # Query Standard ticks with custom filter
            >>> df = engine.query_ticks("EURUSD", variant="standard", filter_sql="Bid > 1.10")
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
            DataFrame with OHLC data (Phase7 30-column schema v1.6.0)

        Raises:
            FileNotFoundError: If database does not exist
            ValueError: If timeframe is not supported
            Exception: If query execution fails

        Example:
            >>> engine = QueryEngine(base_dir=Path("~/eon/exness-data/"))
            >>> # Query 1m OHLC for January 2024
            >>> df = engine.query_ohlc("EURUSD", timeframe="1m", start_date="2024-01-01", end_date="2024-01-31")
            >>> # Query 1h OHLC (on-demand resampling)
            >>> df = engine.query_ohlc("EURUSD", timeframe="1h", start_date="2024-01-01")
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

        Raises:
            Exception: If database query fails (only if database exists)

        Example:
            >>> engine = QueryEngine(base_dir=Path("~/eon/exness-data/"))
            >>> coverage = engine.get_data_coverage("EURUSD")
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
