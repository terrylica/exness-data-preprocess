"""
Database schema management, connections, and tick insertion.

SLOs:
- Availability: Database creation must succeed or raise exception (no silent failures)
- Correctness: PRIMARY KEY constraints prevent duplicates, schema matches v1.5.0 exactly
- Observability: All database operations use DuckDB native logging
- Maintainability: Single module for all database operations, off-the-shelf DuckDB

Handles:
- Database file creation and connection
- Schema initialization with PRIMARY KEY constraints
- Self-documenting COMMENT ON statements
- Tick data insertion with duplicate prevention
- Phase7 30-column OHLC schema (v1.5.0)
"""

from pathlib import Path

import duckdb
import pandas as pd

from exness_data_preprocess.schema import OHLCSchema


class DatabaseManager:
    """
    Manage DuckDB database schema and connections.

    Responsibilities:
    - Create database files with proper schema
    - Add self-documenting COMMENT statements
    - Insert tick data with duplicate prevention
    - Ensure Phase7 30-column OHLC schema (v1.5.0)

    Example:
        >>> db_manager = DatabaseManager(base_dir=Path("~/eon/exness-data/"))
        >>> duckdb_path = db_manager.get_or_create_db("EURUSD")
        >>> # Insert ticks with duplicate prevention
        >>> rows_added = db_manager.append_ticks(duckdb_path, df_ticks, "raw_spread_ticks")
    """

    def __init__(self, base_dir: Path):
        """
        Initialize database manager.

        Args:
            base_dir: Base directory for DuckDB files
        """
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def get_or_create_db(self, pair: str) -> Path:
        """
        Get DuckDB path and ensure schema exists.

        Creates tables if they don't exist:
        - raw_spread_ticks (PRIMARY KEY on Timestamp)
        - standard_ticks (PRIMARY KEY on Timestamp)
        - ohlc_1m (Phase7 30-column schema v1.5.0)
        - metadata (coverage tracking)

        All tables include self-documenting COMMENT statements.

        Args:
            pair: Currency pair (e.g., "EURUSD")

        Returns:
            Path to DuckDB file

        Raises:
            Exception: If database creation or schema initialization fails

        Example:
            >>> db_manager = DatabaseManager(base_dir=Path("~/eon/exness-data/"))
            >>> duckdb_path = db_manager.get_or_create_db("EURUSD")
            >>> print(f"Database: {duckdb_path}")
            Database: /Users/user/eon/exness-data/eurusd.duckdb
        """
        duckdb_path = self.base_dir / f"{pair.lower()}.duckdb"
        conn = duckdb.connect(str(duckdb_path))

        # Create raw_spread_ticks table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS raw_spread_ticks (
                Timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
                Bid DOUBLE NOT NULL,
                Ask DOUBLE NOT NULL,
                PRIMARY KEY (Timestamp)
            )
        """)

        # Add table and column comments for raw_spread_ticks
        conn.execute("""
            COMMENT ON TABLE raw_spread_ticks IS
            'Exness Raw_Spread variant (execution prices, ~98% zero-spreads).
             Data source: https://ticks.ex2archive.com/ticks/{SYMBOL}_Raw_Spread/{YEAR}/{MONTH}/'
        """)
        conn.execute(
            "COMMENT ON COLUMN raw_spread_ticks.Timestamp IS 'Microsecond-precision tick timestamp (UTC)'"
        )
        conn.execute("COMMENT ON COLUMN raw_spread_ticks.Bid IS 'Bid price (execution price)'")
        conn.execute("COMMENT ON COLUMN raw_spread_ticks.Ask IS 'Ask price (execution price)'")

        # Create standard_ticks table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS standard_ticks (
                Timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
                Bid DOUBLE NOT NULL,
                Ask DOUBLE NOT NULL,
                PRIMARY KEY (Timestamp)
            )
        """)

        # Add table and column comments for standard_ticks
        conn.execute("""
            COMMENT ON TABLE standard_ticks IS
            'Exness Standard variant (traditional quotes, 0% zero-spreads, always Bid < Ask).
             Data source: https://ticks.ex2archive.com/ticks/{SYMBOL}/{YEAR}/{MONTH}/'
        """)
        conn.execute(
            "COMMENT ON COLUMN standard_ticks.Timestamp IS 'Microsecond-precision tick timestamp (UTC)'"
        )
        conn.execute("COMMENT ON COLUMN standard_ticks.Bid IS 'Bid price (always < Ask)'")
        conn.execute("COMMENT ON COLUMN standard_ticks.Ask IS 'Ask price (always > Bid)'")

        # Create metadata table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS metadata (
                key VARCHAR PRIMARY KEY,
                value VARCHAR NOT NULL,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
        """)

        # Add table and column comments for metadata
        conn.execute("""
            COMMENT ON TABLE metadata IS
            'Database coverage tracking and statistics (earliest/latest dates, tick counts, etc.)'
        """)
        conn.execute(
            "COMMENT ON COLUMN metadata.key IS 'Metadata key identifier (e.g., earliest_date, latest_date)'"
        )
        conn.execute("COMMENT ON COLUMN metadata.value IS 'Metadata value (string representation)'")
        conn.execute("COMMENT ON COLUMN metadata.updated_at IS 'Last update timestamp'")

        # Create ohlc_1m table using schema definition (includes 13 columns in v1.2.0)
        conn.execute(OHLCSchema.get_create_table_sql())

        # Add table and column comments
        conn.execute(OHLCSchema.get_table_comment_sql())
        for comment_sql in OHLCSchema.get_column_comment_sqls():
            conn.execute(comment_sql)

        # Commit all schema changes before closing
        conn.commit()
        conn.close()
        return duckdb_path

    def append_ticks(self, duckdb_path: Path, df: pd.DataFrame, table_name: str) -> int:
        """
        Append ticks to DuckDB table.

        PRIMARY KEY constraint automatically prevents duplicates.

        Args:
            duckdb_path: Path to DuckDB file
            df: DataFrame with tick data (Timestamp, Bid, Ask)
            table_name: Target table ("raw_spread_ticks" or "standard_ticks")

        Returns:
            Number of rows inserted (may be less than df length if duplicates)

        Raises:
            Exception: If database connection or insertion fails

        Example:
            >>> db_manager = DatabaseManager(base_dir=Path("~/eon/exness-data/"))
            >>> duckdb_path = db_manager.get_or_create_db("EURUSD")
            >>> df_ticks = pd.DataFrame({
            ...     "Timestamp": pd.date_range("2024-01-01", periods=100, freq="1s", tz="UTC"),
            ...     "Bid": [1.1000] * 100,
            ...     "Ask": [1.1001] * 100
            ... })
            >>> rows_added = db_manager.append_ticks(duckdb_path, df_ticks, "raw_spread_ticks")
            >>> print(f"Inserted {rows_added} rows")
            Inserted 100 rows
        """
        conn = duckdb.connect(str(duckdb_path))

        try:
            # Get count before insert
            count_before = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]

            # Use INSERT OR IGNORE to skip duplicates
            conn.register("df_temp", df)
            conn.execute(f"""
                INSERT OR IGNORE INTO {table_name}
                SELECT * FROM df_temp
            """)

            # Get count after insert
            count_after = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
            rows_inserted = count_after - count_before
        finally:
            conn.close()

        return rows_inserted
