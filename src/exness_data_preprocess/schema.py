"""
Database schema definitions - Single source of truth for all table structures.

This module centralizes all database schema definitions, eliminating duplication
and making future schema changes require updates in only one place.

Adding new OHLC columns (example):
1. Add entry to OHLCSchema.COLUMNS dict (column name, type, comment, aggregation)
2. Update _regenerate_ohlc() if column requires special calculation from ticks
3. Regenerate databases: processor.update_data(pair) handles schema migration
4. Done! All queries, comments, and tests automatically updated.

Architecture Benefits:
- DRY: Column definitions in one place (not duplicated across 9 files)
- Type-safe: Python dataclasses with clear structure
- Self-documenting: Comments embedded with column definitions
- Dynamic SQL: Queries generated programmatically
- Test-friendly: Tests validate structure, not magic numbers
"""

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class ColumnDefinition:
    """
    Definition for a single database column.

    Attributes:
        dtype: SQL data type (e.g., "DOUBLE", "BIGINT", "TIMESTAMP WITH TIME ZONE PRIMARY KEY")
        comment: Human-readable description for COMMENT ON COLUMN statement
        aggregation: SQL expression for resampling (e.g., "AVG(column_name)")
                     None for non-aggregated columns like Timestamp
    """

    dtype: str
    comment: str
    aggregation: Optional[str] = None


class OHLCSchema:
    """
    Phase7 OHLC schema v1.2.0 - Centralized definition for ohlc_1m table.

    This class provides a single source of truth for the OHLC schema, including:
    - Column names, types, and constraints
    - Column documentation (COMMENT ON statements)
    - Resampling aggregation logic

    Schema Version History:
        v1.1.0: 9 columns (Timestamp, OHLC, dual spreads, dual tick counts)
        v1.2.0: 13 columns (added 4 normalized spread metrics)

    Usage:
        >>> # Generate CREATE TABLE statement
        >>> sql = OHLCSchema.get_create_table_sql()
        >>> conn.execute(sql)
        >>>
        >>> # Add column comments
        >>> for comment_sql in OHLCSchema.get_column_comment_sqls():
        ...     conn.execute(comment_sql)
        >>>
        >>> # Generate resampling query
        >>> time_expr = "DATE_TRUNC('hour', Timestamp)"
        >>> select = OHLCSchema.get_resampling_select_clause(time_expr)
        >>> conn.execute(f"SELECT {select} FROM ohlc_1m GROUP BY {time_expr}")
    """

    VERSION = "1.2.0"

    # Single source of truth: Column definitions (update here, propagates everywhere)
    COLUMNS: Dict[str, ColumnDefinition] = {
        "Timestamp": ColumnDefinition(
            dtype="TIMESTAMP WITH TIME ZONE PRIMARY KEY",
            comment="Minute-aligned bar timestamp",
            aggregation=None,  # GROUP BY column, not aggregated
        ),
        "Open": ColumnDefinition(
            dtype="DOUBLE NOT NULL",
            comment="Opening price (first Raw_Spread Bid)",
            aggregation="FIRST(Open ORDER BY Timestamp)",
        ),
        "High": ColumnDefinition(
            dtype="DOUBLE NOT NULL",
            comment="High price (max Raw_Spread Bid)",
            aggregation="MAX(High)",
        ),
        "Low": ColumnDefinition(
            dtype="DOUBLE NOT NULL",
            comment="Low price (min Raw_Spread Bid)",
            aggregation="MIN(Low)",
        ),
        "Close": ColumnDefinition(
            dtype="DOUBLE NOT NULL",
            comment="Closing price (last Raw_Spread Bid)",
            aggregation="LAST(Close ORDER BY Timestamp)",
        ),
        "raw_spread_avg": ColumnDefinition(
            dtype="DOUBLE",
            comment="Average spread from Raw_Spread variant (NULL if no ticks)",
            aggregation="AVG(raw_spread_avg)",
        ),
        "standard_spread_avg": ColumnDefinition(
            dtype="DOUBLE",
            comment="Average spread from Standard variant (NULL if no Standard ticks for that minute)",
            aggregation="AVG(standard_spread_avg)",
        ),
        "tick_count_raw_spread": ColumnDefinition(
            dtype="BIGINT",
            comment="Number of ticks from Raw_Spread variant (NULL if no ticks)",
            aggregation="SUM(tick_count_raw_spread)",
        ),
        "tick_count_standard": ColumnDefinition(
            dtype="BIGINT",
            comment="Number of ticks from Standard variant (NULL if no Standard ticks for that minute)",
            aggregation="SUM(tick_count_standard)",
        ),
        # NEW COLUMNS (v1.2.0): Normalized spread metrics
        "range_per_spread": ColumnDefinition(
            dtype="DOUBLE",
            comment="(High-Low)/standard_spread_avg - Range normalized by spread (NULL if no Standard ticks)",
            aggregation="AVG(range_per_spread)",
        ),
        "range_per_tick": ColumnDefinition(
            dtype="DOUBLE",
            comment="(High-Low)/tick_count_standard - Range normalized by tick count (NULL if no Standard ticks)",
            aggregation="AVG(range_per_tick)",
        ),
        "body_per_spread": ColumnDefinition(
            dtype="DOUBLE",
            comment="abs(Close-Open)/standard_spread_avg - Body normalized by spread (NULL if no Standard ticks)",
            aggregation="AVG(body_per_spread)",
        ),
        "body_per_tick": ColumnDefinition(
            dtype="DOUBLE",
            comment="abs(Close-Open)/tick_count_standard - Body normalized by tick count (NULL if no Standard ticks)",
            aggregation="AVG(body_per_tick)",
        ),
    }

    # Table-level comment
    TABLE_COMMENT = (
        f"Phase7 v{VERSION} 1-minute OHLC bars (BID-only from Raw_Spread, "
        "dual-variant spreads and tick counts, normalized metrics). "
        "OHLC Source: Raw_Spread BID prices. Spreads: Dual-variant (Raw_Spread + Standard)."
    )

    @classmethod
    def get_create_table_sql(cls) -> str:
        """
        Generate CREATE TABLE statement from column definitions.

        Returns:
            SQL statement to create ohlc_1m table with all columns

        Example:
            >>> sql = OHLCSchema.get_create_table_sql()
            >>> print(sql)
            CREATE TABLE IF NOT EXISTS ohlc_1m (
                Timestamp TIMESTAMP WITH TIME ZONE PRIMARY KEY,
                Open DOUBLE NOT NULL,
                ...
            )
        """
        col_defs = [f"{name} {col.dtype}" for name, col in cls.COLUMNS.items()]
        return f"CREATE TABLE IF NOT EXISTS ohlc_1m (\n    {',\n    '.join(col_defs)}\n)"

    @classmethod
    def get_table_comment_sql(cls) -> str:
        """
        Generate COMMENT ON TABLE statement.

        Returns:
            SQL statement to add table-level comment

        Example:
            >>> sql = OHLCSchema.get_table_comment_sql()
            >>> print(sql)
            COMMENT ON TABLE ohlc_1m IS 'Phase7 v1.2.0 1-minute OHLC bars...'
        """
        return f"COMMENT ON TABLE ohlc_1m IS '{cls.TABLE_COMMENT}'"

    @classmethod
    def get_column_comment_sqls(cls) -> list[str]:
        """
        Generate all COMMENT ON COLUMN statements.

        Returns:
            List of SQL statements to add column comments

        Example:
            >>> sqls = OHLCSchema.get_column_comment_sqls()
            >>> len(sqls)
            13
            >>> print(sqls[0])
            COMMENT ON COLUMN ohlc_1m.Timestamp IS 'Minute-aligned bar timestamp'
        """
        return [
            f"COMMENT ON COLUMN ohlc_1m.{name} IS '{col.comment}'"
            for name, col in cls.COLUMNS.items()
        ]

    @classmethod
    def get_resampling_select_clause(cls, time_expr: str) -> str:
        """
        Generate SELECT clause for resampling queries.

        This method creates the column aggregations needed for resampling 1m OHLC
        data to higher timeframes (5m, 1h, 1d, etc.). All 13 columns are automatically
        included with their correct aggregation functions.

        Args:
            time_expr: Time bucket expression for grouping
                      Examples: "DATE_TRUNC('hour', Timestamp)"
                               "TIME_BUCKET(INTERVAL '5 minutes', Timestamp)"

        Returns:
            Complete SELECT clause with all column aggregations

        Example:
            >>> time_expr = "DATE_TRUNC('hour', Timestamp)"
            >>> select_clause = OHLCSchema.get_resampling_select_clause(time_expr)
            >>> print(select_clause)
            DATE_TRUNC('hour', Timestamp) as Timestamp,
            FIRST(Open ORDER BY Timestamp) as Open,
            MAX(High) as High,
            ...
            AVG(body_per_tick) as body_per_tick
        """
        selects = [f"{time_expr} as Timestamp"]

        for name, col in cls.COLUMNS.items():
            if name != "Timestamp" and col.aggregation:
                selects.append(f"{col.aggregation} as {name}")

        return ",\n            ".join(selects)

    @classmethod
    def get_required_columns(cls) -> list[str]:
        """
        Get list of required column names for test validation.

        Returns:
            List of all column names in schema

        Example:
            >>> cols = OHLCSchema.get_required_columns()
            >>> len(cols)
            13
            >>> 'Timestamp' in cols
            True
            >>> 'range_per_spread' in cols
            True
        """
        return list(cls.COLUMNS.keys())
