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


from collections.abc import Iterator

import pandas as pd
from clickhouse_connect.driver import Client

from exness_data_preprocess.clickhouse_base import ClickHouseClientMixin
from exness_data_preprocess.clickhouse_client import (
    ClickHouseQueryError,
    execute_query,
)
from exness_data_preprocess.models import (
    CoverageInfo,
    CursorResult,
    PairType,
    TimeframeType,
    VariantType,
)


class ClickHouseQueryEngine(ClickHouseClientMixin):
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
        self._init_client(client)

    def query_ticks(
        self,
        instrument: PairType = "EURUSD",
        variant: VariantType = "raw_spread",
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> pd.DataFrame:
        """
        Query tick data with optional date range filtering and pagination.

        ADR: /docs/adr/2025-12-10-clickhouse-e2e-validation-pipeline.md

        Args:
            instrument: Instrument symbol (e.g., "EURUSD")
            variant: "raw_spread" or "standard"
            start_date: Start date (YYYY-MM-DD), inclusive
            end_date: End date (YYYY-MM-DD), inclusive
            limit: Maximum number of rows to return
            offset: Number of rows to skip (for pagination)

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
            >>> # Paginate through results
            >>> page1 = engine.query_ticks("EURUSD", limit=1000, offset=0)
            >>> page2 = engine.query_ticks("EURUSD", limit=1000, offset=1000)
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
        offset_sql = f"OFFSET {offset}" if offset else ""

        query = f"""
            SELECT timestamp, bid, ask
            FROM {self.DATABASE}.{table_name}
            WHERE {where_sql}
            ORDER BY timestamp
            {limit_sql}
            {offset_sql}
        """

        result = execute_query(self.client, query, parameters=params)
        return pd.DataFrame(result.result_rows, columns=["timestamp", "bid", "ask"])

    def query_ohlc(
        self,
        instrument: PairType = "EURUSD",
        timeframe: TimeframeType = "1m",
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> pd.DataFrame:
        """
        Query OHLC data with optional date range filtering, resampling, and pagination.

        ADR: /docs/adr/2025-12-10-clickhouse-e2e-validation-pipeline.md

        Uses parameterized view pattern for on-demand resampling.

        Args:
            instrument: Instrument symbol (e.g., "EURUSD")
            timeframe: Timeframe (1m, 5m, 15m, 30m, 1h, 4h, 1d)
            start_date: Start date (YYYY-MM-DD), inclusive
            end_date: End date (YYYY-MM-DD), inclusive
            limit: Maximum number of rows to return
            offset: Number of rows to skip (for pagination)

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
            >>> # Paginate through results
            >>> page1 = engine.query_ohlc("EURUSD", limit=1000, offset=0)
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
        limit_sql = f"LIMIT {limit}" if limit else ""
        offset_sql = f"OFFSET {offset}" if offset else ""

        if timeframe == "1m":
            # Direct query for 1m data
            query = f"""
                SELECT *
                FROM {self.DATABASE}.ohlc_1m
                WHERE {where_sql}
                ORDER BY timestamp
                {limit_sql}
                {offset_sql}
            """
        else:
            # On-demand resampling using CTE to avoid ClickHouse nested aggregate issue
            # ADR: /docs/adr/2025-12-10-clickhouse-e2e-validation-pipeline.md
            query = f"""
                WITH base AS (
                    SELECT
                        toStartOfInterval(timestamp, INTERVAL {{minutes:UInt32}} MINUTE) AS ts,
                        argMin(open, timestamp) AS open,
                        max(high) AS high,
                        min(low) AS low,
                        argMax(close, timestamp) AS close,
                        avg(raw_spread_avg) AS raw_spread_avg,
                        avg(standard_spread_avg) AS standard_spread_avg,
                        sum(tick_count_raw_spread) AS tick_count_raw_spread,
                        sum(tick_count_standard) AS tick_count_standard,
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
                    GROUP BY ts
                )
                SELECT
                    ts AS timestamp,
                    open, high, low, close,
                    raw_spread_avg, standard_spread_avg,
                    tick_count_raw_spread, tick_count_standard,
                    if(raw_spread_avg > 0, (high - low) / raw_spread_avg, NULL) AS range_per_spread,
                    if(tick_count_raw_spread > 0, (high - low) / tick_count_raw_spread, NULL) AS range_per_tick,
                    if(raw_spread_avg > 0, abs(close - open) / raw_spread_avg, NULL) AS body_per_spread,
                    if(tick_count_raw_spread > 0, abs(close - open) / tick_count_raw_spread, NULL) AS body_per_tick,
                    ny_hour, london_hour, ny_session, london_session,
                    is_us_holiday, is_uk_holiday, is_major_holiday,
                    is_nyse_session, is_lse_session, is_xswx_session, is_xfra_session,
                    is_xtse_session, is_xnze_session, is_xtks_session, is_xasx_session,
                    is_xhkg_session, is_xses_session
                FROM base
                ORDER BY timestamp
                {limit_sql}
                {offset_sql}
            """

        result = execute_query(self.client, query, parameters=params)

        # Convert to DataFrame using column names from result
        columns = result.column_names if hasattr(result, 'column_names') else None
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
            database=self.DATABASE,  # v2.0.0: ClickHouse database name
            storage_bytes=0,  # TODO: Query system.tables for actual size
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

    def query_ticks_paginated(
        self,
        instrument: PairType = "EURUSD",
        variant: VariantType = "raw_spread",
        cursor: str | None = None,
        page_size: int = 100_000,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> CursorResult:
        """
        Query tick data with cursor-based pagination.

        ADR: /docs/adr/2025-12-10-clickhouse-e2e-validation-pipeline.md

        More efficient than OFFSET for large datasets because it uses timestamp
        as cursor instead of row counting.

        Args:
            instrument: Instrument symbol (e.g., "EURUSD")
            variant: "raw_spread" or "standard"
            cursor: ISO 8601 timestamp to start from (exclusive), None for first page
            page_size: Number of rows per page (default: 100,000)
            start_date: Start date filter (YYYY-MM-DD), inclusive
            end_date: End date filter (YYYY-MM-DD), inclusive

        Returns:
            CursorResult with data, next_cursor, has_more, and page_size

        Example:
            >>> engine = ClickHouseQueryEngine()
            >>> result = engine.query_ticks_paginated("EURUSD", page_size=10000)
            >>> print(f"Got {len(result.data)} rows, has_more={result.has_more}")
            >>> if result.has_more:
            ...     next_page = engine.query_ticks_paginated("EURUSD", cursor=result.next_cursor)
        """
        table_name = f"{variant}_ticks"
        instrument = instrument.upper()

        # Build WHERE clauses
        where_parts = ["instrument = {instrument:String}"]
        params: dict = {"instrument": instrument}

        if cursor:
            where_parts.append("timestamp > {cursor:DateTime64}")
            params["cursor"] = cursor
        if start_date:
            where_parts.append("timestamp >= {start_date:DateTime64}")
            params["start_date"] = start_date
        if end_date:
            where_parts.append("timestamp <= {end_date:DateTime64}")
            params["end_date"] = end_date

        where_sql = " AND ".join(where_parts)

        # Fetch page_size + 1 to detect if there's more data
        query = f"""
            SELECT timestamp, bid, ask
            FROM {self.DATABASE}.{table_name}
            WHERE {where_sql}
            ORDER BY timestamp
            LIMIT {page_size + 1}
        """

        result = execute_query(self.client, query, parameters=params)
        df = pd.DataFrame(result.result_rows, columns=["timestamp", "bid", "ask"])

        # Check if there's more data
        has_more = len(df) > page_size
        if has_more:
            df = df.iloc[:page_size]  # Trim to page_size

        # Get next cursor from last timestamp
        next_cursor = None
        if has_more and len(df) > 0:
            last_ts = df.iloc[-1]["timestamp"]
            next_cursor = str(last_ts)

        return CursorResult(
            data=df,
            next_cursor=next_cursor,
            has_more=has_more,
            page_size=page_size,
        )

    def query_ticks_batches(
        self,
        instrument: PairType = "EURUSD",
        variant: VariantType = "raw_spread",
        batch_size: int = 100_000,
        start_date: str | None = None,
        end_date: str | None = None,
        max_batches: int | None = None,
    ) -> Iterator[pd.DataFrame]:
        """
        Iterate through tick data in memory-efficient batches.

        ADR: /docs/adr/2025-12-10-clickhouse-e2e-validation-pipeline.md

        Uses cursor-based pagination internally to avoid loading entire dataset
        into memory. Each batch is yielded and can be garbage collected after
        processing.

        Args:
            instrument: Instrument symbol (e.g., "EURUSD")
            variant: "raw_spread" or "standard"
            batch_size: Number of rows per batch (default: 100,000 = ~8MB)
            start_date: Start date filter (YYYY-MM-DD), inclusive
            end_date: End date filter (YYYY-MM-DD), inclusive
            max_batches: Maximum number of batches to yield (None = unlimited)

        Yields:
            DataFrame batches of tick data

        Example:
            >>> engine = ClickHouseQueryEngine()
            >>> for batch in engine.query_ticks_batches("EURUSD", batch_size=50000):
            ...     process(batch)  # ~4MB per batch
            ...     # Batch garbage collected after loop iteration
        """
        cursor = None
        batch_count = 0

        while True:
            result = self.query_ticks_paginated(
                instrument=instrument,
                variant=variant,
                cursor=cursor,
                page_size=batch_size,
                start_date=start_date,
                end_date=end_date,
            )

            if len(result.data) == 0:
                break

            yield result.data
            batch_count += 1

            if max_batches is not None and batch_count >= max_batches:
                break

            if not result.has_more:
                break

            cursor = result.next_cursor
