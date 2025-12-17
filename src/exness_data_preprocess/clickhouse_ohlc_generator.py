"""
OHLC (Open-High-Low-Close) generation from ClickHouse tick data.

ADR: /docs/adr/2025-12-09-exness-clickhouse-migration.md

SLOs:
- Availability: OHLC generation must succeed or raise exception (no silent failures)
- Correctness: Phase7 30-column schema with dual variants, normalized metrics, holiday/session detection
- Observability: All OHLC operations logged via structured logging
- Maintainability: Single module for all OHLC logic, off-the-shelf ClickHouse and exchange_calendars

Handles:
- Phase7 30-column OHLC schema
- BID-only OHLC construction from raw_spread_ticks
- ASOF JOIN with standard_ticks for dual spread tracking
- Normalized metrics (range_per_spread, range_per_tick, body_per_spread, body_per_tick)
- Timezone/session tracking (NY and London sessions)
- Holiday detection (US, UK, major holidays via exchange_calendars)
- 10 global exchange session flags with trading hour detection
"""

import pandas as pd
from clickhouse_connect.driver import Client

from exness_data_preprocess.clickhouse_base import ClickHouseClientMixin
from exness_data_preprocess.clickhouse_client import (
    execute_command,
    execute_query,
)
from exness_data_preprocess.exchanges import EXCHANGES
from exness_data_preprocess.session_detector import SessionDetector


class ClickHouseOHLCGenerator(ClickHouseClientMixin):
    """
    Generate Phase7 30-column OHLC from dual-variant tick data in ClickHouse.

    Responsibilities:
    - Delete existing OHLC data before regeneration (by instrument)
    - Generate BID-only OHLC from raw_spread_ticks with ASOF JOIN to standard_ticks
    - Calculate normalized spread metrics (NULL-safe)
    - Add timezone/session tracking for NY and London
    - Delegate holiday and session detection to SessionDetector
    - Insert OHLC data with holiday and session flags

    Example:
        >>> session_detector = SessionDetector()
        >>> generator = ClickHouseOHLCGenerator(session_detector)
        >>> generator.regenerate_ohlc("EURUSD")
    """

    DATABASE = "exness"

    def __init__(self, session_detector: SessionDetector, client: Client | None = None):
        """
        Initialize OHLC generator.

        Args:
            session_detector: SessionDetector instance for holiday/session detection
            client: Optional ClickHouse client (creates one if not provided)
        """
        self.session_detector = session_detector
        self._init_client(client)

    def regenerate_ohlc(
        self,
        instrument: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> int:
        """
        Generate/update OHLC table with Phase7 schema (30 columns).

        Uses ASOF JOIN to combine raw_spread_ticks and standard_ticks.
        Includes normalized spread metrics, timezone/session tracking,
        holiday detection, and 10 global exchange session flags.

        Supports three operation modes:
        1. Full regeneration (start_date=None, end_date=None): DELETE all + INSERT all
        2. Incremental append (start_date=YYYY-MM-DD, end_date=None): INSERT new data only
        3. Range update (start_date + end_date): DELETE range + INSERT range

        Args:
            instrument: Instrument symbol (e.g., "EURUSD")
            start_date: Optional start date (YYYY-MM-DD) for filtering tick data.
            end_date: Optional end date (YYYY-MM-DD) for filtering tick data.

        Returns:
            Number of OHLC bars generated

        Raises:
            ClickHouseQueryError: If OHLC generation fails

        Example:
            >>> generator = ClickHouseOHLCGenerator(SessionDetector())
            >>> # Full regeneration
            >>> generator.regenerate_ohlc("EURUSD")
            >>> # Incremental append
            >>> generator.regenerate_ohlc("EURUSD", start_date="2024-10-01")
        """
        instrument = instrument.upper()

        # Delete existing OHLC data based on mode
        if start_date is None and end_date is None:
            # Mode 1: Full regeneration - delete all data for instrument
            execute_command(
                self.client,
                f"ALTER TABLE {self.DATABASE}.ohlc_1m DELETE WHERE instrument = {{instrument:String}}",
            )
            # Wait for mutation to complete
            self._wait_for_mutations()
        elif start_date is not None and end_date is not None:
            # Mode 3: Range update - delete specific range
            execute_command(
                self.client,
                f"""
                ALTER TABLE {self.DATABASE}.ohlc_1m DELETE
                WHERE instrument = {{instrument:String}}
                  AND timestamp >= {{start_date:DateTime64}}
                  AND timestamp < addMonths(toDate({{end_date:String}}), 1)
                """,
            )
            self._wait_for_mutations()
        # Mode 2: Incremental append - no delete, ReplacingMergeTree handles deduplication

        # Build WHERE clause for date filtering
        where_parts = ["r.instrument = {instrument:String}"]
        params: dict = {"instrument": instrument}

        if start_date:
            where_parts.append("r.timestamp >= {start_date:DateTime64}")
            params["start_date"] = start_date
        if end_date:
            where_parts.append("r.timestamp < addMonths(toDate({end_date:String}), 1)")
            params["end_date"] = end_date

        where_sql = " AND ".join(where_parts)

        # Generate session column initializations from exchange registry
        session_columns = ", ".join([f"0 AS is_{name}_session" for name in EXCHANGES.keys()])

        # Generate Phase7 OHLC with normalized metrics
        # Note: ClickHouse ASOF JOIN matches closest preceding timestamp from standard_ticks
        insert_sql = f"""
            INSERT INTO {self.DATABASE}.ohlc_1m
            SELECT
                {{instrument:String}} AS instrument,
                toStartOfMinute(r.timestamp) AS timestamp,
                argMin(r.bid, r.timestamp) AS open,
                max(r.bid) AS high,
                min(r.bid) AS low,
                argMax(r.bid, r.timestamp) AS close,
                avg(r.ask - r.bid) AS raw_spread_avg,
                avg(s.ask - s.bid) AS standard_spread_avg,
                toUInt32(count(r.timestamp)) AS tick_count_raw_spread,
                toUInt32(countIf(s.timestamp IS NOT NULL)) AS tick_count_standard,
                -- Normalized spread metrics (NULL-safe)
                if(avg(s.ask - s.bid) > 0,
                   toFloat32((max(r.bid) - min(r.bid)) / avg(s.ask - s.bid)),
                   NULL) AS range_per_spread,
                if(countIf(s.timestamp IS NOT NULL) > 0,
                   toFloat32((max(r.bid) - min(r.bid)) / countIf(s.timestamp IS NOT NULL)),
                   NULL) AS range_per_tick,
                if(avg(s.ask - s.bid) > 0,
                   toFloat32(abs(argMax(r.bid, r.timestamp) - argMin(r.bid, r.timestamp)) / avg(s.ask - s.bid)),
                   NULL) AS body_per_spread,
                if(countIf(s.timestamp IS NOT NULL) > 0,
                   toFloat32(abs(argMax(r.bid, r.timestamp) - argMin(r.bid, r.timestamp)) / countIf(s.timestamp IS NOT NULL)),
                   NULL) AS body_per_tick,
                -- Timezone-aware session columns
                toUInt8(toHour(toTimezone(toStartOfMinute(r.timestamp), 'America/New_York'))) AS ny_hour,
                toUInt8(toHour(toTimezone(toStartOfMinute(r.timestamp), 'Europe/London'))) AS london_hour,
                multiIf(
                    toHour(toTimezone(toStartOfMinute(r.timestamp), 'America/New_York')) >= 9
                    AND toHour(toTimezone(toStartOfMinute(r.timestamp), 'America/New_York')) <= 16,
                    'NY_Session',
                    toHour(toTimezone(toStartOfMinute(r.timestamp), 'America/New_York')) >= 17
                    AND toHour(toTimezone(toStartOfMinute(r.timestamp), 'America/New_York')) <= 20,
                    'NY_After_Hours',
                    'NY_Closed'
                ) AS ny_session,
                if(
                    toHour(toTimezone(toStartOfMinute(r.timestamp), 'Europe/London')) >= 8
                    AND toHour(toTimezone(toStartOfMinute(r.timestamp), 'Europe/London')) <= 16,
                    'London_Session',
                    'London_Closed'
                ) AS london_session,
                -- Holiday columns (initialized to 0, updated via session_detector)
                toUInt8(0) AS is_us_holiday,
                toUInt8(0) AS is_uk_holiday,
                toUInt8(0) AS is_major_holiday,
                -- Trading session flags (initialized to 0, updated via session_detector)
                {session_columns}
            FROM {self.DATABASE}.raw_spread_ticks AS r
            ASOF LEFT JOIN {self.DATABASE}.standard_ticks AS s
                ON r.instrument = s.instrument
                AND r.timestamp >= s.timestamp
            WHERE {where_sql}
            GROUP BY toStartOfMinute(r.timestamp)
            ORDER BY timestamp
        """

        execute_command(self.client, insert_sql, parameters=params)

        # Get count of generated OHLC bars
        count_where = ["instrument = {instrument:String}"]
        if start_date:
            count_where.append("timestamp >= {start_date:DateTime64}")
        if end_date:
            count_where.append("timestamp < addMonths(toDate({end_date:String}), 1)")

        count_result = execute_query(
            self.client,
            f"SELECT count() FROM {self.DATABASE}.ohlc_1m WHERE " + " AND ".join(count_where),
            parameters=params,
        )
        ohlc_count = count_result.first_row[0] if count_result.result_rows else 0

        # Update holiday and session flags using session_detector
        self._update_session_flags(instrument, start_date, end_date)

        return ohlc_count

    def _update_session_flags(
        self,
        instrument: str,
        start_date: str | None,
        end_date: str | None,
    ) -> None:
        """
        Update holiday and session flags using SessionDetector.

        Since ClickHouse is OLAP-optimized (not UPDATE-friendly), we:
        1. Query timestamps from ohlc_1m
        2. Calculate flags using SessionDetector
        3. Delete old rows and re-insert with updated flags

        Args:
            instrument: Instrument symbol
            start_date: Optional start date filter
            end_date: Optional end date filter
        """
        print(f"  Detecting holidays and sessions for {len(EXCHANGES)} exchanges...")

        # Build WHERE clause
        where_parts = ["instrument = {instrument:String}"]
        params: dict = {"instrument": instrument}

        if start_date:
            where_parts.append("timestamp >= {start_date:DateTime64}")
            params["start_date"] = start_date
        if end_date:
            where_parts.append("timestamp < addMonths(toDate({end_date:String}), 1)")
            params["end_date"] = end_date

        where_sql = " AND ".join(where_parts)

        # Query all OHLC data that needs session flags updated
        result = execute_query(
            self.client,
            f"SELECT * FROM {self.DATABASE}.ohlc_1m WHERE {where_sql} ORDER BY timestamp",
            parameters=params,
        )

        if not result.result_rows:
            return

        # Convert to DataFrame for session_detector
        columns = (
            [col[0] for col in result.column_names] if hasattr(result, "column_names") else None
        )
        df = pd.DataFrame(result.result_rows, columns=columns)

        if len(df) == 0:
            return

        # Prepare DataFrame for session_detector
        df["ts"] = pd.to_datetime(df["timestamp"])
        df["date"] = df["ts"].dt.date

        # Delegate to session_detector
        df = self.session_detector.detect_sessions_and_holidays(df)

        # Report session counts
        session_counts = {name: df[f"is_{name}_session"].sum() for name in EXCHANGES.keys()}

        us_holidays = df[df["is_us_holiday"] == 1]["date"].nunique()
        uk_holidays = df[df["is_uk_holiday"] == 1]["date"].nunique()
        major_holidays = df[df["is_major_holiday"] == 1]["date"].nunique()
        print(f"  ✓ Holidays: {us_holidays} US, {uk_holidays} UK, {major_holidays} major")

        session_summary = ", ".join(
            [f"{name.upper()}: {count}" for name, count in session_counts.items()]
        )
        print(f"  ✓ Trading minutes: {session_summary}")

        # For ClickHouse, we need to delete and re-insert since UPDATE is expensive
        # Delete existing rows for this range
        execute_command(
            self.client,
            f"ALTER TABLE {self.DATABASE}.ohlc_1m DELETE WHERE {where_sql}",
            parameters=params,
        )
        self._wait_for_mutations()

        # Prepare data for insertion
        # Map session_detector column names back to schema
        insert_df = df[
            [
                "instrument",
                "timestamp",
                "open",
                "high",
                "low",
                "close",
                "raw_spread_avg",
                "standard_spread_avg",
                "tick_count_raw_spread",
                "tick_count_standard",
                "range_per_spread",
                "range_per_tick",
                "body_per_spread",
                "body_per_tick",
                "ny_hour",
                "london_hour",
                "ny_session",
                "london_session",
                "is_us_holiday",
                "is_uk_holiday",
                "is_major_holiday",
            ]
            + [f"is_{name}_session" for name in EXCHANGES.keys()]
        ].copy()

        # Convert types for ClickHouse
        insert_df["timestamp"] = pd.to_datetime(insert_df["timestamp"])

        # Insert updated data
        self.client.insert(
            table="ohlc_1m",
            data=insert_df,
            database=self.DATABASE,
        )

    def _wait_for_mutations(self, timeout_seconds: int = 60) -> None:
        """
        Wait for all mutations to complete.

        Args:
            timeout_seconds: Maximum time to wait
        """
        import time

        start_time = time.time()
        while time.time() - start_time < timeout_seconds:
            result = execute_query(
                self.client,
                f"""
                SELECT count()
                FROM system.mutations
                WHERE database = '{self.DATABASE}'
                  AND is_done = 0
                """,
            )
            if result.first_row[0] == 0:
                return
            time.sleep(0.5)
