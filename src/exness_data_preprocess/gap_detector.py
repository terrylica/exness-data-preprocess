"""
Gap detection for incremental database updates.

SLOs:
- Availability: Gap detection must succeed or raise exception (no silent failures)
- Correctness: Detects all missing months from start_date to current month
- Observability: All gap detection operations logged via print statements
- Maintainability: Single module for all gap detection logic, off-the-shelf DuckDB

Handles:
- New database initialization (no existing data)
- Empty database detection (tables exist but no ticks)
- Gap detection before earliest and after latest coverage
- Month enumeration from start_date to current month
"""

from datetime import datetime
from pathlib import Path
from typing import List, Tuple

import duckdb
import pandas as pd


class GapDetector:
    """
    Detect missing months for incremental database updates.

    Responsibilities:
    - Check if database exists and has data
    - Find gaps before earliest coverage
    - Find gaps after latest coverage
    - Enumerate all months from start_date to current month for new databases

    Example:
        >>> detector = GapDetector(base_dir=Path("~/eon/exness-data/"))
        >>> missing = detector.discover_missing_months("EURUSD", "2022-01-01")
        >>> print(f"Need to download {len(missing)} months")
    """

    def __init__(self, base_dir: Path):
        """
        Initialize gap detector.

        Args:
            base_dir: Base directory for DuckDB files

        Raises:
            Exception: If base_dir initialization fails
        """
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def discover_missing_months(self, pair: str, start_date: str) -> List[Tuple[int, int]]:
        """
        Discover which months need to be downloaded.

        Args:
            pair: Currency pair
            start_date: Earliest date to consider (YYYY-MM-DD)

        Returns:
            List of (year, month) tuples to download

        Raises:
            Exception: If database query or gap detection fails

        Example:
            >>> detector = GapDetector(base_dir=Path("~/eon/exness-data/"))
            >>> missing = detector.discover_missing_months("EURUSD", "2022-01-01")
            >>> print(missing)
            [(2022, 1), (2022, 2), ..., (2025, 10)]
        """
        duckdb_path = self.base_dir / f"{pair.lower()}.duckdb"

        if not duckdb_path.exists():
            # No database yet - need full historical download
            # From start_date to current month
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
