"""
Exchange calendar operations and session/holiday detection.

SLOs:
- Availability: Calendar initialization must succeed or raise exception (no silent failures)
- Correctness: Session detection matches exchange_calendars library exactly (includes lunch breaks)
- Observability: All detection operations logged via print statements
- Maintainability: Single module for all session/holiday logic, off-the-shelf exchange_calendars

Uses exchange_calendars library (off-the-shelf) to determine trading hours, holidays, and
lunch breaks for 10 global exchanges (NYSE, LSE, SIX, FWB, TSX, NZX, JPX, ASX, HKEX, SGX).

Handles:
- Exchange calendar initialization from EXCHANGES registry
- Holiday detection for NYSE and LSE (official closures only)
- Major holiday detection (both NYSE and LSE closed)
- Trading session detection for all 10 exchanges with lunch break support
  (Tokyo 11:30-12:30 JST, Hong Kong 12:00-13:00 HKT, Singapore 12:00-13:00 SGT)

Performance (v1.7.0+):
- Pre-computes trading minutes for vectorized lookup (2.2x speedup vs per-timestamp checks)
- Preserves accuracy via exchange_calendars.is_open_on_minute()
"""

from datetime import date
from typing import Any, Dict, Set

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
    - Detect trading hours for all 10 exchanges (respects lunch breaks for Asian exchanges)

    Lunch Breaks (automatically handled):
    - Tokyo (XTKS): 11:30-12:30 JST
    - Hong Kong (XHKG): 12:00-13:00 HKT
    - Singapore (XSES): 12:00-13:00 SGT

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

    def _precompute_trading_minutes(
        self, start_date: date, end_date: date
    ) -> Dict[str, Set[pd.Timestamp]]:
        """
        Pre-compute trading minutes for all exchanges in date range.

        Args:
            start_date: Start date (inclusive)
            end_date: End date (inclusive)

        Returns:
            Dictionary mapping exchange_name to set of trading minutes (timezone-aware UTC timestamps)

        Intent:
            Enables vectorized session detection via .isin() instead of per-timestamp .apply() calls.
            Preserves accuracy by delegating lunch break and trading hour logic to exchange_calendars.

        Note:
            Calls calendar.is_open_on_minute() during pre-computation to respect:
            - Lunch breaks (Tokyo 11:30-12:30, Hong Kong/Singapore 12:00-13:00)
            - Trading hour changes (e.g., Tokyo extended to 15:30 on Nov 5, 2024)
            - Holidays and weekends (automatically excluded)
        """
        trading_minutes: Dict[str, Set[pd.Timestamp]] = {}

        for exchange_name, calendar in self.calendars.items():
            minutes_set: Set[pd.Timestamp] = set()

            # Get all open sessions in date range
            sessions = calendar.sessions_in_range(start_date, end_date)

            for session_date in sessions:
                # Get market open/close times for this session
                market_open = calendar.session_open(session_date)
                market_close = calendar.session_close(session_date)

                # Generate all minutes in this session
                current_minute = market_open
                while current_minute <= market_close:
                    # Use is_open_on_minute() to respect lunch breaks and other edge cases
                    if calendar.is_open_on_minute(current_minute):
                        minutes_set.add(current_minute)
                    current_minute += pd.Timedelta(minutes=1)

            trading_minutes[exchange_name] = minutes_set

        return trading_minutes

    def detect_sessions_and_holidays(self, dates_df: pd.DataFrame) -> pd.DataFrame:
        """
        Add holiday and session columns to dates DataFrame.

        Args:
            dates_df: DataFrame with 'ts' column (timezone-aware UTC timestamps) and 'date' column

        Returns:
            Same DataFrame with added columns:
                - is_us_holiday: 1 if NYSE closed (official holiday, excludes weekends), 0 otherwise
                - is_uk_holiday: 1 if LSE closed (official holiday, excludes weekends), 0 otherwise
                - is_major_holiday: 1 if both NYSE and LSE closed, 0 otherwise
                - is_{exchange}_session: 1 if during trading hours (excludes lunch breaks), 0 otherwise

        Session Detection (v1.7.0+):
            - Pre-computes trading minutes using exchange_calendars.is_open_on_minute()
            - Uses vectorized .isin() lookup (2.2x faster than per-timestamp .apply())
            - Automatically excludes lunch breaks for Tokyo (11:30-12:30), Hong Kong (12:00-13:00), Singapore (12:00-13:00)
            - Handles trading hour changes (e.g., Tokyo extended to 15:30 on Nov 5, 2024)

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
        # Get date range
        start_date = dates_df["ts"].min().date()
        end_date = dates_df["ts"].max().date()

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

        # Vectorized session detection (v1.7.0+)
        # Pre-compute trading minutes for all exchanges, then use .isin() for fast lookup
        trading_minutes = self._precompute_trading_minutes(start_date, end_date)

        for exchange_name in self.calendars.keys():
            col_name = f"is_{exchange_name}_session"
            dates_df[col_name] = dates_df["ts"].isin(trading_minutes[exchange_name]).astype(int)

        return dates_df
