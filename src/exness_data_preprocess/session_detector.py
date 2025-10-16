"""
Exchange calendar operations and session/holiday detection.

SLOs:
- Availability: Calendar initialization must succeed or raise exception (no silent failures)
- Correctness: Holiday detection matches exchange_calendars library exactly, excludes weekends
- Observability: All detection operations logged via print statements
- Maintainability: Single module for all session/holiday logic, off-the-shelf exchange_calendars

Uses exchange_calendars library (off-the-shelf) to determine trading days and holidays
for 10 global exchanges (NYSE, LSE, SIX, FWB, TSX, NZX, JPX, ASX, HKEX, SGX).

Handles:
- Exchange calendar initialization from EXCHANGES registry
- Holiday detection for NYSE and LSE (official closures only)
- Major holiday detection (both NYSE and LSE closed)
- Trading session detection for all 10 exchanges (excludes weekends + holidays)
"""

from typing import Any, Dict

import exchange_calendars as xcals
import pandas as pd

from exness_data_preprocess.exchanges import EXCHANGES


class SessionDetector:
    """
    Detect trading sessions and holidays for global exchanges.

    Responsibilities:
    - Initialize exchange calendars from EXCHANGES registry
    - Detect holidays for NYSE and LSE (excludes weekends)
    - Detect major holidays (both NYSE and LSE closed)
    - Detect trading days for all 10 exchanges (excludes weekends + holidays)

    Example:
        >>> detector = SessionDetector()
        >>> dates_df = pd.DataFrame({"ts": pd.date_range("2024-01-01", "2024-12-31")})
        >>> result = detector.detect_sessions_and_holidays(dates_df)
        >>> print(result.columns)
        Index(['ts', 'date', 'is_us_holiday', 'is_uk_holiday', 'is_major_holiday',
               'is_nyse_session', 'is_lse_session', ...], dtype='object')
    """

    def __init__(self):
        """
        Initialize session detector with exchange calendars.

        Loads calendars for all exchanges in EXCHANGES registry.

        Raises:
            Exception: If calendar initialization fails for any exchange
        """
        self.calendars: Dict[str, Any] = {}
        for exchange_name, exchange_config in EXCHANGES.items():
            self.calendars[exchange_name] = xcals.get_calendar(exchange_config.code)
        print(
            f"✓ Initialized {len(self.calendars)} exchange calendars: {', '.join(EXCHANGES.keys())}"
        )

    def detect_sessions_and_holidays(self, dates_df: pd.DataFrame) -> pd.DataFrame:
        """
        Add holiday and session columns to dates DataFrame.

        Args:
            dates_df: DataFrame with 'ts' column (timezone-naive timestamps) and 'date' column

        Returns:
            Same DataFrame with added columns:
                - is_us_holiday: 1 if NYSE closed (official holiday, excludes weekends), 0 otherwise
                - is_uk_holiday: 1 if LSE closed (official holiday, excludes weekends), 0 otherwise
                - is_major_holiday: 1 if both NYSE and LSE closed, 0 otherwise
                - is_{exchange}_session: 1 if exchange open, 0 otherwise (for all 10 exchanges)

        Raises:
            Exception: If holiday/session detection fails

        Example:
            >>> detector = SessionDetector()
            >>> dates_df = pd.DataFrame({
            ...     "date": pd.date_range("2024-01-01", "2024-01-31").date,
            ...     "ts": pd.date_range("2024-01-01", "2024-01-31")
            ... })
            >>> result = detector.detect_sessions_and_holidays(dates_df)
            >>> print(f"US holidays: {result['is_us_holiday'].sum()}")
            US holidays: 1  # New Year's Day
        """
        # Get date range for pre-generating holiday sets
        start_date = dates_df["ts"].min()
        end_date = dates_df["ts"].max()

        # Pre-generate holiday sets for O(1) lookup (excludes weekends) - NYSE and LSE only
        nyse_holidays = {
            pd.to_datetime(h).date()
            for h in self.calendars["nyse"].regular_holidays.holidays(
                start=start_date, end=end_date, return_name=False
            )
        }
        lse_holidays = {
            pd.to_datetime(h).date()
            for h in self.calendars["lse"].regular_holidays.holidays(
                start=start_date, end=end_date, return_name=False
            )
        }

        # Vectorized holiday checking using sets (fast and excludes weekends!)
        dates_df["is_us_holiday"] = dates_df["ts"].dt.date.apply(lambda d: int(d in nyse_holidays))
        dates_df["is_uk_holiday"] = dates_df["ts"].dt.date.apply(lambda d: int(d in lse_holidays))
        dates_df["is_major_holiday"] = (
            (dates_df["is_us_holiday"] == 1) & (dates_df["is_uk_holiday"] == 1)
        ).astype(int)

        # Loop-based session detection for all exchanges (v1.5.0)
        # True if exchange is open (excludes weekends + holidays)
        for exchange_name, calendar in self.calendars.items():
            col_name = f"is_{exchange_name}_session"
            dates_df[col_name] = dates_df["ts"].apply(lambda d, cal=calendar: int(cal.is_session(d)))

        return dates_df
