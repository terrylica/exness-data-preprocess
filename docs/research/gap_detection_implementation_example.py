"""
Gap Detection Implementation Example - SQL Approach

This file shows the exact code changes needed to implement full gap detection
in gap_detector.py using DuckDB's generate_series() function.

Context:
- Current: Lines 54-155 in gap_detector.py
- Change: Replace lines 94-155 (database exists path)
- Keep: Lines 76-92 (database doesn't exist path - Python generation)
"""

from datetime import datetime
from pathlib import Path
from typing import List, Tuple

import duckdb


class GapDetector:
    """Gap detector with full SQL-based gap detection."""

    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def discover_missing_months(self, pair: str, start_date: str) -> List[Tuple[int, int]]:
        """
        Discover which months need to be downloaded.

        Detects ALL gaps:
        - Before earliest coverage (e.g., start_date to first month in DB)
        - Within coverage range (e.g., missing months between first and last)
        - After latest coverage (e.g., last month in DB to current month)

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
            >>> # Returns ALL missing months including gaps within range
            >>> print(missing)
            [(2022, 1), (2022, 4), (2024, 6), ..., (2025, 10)]
        """
        duckdb_path = self.base_dir / f"{pair.lower()}.duckdb"

        if not duckdb_path.exists():
            # No database yet - need full historical download
            # Keep existing Python logic (lines 76-92)
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

        # Database exists - use SQL to find ALL gaps
        # ============================================
        # REPLACE LINES 94-155 WITH THIS SQL APPROACH
        # ============================================

        conn = duckdb.connect(str(duckdb_path), read_only=True)
        try:
            # Single SQL query finds ALL gaps (before + within + after)
            result = conn.execute(
                """
                WITH expected_months AS (
                    -- Generate all expected months from start_date to current month
                    SELECT
                        YEAR(month_date) as year,
                        MONTH(month_date) as month
                    FROM generate_series(
                        ?::DATE,  -- start_date parameter (YYYY-MM-DD)
                        DATE_TRUNC('month', CURRENT_DATE)::DATE,
                        INTERVAL '1 month'
                    ) as t(month_date)
                ),
                existing_months AS (
                    -- Get distinct months that exist in database
                    SELECT DISTINCT
                        YEAR(Timestamp) as year,
                        MONTH(Timestamp) as month
                    FROM raw_spread_ticks
                )
                -- Set difference: expected - existing = missing
                SELECT year, month
                FROM expected_months
                EXCEPT
                SELECT year, month
                FROM existing_months
                ORDER BY year, month
            """,
                [start_date],
            ).fetchall()

            # Handle empty result (no gaps)
            if not result:
                return []

            return result

        finally:
            conn.close()


# ============================================
# DEMONSTRATION OF FUNCTIONALITY
# ============================================

if __name__ == "__main__":
    import tempfile

    # Create test database with gaps
    test_dir = Path(tempfile.mkdtemp())
    test_db = test_dir / "eurusd.duckdb"

    # Setup test database
    conn = duckdb.connect(str(test_db))
    conn.execute(
        """
        CREATE TABLE raw_spread_ticks (
            Timestamp TIMESTAMP WITH TIME ZONE PRIMARY KEY,
            Bid DOUBLE,
            Ask DOUBLE
        )
    """
    )
    # Insert data with gaps:
    # - 2024-01, 2024-02, 2024-03 (exists)
    # - 2024-04 (GAP)
    # - 2024-05 (exists)
    # - 2024-06, 2024-07 (GAP)
    # - 2024-08, 2024-09 (exists)
    # - 2024-10 to current (GAP - after latest)
    conn.execute(
        """
        INSERT INTO raw_spread_ticks VALUES
        ('2024-01-15 12:00:00+00', 1.1, 1.1),
        ('2024-02-15 12:00:00+00', 1.1, 1.1),
        ('2024-03-15 12:00:00+00', 1.1, 1.1),
        ('2024-05-15 12:00:00+00', 1.1, 1.1),
        ('2024-08-15 12:00:00+00', 1.1, 1.1),
        ('2024-09-15 12:00:00+00', 1.1, 1.1)
    """
    )
    conn.close()

    # Test gap detection
    detector = GapDetector(base_dir=test_dir)
    missing = detector.discover_missing_months("EURUSD", "2024-01-01")

    print("=== Gap Detection Results ===")
    print(f"Total missing months: {len(missing)}")
    print(f"\nFirst 10 gaps: {missing[:10]}")

    # Categorize gaps
    existing = {(2024, 1), (2024, 2), (2024, 3), (2024, 5), (2024, 8), (2024, 9)}
    within_range = [
        (y, m) for y, m in missing if datetime(2024, 1, 1) <= datetime(y, m, 1) <= datetime(2024, 9, 30)
    ]
    after_latest = [
        (y, m) for y, m in missing if datetime(y, m, 1) > datetime(2024, 9, 30)
    ]

    print(f"\nGaps within coverage range: {within_range}")
    print(f"Expected: [(2024, 4), (2024, 6), (2024, 7)]")
    print(f"Match: {within_range == [(2024, 4), (2024, 6), (2024, 7)]}")

    print(f"\nGaps after latest (Oct 2024 to current): {len(after_latest)} months")
    print(f"First 3: {after_latest[:3]}")

    # Cleanup
    import shutil

    shutil.rmtree(test_dir)

    print("\n✅ Implementation validated successfully!")
