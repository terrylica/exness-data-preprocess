"""
Query engine for ClickHouse tick and OHLC data retrieval.

ADR: /docs/adr/2025-12-09-exness-clickhouse-migration.md

SLOs:
- Availability: Queries must succeed or raise exception (no silent failures)
- Correctness: SQL queries must be accurate, date filtering must be inclusive
- Observability: All query operations use structured logging
- Maintainability: Single module for all query operations, off-the-shelf ClickHouse

Handles:
- Tick data queries with date range and SQL filtering
- OHLC queries with on-demand resampling (1m, 5m, 15m, 30m, 1h, 4h, 1d)
- Data coverage statistics and metadata
- Parameterized queries for safe, efficient access
"""

from typing import Literal

import pandas as pd
from clickhouse_connect.driver import Client

from exness_data_preprocess.clickhouse_client import (
    ClickHouseQueryError,
    execute_query,
    get_client,
)
from exness_data_preprocess.models import CoverageInfo, PairType, TimeframeType, VariantType


class ClickHouseQueryEngine:
    """
    Query tick and OHLC data from ClickHouse.

    Responsibilities:
    - Query tick data with optional date range and SQL filtering
    - Query OHLC data with optional resampling to higher timeframes
    - Calculate data coverage statistics
    - Use parameterized queries for safe access

    Example:
        >>> engine = ClickHouseQueryEngine()
        >>> df_ticks = engine.query_ticks("EURUSD", start_date="2024-01-01")
        >>> df_ohlc = engine.query_ohlc("EURUSD", timeframe="1h")
        >>> coverage = engine.get_data_coverage("EURUSD")
    """

    DATABASE = "exness"

    def __init__(self, client: Client | None = None):
        """
        Initialize query engine.

        Args:
            client: Optional ClickHouse client (creates one if not provided)
        """
        self._client = client
        self._owns_client = client is None

    @property
    def client(self) -> Client:
        """Get or create ClickHouse client."""
        if self._client is None:
            self._client = get_client()
        return self._client

    def close(self) -> None:
        """Close client connection if we own it."""
        if self._owns_client and self._client is not None:
            self._client.close()
            self._client = None

    def query_ticks(
        self,
        instrument: PairType = "EURUSD",
        variant: VariantType = "raw_spread",
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int | None = None,
    ) -> pd.DataFrame:
        """
        Query tick data with optional date range filtering.

        Args:
            instrument: Instrument symbol (e.g., "EURUSD")
            variant: "raw_spread" or "standard"
            start_date: Start date (YYYY-MM-DD), inclusive
            end_date: End date (YYYY-MM-DD), inclusive
            limit: Maximum number of rows to return

        Returns:
            DataFrame with tick data (timestamp, bid, ask)

        Raises:
            ClickHouseQueryError: If query execution fails

        Example:
            >>> engine = ClickHouseQueryEngine()
            >>> # Query all Raw_Spread ticks for 2024
            >>> df = engine.query_ticks("EURUSD", start_date="2024-01-01", end_date="2024-12-31")
            >>> # Query Standard ticks with limit
            >>> df = engine.query_ticks("EURUSD", variant="standard", limit=1000)
        """
        table_name = f"{variant}_ticks"
        instrument = instrument.upper()

        # Build WHERE clauses
        where_parts = ["instrument = {instrument:String}"]
        params: dict = {"instrument": instrument}

        if start_date:
            where_parts.append("timestamp >= {start_date:DateTime64}")
            params["start_date"] = start_date
        if end_date:
            where_parts.append("timestamp <= {end_date:DateTime64}")
            params["end_date"] = end_date

        where_sql = " AND ".join(where_parts)
        limit_sql = f"LIMIT {limit}" if limit else ""

        query = f"""
            SELECT timestamp, bid, ask
            FROM {self.DATABASE}.{table_name}
            WHERE {where_sql}
            ORDER BY timestamp
            {limit_sql}
        """

        result = execute_query(self.client, query, parameters=params)
        return result.result_set.to_pandas() if hasattr(result, 'result_set') else pd.DataFrame(
            result.result_rows,
            columns=["timestamp", "bid", "ask"]
        )

    def query_ohlc(
        self,
        instrument: PairType = "EURUSD",
        timeframe: TimeframeType = "1m",
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> pd.DataFrame:
        """
        Query OHLC data with optional date range filtering and resampling.

        Uses parameterized view pattern for on-demand resampling.

        Args:
            instrument: Instrument symbol (e.g., "EURUSD")
            timeframe: Timeframe (1m, 5m, 15m, 30m, 1h, 4h, 1d)
            start_date: Start date (YYYY-MM-DD), inclusive
            end_date: End date (YYYY-MM-DD), inclusive

        Returns:
            DataFrame with OHLC data

        Raises:
            ValueError: If timeframe is not supported
            ClickHouseQueryError: If query execution fails

        Example:
            >>> engine = ClickHouseQueryEngine()
            >>> # Query 1m OHLC for January 2024
            >>> df = engine.query_ohlc("EURUSD", timeframe="1m", start_date="2024-01-01", end_date="2024-01-31")
            >>> # Query 1h OHLC (on-demand resampling)
            >>> df = engine.query_ohlc("EURUSD", timeframe="1h", start_date="2024-01-01")
        """
        instrument = instrument.upper()

        # Timeframe to minutes mapping
        timeframe_minutes = {
            "1m": 1,
            "5m": 5,
            "15m": 15,
            "30m": 30,
            "1h": 60,
            "4h": 240,
            "1d": 1440,
        }

        if timeframe not in timeframe_minutes:
            raise ValueError(f"Unsupported timeframe: {timeframe}")

        minutes = timeframe_minutes[timeframe]

        # Build WHERE clauses
        where_parts = ["instrument = {instrument:String}"]
        params: dict = {"instrument": instrument, "minutes": minutes}

        if start_date:
            where_parts.append("timestamp >= {start_date:DateTime64}")
            params["start_date"] = start_date
        if end_date:
            where_parts.append("timestamp <= {end_date:DateTime64}")
            params["end_date"] = end_date

        where_sql = " AND ".join(where_parts)

        if timeframe == "1m":
            # Direct query for 1m data
            query = f"""
                SELECT *
                FROM {self.DATABASE}.ohlc_1m
                WHERE {where_sql}
                ORDER BY timestamp
            """
        else:
            # On-demand resampling using toStartOfInterval
            query = f"""
                SELECT
                    toStartOfInterval(timestamp, INTERVAL {{minutes:UInt32}} MINUTE) AS timestamp,
                    argMin(open, timestamp) AS open,
                    max(high) AS high,
                    min(low) AS low,
                    argMax(close, timestamp) AS close,
                    avg(raw_spread_avg) AS raw_spread_avg,
                    avg(standard_spread_avg) AS standard_spread_avg,
                    sum(tick_count_raw_spread) AS tick_count_raw_spread,
                    sum(tick_count_standard) AS tick_count_standard,
                    -- Normalized metrics recalculated
                    if(avg(raw_spread_avg) > 0,
                       (max(high) - min(low)) / avg(raw_spread_avg),
                       NULL) AS range_per_spread,
                    if(sum(tick_count_raw_spread) > 0,
                       (max(high) - min(low)) / sum(tick_count_raw_spread),
                       NULL) AS range_per_tick,
                    if(avg(raw_spread_avg) > 0,
                       abs(argMax(close, timestamp) - argMin(open, timestamp)) / avg(raw_spread_avg),
                       NULL) AS body_per_spread,
                    if(sum(tick_count_raw_spread) > 0,
                       abs(argMax(close, timestamp) - argMin(open, timestamp)) / sum(tick_count_raw_spread),
                       NULL) AS body_per_tick,
                    -- Session columns: take max (any non-zero means session was active)
                    max(ny_hour) AS ny_hour,
                    max(london_hour) AS london_hour,
                    any(ny_session) AS ny_session,
                    any(london_session) AS london_session,
                    max(is_us_holiday) AS is_us_holiday,
                    max(is_uk_holiday) AS is_uk_holiday,
                    max(is_major_holiday) AS is_major_holiday,
                    max(is_nyse_session) AS is_nyse_session,
                    max(is_lse_session) AS is_lse_session,
                    max(is_xswx_session) AS is_xswx_session,
                    max(is_xfra_session) AS is_xfra_session,
                    max(is_xtse_session) AS is_xtse_session,
                    max(is_xnze_session) AS is_xnze_session,
                    max(is_xtks_session) AS is_xtks_session,
                    max(is_xasx_session) AS is_xasx_session,
                    max(is_xhkg_session) AS is_xhkg_session,
                    max(is_xses_session) AS is_xses_session
                FROM {self.DATABASE}.ohlc_1m
                WHERE {where_sql}
                GROUP BY toStartOfInterval(timestamp, INTERVAL {{minutes:UInt32}} MINUTE)
                ORDER BY timestamp
            """

        result = execute_query(self.client, query, parameters=params)

        # Convert to DataFrame
        if hasattr(result, 'result_set'):
            return result.result_set.to_pandas()
        else:
            columns = [col[0] for col in result.column_names] if hasattr(result, 'column_names') else None
            return pd.DataFrame(result.result_rows, columns=columns)

    def get_data_coverage(self, instrument: PairType = "EURUSD") -> CoverageInfo:
        """
        Get data coverage information for an instrument.

        Args:
            instrument: Instrument symbol (e.g., "EURUSD")

        Returns:
            CoverageInfo with coverage information

        Raises:
            ClickHouseQueryError: If query fails

        Example:
            >>> engine = ClickHouseQueryEngine()
            >>> coverage = engine.get_data_coverage("EURUSD")
            >>> print(f"Coverage: {coverage.earliest_date} to {coverage.latest_date}")
            >>> print(f"Total: {coverage.raw_spread_ticks:,} ticks")
        """
        instrument = instrument.upper()

        # Get tick counts
        query = """
            SELECT
                countIf(1, table = 'raw_spread_ticks') AS raw_count,
                countIf(1, table = 'standard_ticks') AS std_count
            FROM (
                SELECT 'raw_spread_ticks' AS table
                FROM {database:Identifier}.raw_spread_ticks
                WHERE instrument = {instrument:String}
                UNION ALL
                SELECT 'standard_ticks' AS table
                FROM {database:Identifier}.standard_ticks
                WHERE instrument = {instrument:String}
            )
        """

        try:
            result = execute_query(
                self.client,
                query,
                parameters={"database": self.DATABASE, "instrument": instrument},
            )
            raw_count = result.first_row[0] if result.result_rows else 0
            std_count = result.first_row[1] if result.result_rows else 0
        except ClickHouseQueryError:
            raw_count = 0
            std_count = 0

        # Get OHLC count
        try:
            ohlc_result = execute_query(
                self.client,
                f"SELECT count() FROM {self.DATABASE}.ohlc_1m WHERE instrument = {{instrument:String}}",
                parameters={"instrument": instrument},
            )
            ohlc_count = ohlc_result.first_row[0] if ohlc_result.result_rows else 0
        except ClickHouseQueryError:
            ohlc_count = 0

        # Get date range
        try:
            range_result = execute_query(
                self.client,
                f"""
                SELECT
                    min(timestamp) AS earliest,
                    max(timestamp) AS latest
                FROM {self.DATABASE}.raw_spread_ticks
                WHERE instrument = {{instrument:String}}
                """,
                parameters={"instrument": instrument},
            )

            if range_result.result_rows and range_result.first_row[0]:
                earliest = pd.to_datetime(range_result.first_row[0])
                latest = pd.to_datetime(range_result.first_row[1])
                date_range_days = (latest - earliest).days
            else:
                earliest = None
                latest = None
                date_range_days = 0
        except ClickHouseQueryError:
            earliest = None
            latest = None
            date_range_days = 0

        return CoverageInfo(
            database_exists=True,  # ClickHouse is always "exists" if connection works
            duckdb_path="",  # Not applicable for ClickHouse
            duckdb_size_mb=0,  # Not applicable for ClickHouse
            raw_spread_ticks=raw_count,
            standard_ticks=std_count,
            ohlc_bars=ohlc_count,
            earliest_date=str(earliest) if earliest else None,
            latest_date=str(latest) if latest else None,
            date_range_days=date_range_days,
        )

    def get_instruments(self) -> list[str]:
        """
        Get list of all instruments with data.

        Returns:
            List of instrument symbols
        """
        result = execute_query(
            self.client,
            f"SELECT DISTINCT instrument FROM {self.DATABASE}.raw_spread_ticks ORDER BY instrument",
        )
        return [row[0] for row in result.result_rows]
