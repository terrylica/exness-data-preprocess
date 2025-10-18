"""
OHLC (Open-High-Low-Close) generation from tick data.

SLOs:
- Availability: OHLC generation must succeed or raise exception (no silent failures)
- Correctness: Phase7 30-column schema with dual variants, normalized metrics, holiday/session detection
- Observability: All OHLC operations logged via print statements
- Maintainability: Single module for all OHLC logic, off-the-shelf DuckDB and exchange_calendars

Handles:
- Phase7 30-column OHLC schema (v1.6.0)
- BID-only OHLC construction from Raw_Spread variant
- LEFT JOIN with Standard variant for dual spread tracking
- Normalized metrics (range_per_spread, range_per_tick, body_per_spread, body_per_tick)
- Timezone/session tracking (NY and London sessions)
- Holiday detection (US, UK, major holidays via exchange_calendars)
- 10 global exchange session flags with trading hour detection (NYSE, LSE, SIX, FWB, TSX, NZX, JPX, ASX, HKEX, SGX)
"""

from pathlib import Path
from typing import Optional

import duckdb

from exness_data_preprocess.exchanges import EXCHANGES
from exness_data_preprocess.session_detector import SessionDetector


class OHLCGenerator:
    """
    Generate Phase7 30-column OHLC from dual-variant tick data.

    Responsibilities:
    - Delete existing OHLC data before regeneration
    - Generate BID-only OHLC from Raw_Spread variant with LEFT JOIN to Standard
    - Calculate normalized spread metrics (NULL-safe)
    - Add timezone/session tracking for NY and London
    - Delegate holiday and session detection to SessionDetector
    - Update OHLC table with holiday and session flags

    Example:
        >>> session_detector = SessionDetector()
        >>> generator = OHLCGenerator(session_detector)
        >>> generator.regenerate_ohlc(Path("~/eon/exness-data/eurusd.duckdb"))
    """

    def __init__(self, session_detector: SessionDetector):
        """
        Initialize OHLC generator.

        Args:
            session_detector: SessionDetector instance for holiday/session detection

        Raises:
            Exception: If session_detector initialization fails
        """
        self.session_detector = session_detector

    def regenerate_ohlc(
        self,
        duckdb_path: Path,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> None:
        """
        Generate/update OHLC table with Phase7 schema (v1.6.0: 30 columns).

        Uses LEFT JOIN to combine Raw_Spread and Standard variants.
        Includes normalized spread metrics (v1.2.0+), timezone/session tracking (v1.3.0+),
        holiday detection (v1.4.0+), and 10 global exchange session flags with trading hour detection (v1.6.0+).

        Supports three operation modes:
        1. Full regeneration (start_date=None, end_date=None): DELETE all + INSERT all [backward compatible]
        2. Incremental append (start_date=YYYY-MM-DD, end_date=None): INSERT OR IGNORE new data only [most common, 95% speedup]
        3. Range update (start_date + end_date): DELETE range + INSERT range [fix specific period]

        Args:
            duckdb_path: Path to DuckDB file
            start_date: Optional start date (YYYY-MM-DD) for filtering tick data.
                       If None, performs full regeneration (backward compatible).
                       If specified, only processes data from this date onward.
            end_date: Optional end date (YYYY-MM-DD) for filtering tick data.
                     Use first day of month for monthly updates (e.g., "2024-10-01").
                     If None with start_date, processes from start_date to present.

        Raises:
            Exception: If OHLC generation or database operations fail

        Example:
            >>> session_detector = SessionDetector()
            >>> generator = OHLCGenerator(session_detector)

            >>> # Mode 1: Full regeneration (backward compatible)
            >>> generator.regenerate_ohlc(Path("~/eon/exness-data/eurusd.duckdb"))

            >>> # Mode 2: Incremental append (add October 2024 onward)
            >>> generator.regenerate_ohlc(
            ...     Path("~/eon/exness-data/eurusd.duckdb"),
            ...     start_date="2024-10-01"
            ... )

            >>> # Mode 3: Range update (reprocess specific month)
            >>> generator.regenerate_ohlc(
            ...     Path("~/eon/exness-data/eurusd.duckdb"),
            ...     start_date="2024-09-01",
            ...     end_date="2024-09-01"
            ... )
        """
        conn = duckdb.connect(str(duckdb_path))

        # Delete existing OHLC data (full regeneration or range-specific)
        if start_date is None and end_date is None:
            # Mode 1: Full regeneration - delete all data
            conn.execute("DELETE FROM ohlc_1m")
        elif start_date is not None and end_date is not None:
            # Mode 3: Range update - delete specific range
            conn.execute(f"""
                DELETE FROM ohlc_1m
                WHERE Timestamp >= '{start_date}'
                AND Timestamp < '{end_date}'::date + INTERVAL '1 month'
            """)
        # Mode 2: Incremental append - no delete needed, INSERT OR IGNORE handles duplicates

        # Generate session column initializations dynamically from exchange registry (v1.6.0)
        session_inits = ",\n                ".join(
            [f"0 as is_{name}_session" for name in EXCHANGES.keys()]
        )

        # Build WHERE clause for date filtering (incremental generation)
        where_clause = ""
        if start_date is not None or end_date is not None:
            conditions = []
            if start_date:
                conditions.append(f"DATE_TRUNC('minute', r.Timestamp) >= '{start_date}'")
            if end_date:
                # Include full end month (end_date is first day of month)
                conditions.append(f"DATE_TRUNC('minute', r.Timestamp) < '{end_date}'::date + INTERVAL '1 month'")
            where_clause = "WHERE " + " AND ".join(conditions)

        # Generate Phase7 OHLC with normalized metrics (NULL-safe calculations)
        insert_sql = f"""
            INSERT OR IGNORE INTO ohlc_1m
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
                END as body_per_tick,
                -- Timezone-aware session columns (v1.3.0) - DuckDB handles DST automatically
                EXTRACT(HOUR FROM (DATE_TRUNC('minute', r.Timestamp) AT TIME ZONE 'America/New_York')) as ny_hour,
                EXTRACT(HOUR FROM (DATE_TRUNC('minute', r.Timestamp) AT TIME ZONE 'Europe/London')) as london_hour,
                CASE
                    WHEN EXTRACT(HOUR FROM (DATE_TRUNC('minute', r.Timestamp) AT TIME ZONE 'America/New_York')) BETWEEN 9 AND 16 THEN 'NY_Session'
                    WHEN EXTRACT(HOUR FROM (DATE_TRUNC('minute', r.Timestamp) AT TIME ZONE 'America/New_York')) BETWEEN 17 AND 20 THEN 'NY_After_Hours'
                    ELSE 'NY_Closed'
                END as ny_session,
                CASE
                    WHEN EXTRACT(HOUR FROM (DATE_TRUNC('minute', r.Timestamp) AT TIME ZONE 'Europe/London')) BETWEEN 8 AND 16 THEN 'London_Session'
                    ELSE 'London_Closed'
                END as london_session,
                -- Holiday columns (v1.4.0) - initialized to 0, then updated dynamically
                0 as is_us_holiday,
                0 as is_uk_holiday,
                0 as is_major_holiday,
                -- Trading session flags (v1.6.0) - initialized to 0, then updated dynamically for {len(EXCHANGES)} exchanges
                {session_inits}
            FROM raw_spread_ticks r
            LEFT JOIN standard_ticks s
                ON DATE_TRUNC('minute', r.Timestamp) = DATE_TRUNC('minute', s.Timestamp)
            {where_clause}
            GROUP BY DATE_TRUNC('minute', r.Timestamp)
            ORDER BY Timestamp
        """
        conn.execute(insert_sql)

        # Dynamic holiday and session detection (v1.6.0) using exchange_calendars
        print(f"  Detecting holidays and sessions for {len(EXCHANGES)} exchanges...")

        # Build WHERE clause for session detection filtering (same as INSERT)
        session_where = ""
        if start_date is not None or end_date is not None:
            conditions = []
            if start_date:
                conditions.append(f"Timestamp >= '{start_date}'")
            if end_date:
                conditions.append(f"Timestamp < '{end_date}'::date + INTERVAL '1 month'")
            session_where = "WHERE " + " AND ".join(conditions)

        # Get timestamps from ohlc_1m (filtered by date range for incremental updates)
        # This enables minute-level session detection (v1.6.0 requirement)
        timestamps_df = conn.execute(f"""
            SELECT Timestamp FROM ohlc_1m {session_where} ORDER BY Timestamp
        """).df()

        if len(timestamps_df) > 0:
            # Prepare DataFrame for session_detector compatibility
            timestamps_df["ts"] = timestamps_df["Timestamp"]
            timestamps_df["date"] = timestamps_df["Timestamp"].dt.date

            # Delegate to session_detector module (checks each minute individually)
            timestamps_df = self.session_detector.detect_sessions_and_holidays(timestamps_df)

            # Calculate session counts for reporting
            session_counts = {
                name: timestamps_df[f"is_{name}_session"].sum() for name in EXCHANGES.keys()
            }

            # Generate dynamic UPDATE query with SET clauses for all exchanges
            session_sets = ",\n                    ".join(
                [f"is_{name}_session = hf.is_{name}_session" for name in EXCHANGES.keys()]
            )

            # Update database with holiday and session flags (exact timestamp match)
            conn.register("holiday_flags", timestamps_df)
            update_sql = f"""
                UPDATE ohlc_1m
                SET
                    is_us_holiday = hf.is_us_holiday,
                    is_uk_holiday = hf.is_uk_holiday,
                    is_major_holiday = hf.is_major_holiday,
                    {session_sets}
                FROM holiday_flags hf
                WHERE ohlc_1m.Timestamp = hf.Timestamp
            """
            conn.execute(update_sql)

            # Report holiday and session counts
            # Count unique dates for holidays (not timestamps, since holidays apply to entire days)
            us_holidays = timestamps_df[timestamps_df["is_us_holiday"] == 1]["date"].nunique()
            uk_holidays = timestamps_df[timestamps_df["is_uk_holiday"] == 1]["date"].nunique()
            major_holidays = timestamps_df[timestamps_df["is_major_holiday"] == 1]["date"].nunique()
            print(f"  ✓ Holidays: {us_holidays} US, {uk_holidays} UK, {major_holidays} major")

            # Report session counts for all exchanges (counts trading minutes, not days)
            session_summary = ", ".join(
                [f"{name.upper()}: {count}" for name, count in session_counts.items()]
            )
            print(f"  ✓ Trading minutes: {session_summary}")

        conn.close()
