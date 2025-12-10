"""
Gap detection for incremental ClickHouse updates.

ADR: /docs/adr/2025-12-09-exness-clickhouse-migration.md

SLOs:
- Availability: Gap detection must succeed or raise exception (no silent failures)
- Correctness: Detects all missing months from start_date to current month via SQL EXCEPT
- Observability: All gap detection operations logged via structured logging
- Maintainability: Single module for all gap detection logic, off-the-shelf ClickHouse

Handles:
- New database initialization (no existing data)
- Empty table detection (tables exist but no ticks)
- Gap detection before earliest and after latest coverage
- Month enumeration from start_date to current month
"""

from datetime import datetime

from clickhouse_connect.driver import Client

from exness_data_preprocess.clickhouse_base import ClickHouseClientMixin
from exness_data_preprocess.clickhouse_client import (
    execute_query,
)


class ClickHouseGapDetector(ClickHouseClientMixin):
    """
    Detect missing months for incremental ClickHouse updates.

    Responsibilities:
    - Check if table has data for an instrument
    - Find gaps before earliest coverage
    - Find gaps after latest coverage
    - Enumerate all months from start_date to current month for new instruments

    Example:
        >>> detector = ClickHouseGapDetector()
        >>> missing = detector.discover_missing_months("EURUSD", "2022-01-01")
        >>> print(f"Need to download {len(missing)} months")
    """

    DATABASE = "exness"
    TABLE = "raw_spread_ticks"

    def __init__(self, client: Client | None = None):
        """
        Initialize gap detector.

        Args:
            client: Optional ClickHouse client (creates one if not provided)
        """
        self._init_client(client)

    def discover_missing_months(
        self, instrument: str, start_date: str
    ) -> list[tuple[int, int]]:
        """
        Discover which months need to be downloaded.

        Detects ALL missing months (before earliest + within range + after latest)
        using SQL EXCEPT operator with ClickHouse arrayJoin.

        Args:
            instrument: Instrument symbol (e.g., "EURUSD")
            start_date: Earliest date to consider (YYYY-MM-DD)

        Returns:
            List of (year, month) tuples to download, sorted chronologically

        Raises:
            ClickHouseQueryError: If query execution fails

        Intent:
            Uses SQL set difference (expected - existing = missing) to detect gaps.
            ClickHouse's arrayJoin generates expected months range.

        Example:
            >>> detector = ClickHouseGapDetector()
            >>> missing = detector.discover_missing_months("EURUSD", "2022-01-01")
            >>> print(missing)
            [(2022, 1), (2022, 2), ..., (2025, 10)]
        """
        instrument = instrument.upper()

        # First check if there's any data for this instrument
        has_data = self._has_data(instrument)

        if not has_data:
            # No data yet - need full historical download
            return self._enumerate_months(start_date)

        # Query existing coverage using SQL EXCEPT for complete gap detection
        # Detects ALL gaps: before earliest + within range + after latest
        query = """
            WITH
                toDate({start_date:String}) AS start,
                toStartOfMonth(today()) AS end_month,
                -- Generate expected months using arrayJoin
                expected_months AS (
                    SELECT
                        toYear(month_date) AS year,
                        toMonth(month_date) AS month
                    FROM (
                        SELECT arrayJoin(
                            arrayMap(
                                i -> addMonths(toStartOfMonth(start), i),
                                range(0, toUInt32(dateDiff('month', toStartOfMonth(start), end_month)) + 1)
                            )
                        ) AS month_date
                    )
                ),
                existing_months AS (
                    SELECT DISTINCT
                        toYear(timestamp) AS year,
                        toMonth(timestamp) AS month
                    FROM {database:Identifier}.{table:Identifier}
                    WHERE instrument = {instrument:String}
                )
            SELECT year, month
            FROM expected_months
            WHERE (year, month) NOT IN (
                SELECT year, month FROM existing_months
            )
            ORDER BY year, month
        """

        result = execute_query(
            self.client,
            query,
            parameters={
                "start_date": start_date,
                "database": self.DATABASE,
                "table": self.TABLE,
                "instrument": instrument,
            },
        )

        return [(row[0], row[1]) for row in result.result_rows]

    def _has_data(self, instrument: str) -> bool:
        """
        Check if there's any data for an instrument.

        Args:
            instrument: Instrument symbol (e.g., "EURUSD")

        Returns:
            True if data exists, False otherwise
        """
        query = """
            SELECT count() > 0
            FROM {database:Identifier}.{table:Identifier}
            WHERE instrument = {instrument:String}
            LIMIT 1
        """

        result = execute_query(
            self.client,
            query,
            parameters={
                "database": self.DATABASE,
                "table": self.TABLE,
                "instrument": instrument,
            },
        )

        return result.first_row[0] if result.result_rows else False

    def _enumerate_months(self, start_date: str) -> list[tuple[int, int]]:
        """
        Enumerate all months from start_date to current month.

        Args:
            start_date: Start date (YYYY-MM-DD)

        Returns:
            List of (year, month) tuples
        """
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

    def get_coverage_range(
        self, instrument: str
    ) -> tuple[datetime | None, datetime | None]:
        """
        Get the earliest and latest timestamps for an instrument.

        Args:
            instrument: Instrument symbol (e.g., "EURUSD")

        Returns:
            Tuple of (earliest_timestamp, latest_timestamp), or (None, None) if no data
        """
        query = """
            SELECT
                min(timestamp) AS earliest,
                max(timestamp) AS latest
            FROM {database:Identifier}.{table:Identifier}
            WHERE instrument = {instrument:String}
        """

        result = execute_query(
            self.client,
            query,
            parameters={
                "database": self.DATABASE,
                "table": self.TABLE,
                "instrument": instrument.upper(),
            },
        )

        if not result.result_rows or result.first_row[0] is None:
            return None, None

        return result.first_row[0], result.first_row[1]
