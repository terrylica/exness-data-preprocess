"""
ClickHouse schema management and tick insertion.

ADR: /docs/adr/2025-12-09-exness-clickhouse-migration.md

SLOs:
- Availability: Schema creation must succeed or raise exception (no silent failures)
- Correctness: ReplacingMergeTree provides deduplication, schema matches spec exactly
- Observability: All operations use structured logging
- Maintainability: Single module for all schema operations

Handles:
- Database and table creation with proper codecs
- Self-documenting COMMENT statements (20-27% AI accuracy improvement)
- Tick data insertion with batch optimization
- 26-column OHLC schema (ADR: 2025-12-11-duckdb-removal-clickhouse)

Codec Selection (research-validated):
- DateTime64: DoubleDelta + LZ4 (1.76x faster decompression)
- Float64: Gorilla + ZSTD (8-15x compression)
- UInt8/UInt32: T64 + ZSTD (5-10x compression)
- LowCardinality(String): Dictionary encoding (4x query speed)
"""

import pandas as pd
from clickhouse_connect.driver import Client

from exness_data_preprocess.clickhouse_base import ClickHouseClientMixin
from exness_data_preprocess.clickhouse_client import (
    ClickHouseQueryError,
    execute_command,
    execute_query,
)


class ClickHouseManager(ClickHouseClientMixin):
    """
    Manage ClickHouse database schema and connections.

    Responsibilities:
    - Create database and tables with proper schema
    - Add self-documenting COMMENT statements
    - Insert tick data with batch optimization
    - Ensure 26-column OHLC schema

    Example:
        >>> manager = ClickHouseManager()
        >>> manager.ensure_schema()
        >>> rows_added = manager.insert_ticks(df_ticks, "EURUSD", "raw_spread")
    """

    # Database name
    DATABASE = "exness"

    def __init__(self, client: Client | None = None):
        """
        Initialize ClickHouse manager.

        Args:
            client: Optional ClickHouse client (creates one if not provided)
        """
        self._init_client(client)

    def ensure_schema(self) -> None:
        """
        Ensure database and all tables exist with proper schema.

        Creates:
        - exness database
        - raw_spread_ticks table (ReplacingMergeTree)
        - standard_ticks table (ReplacingMergeTree)
        - ohlc_1m table (ReplacingMergeTree, 26 columns)
        - exchange_sessions table (MergeTree)
        - holidays table (MergeTree)

        All tables include self-documenting COMMENT statements.

        Raises:
            ClickHouseQueryError: If schema creation fails
        """
        # Create database using a client without database context
        # (database may not exist yet, so we can't connect to it)
        from exness_data_preprocess.clickhouse_client import get_client as get_client_fn

        bootstrap_client = get_client_fn(database="")  # Empty string = no database
        try:
            execute_command(bootstrap_client, f"CREATE DATABASE IF NOT EXISTS {self.DATABASE}")
        finally:
            bootstrap_client.close()

        # Create tick tables
        self._create_raw_spread_ticks_table()
        self._create_standard_ticks_table()

        # Create OHLC table
        self._create_ohlc_table()

        # Create lookup tables
        self._create_exchange_sessions_table()
        self._create_holidays_table()

    def _create_raw_spread_ticks_table(self) -> None:
        """Create raw_spread_ticks table with proper codecs.

        Note: Column-level COMMENTs removed - ClickHouse doesn't support CODEC + COMMENT together.
        Schema documentation is in table-level COMMENT and /docs/DATABASE_SCHEMA.md.
        """
        execute_command(
            self.client,
            f"""
            CREATE TABLE IF NOT EXISTS {self.DATABASE}.raw_spread_ticks (
                instrument LowCardinality(String),
                timestamp DateTime64(6, 'UTC') CODEC(DoubleDelta, LZ4),
                bid Float64 CODEC(Gorilla, ZSTD),
                ask Float64 CODEC(Gorilla, ZSTD)
            ) ENGINE = ReplacingMergeTree()
            PARTITION BY toYYYYMM(timestamp)
            ORDER BY (instrument, timestamp)
            COMMENT 'Raw_Spread tick data from Exness. Columns: instrument (forex pair), timestamp (microsecond precision), bid/ask (97.81% zero-spread execution prices). Deduplication via ReplacingMergeTree.'
            """,
        )

    def _create_standard_ticks_table(self) -> None:
        """Create standard_ticks table with proper codecs.

        Note: Column-level COMMENTs removed - ClickHouse doesn't support CODEC + COMMENT together.
        """
        execute_command(
            self.client,
            f"""
            CREATE TABLE IF NOT EXISTS {self.DATABASE}.standard_ticks (
                instrument LowCardinality(String),
                timestamp DateTime64(6, 'UTC') CODEC(DoubleDelta, LZ4),
                bid Float64 CODEC(Gorilla, ZSTD),
                ask Float64 CODEC(Gorilla, ZSTD)
            ) ENGINE = ReplacingMergeTree()
            PARTITION BY toYYYYMM(timestamp)
            ORDER BY (instrument, timestamp)
            COMMENT 'Standard tick data from Exness. Columns: instrument (forex pair), timestamp (microsecond), bid/ask (traditional quotes, always Bid < Ask). ASOF merged with raw_spread_ticks.'
            """,
        )

    def _create_ohlc_table(self) -> None:
        """Create ohlc_1m table with 26-column schema.

        ADR: 2025-12-11-duckdb-removal-clickhouse
        Note: 4 normalized metric columns removed (range_per_*, body_per_*) - can't aggregate correctly.
        Full schema documentation: /docs/DATABASE_SCHEMA.md
        """
        execute_command(
            self.client,
            f"""
            CREATE TABLE IF NOT EXISTS {self.DATABASE}.ohlc_1m (
                instrument LowCardinality(String),
                timestamp DateTime64(0, 'UTC') CODEC(DoubleDelta, LZ4),
                open Float64 CODEC(Gorilla, ZSTD),
                high Float64 CODEC(Gorilla, ZSTD),
                low Float64 CODEC(Gorilla, ZSTD),
                close Float64 CODEC(Gorilla, ZSTD),
                raw_spread_avg Nullable(Float64) CODEC(Gorilla, ZSTD),
                standard_spread_avg Nullable(Float64) CODEC(Gorilla, ZSTD),
                tick_count_raw_spread Nullable(UInt32) CODEC(T64, ZSTD),
                tick_count_standard Nullable(UInt32) CODEC(T64, ZSTD),
                ny_hour UInt8 CODEC(T64, ZSTD),
                london_hour UInt8 CODEC(T64, ZSTD),
                ny_session LowCardinality(String),
                london_session LowCardinality(String),
                is_us_holiday UInt8,
                is_uk_holiday UInt8,
                is_major_holiday UInt8,
                is_nyse_session UInt8,
                is_lse_session UInt8,
                is_xswx_session UInt8,
                is_xfra_session UInt8,
                is_xtse_session UInt8,
                is_xnze_session UInt8,
                is_xtks_session UInt8,
                is_xasx_session UInt8,
                is_xhkg_session UInt8,
                is_xses_session UInt8
            ) ENGINE = ReplacingMergeTree()
            PARTITION BY toYYYYMM(timestamp)
            ORDER BY (instrument, timestamp)
            COMMENT '26-column OHLC bars at 1-minute resolution. BID-only prices from raw_spread_ticks. Supports on-demand resampling to 5m/1h/1d. See /docs/DATABASE_SCHEMA.md for column details.'
            """,
        )

    def _create_exchange_sessions_table(self) -> None:
        """Create exchange_sessions lookup table.

        Note: Using column COMMENTs only (no CODECs needed for small lookup table).
        """
        execute_command(
            self.client,
            f"""
            CREATE TABLE IF NOT EXISTS {self.DATABASE}.exchange_sessions (
                exchange_code LowCardinality(String) COMMENT 'Exchange MIC code (NYSE, LSE, etc.)',
                name String COMMENT 'Full exchange name',
                timezone String COMMENT 'IANA timezone (e.g., America/New_York)',
                open_hour UInt8 COMMENT 'Market open hour (0-23)',
                open_minute UInt8 COMMENT 'Market open minute (0-59)',
                close_hour UInt8 COMMENT 'Market close hour (0-23)',
                close_minute UInt8 COMMENT 'Market close minute (0-59)'
            ) ENGINE = MergeTree()
            ORDER BY exchange_code
            COMMENT 'Exchange trading hours. ~10 rows. JOIN with ohlc_1m on is_*_session columns.'
            """,
        )

    def _create_holidays_table(self) -> None:
        """Create holidays lookup table.

        Note: Using column COMMENTs only (no CODECs needed for small lookup table).
        """
        execute_command(
            self.client,
            f"""
            CREATE TABLE IF NOT EXISTS {self.DATABASE}.holidays (
                date Date COMMENT 'Holiday date',
                exchange_code LowCardinality(String) COMMENT 'Exchange MIC code',
                holiday_name String COMMENT 'Holiday name (e.g., Christmas Day)'
            ) ENGINE = MergeTree()
            ORDER BY (exchange_code, date)
            COMMENT 'Exchange holidays. ~1000 rows/year. JOIN with ohlc_1m on is_*_holiday columns.'
            """,
        )

    def insert_ticks(self, df: pd.DataFrame, instrument: str, variant: str = "raw_spread") -> int:
        """
        Insert ticks into ClickHouse.

        ReplacingMergeTree handles deduplication at merge time.

        Args:
            df: DataFrame with tick data (Timestamp/timestamp, Bid/bid, Ask/ask)
            instrument: Instrument symbol (e.g., "EURUSD")
            variant: "raw_spread" or "standard"

        Returns:
            Number of rows inserted

        Raises:
            ClickHouseQueryError: If insertion fails
            ValueError: If variant is invalid

        Example:
            >>> manager = ClickHouseManager()
            >>> df_ticks = pd.DataFrame({
            ...     "timestamp": pd.date_range("2024-01-01", periods=100, freq="1s", tz="UTC"),
            ...     "bid": [1.1000] * 100,
            ...     "ask": [1.1001] * 100
            ... })
            >>> rows_added = manager.insert_ticks(df_ticks, "EURUSD", "raw_spread")
        """
        if variant not in ("raw_spread", "standard"):
            raise ValueError(f"Invalid variant: {variant}. Must be 'raw_spread' or 'standard'.")

        table_name = f"{variant}_ticks"

        # Normalize column names (handle both DuckDB-style and new lowercase)
        df = df.copy()
        column_map = {
            "Timestamp": "timestamp",
            "Bid": "bid",
            "Ask": "ask",
        }
        df = df.rename(columns={k: v for k, v in column_map.items() if k in df.columns})

        # Add instrument column
        df["instrument"] = instrument.upper()

        # Ensure correct column order
        df = df[["instrument", "timestamp", "bid", "ask"]]

        # Insert using clickhouse-connect
        try:
            self.client.insert(
                table=table_name,
                data=df,
                database=self.DATABASE,
                column_names=["instrument", "timestamp", "bid", "ask"],
            )
            return len(df)
        except Exception as e:
            raise ClickHouseQueryError(
                f"Failed to insert {len(df)} rows into {table_name}: {e}"
            ) from e

    def get_tick_count(self, instrument: str, variant: str = "raw_spread") -> int:
        """
        Get total tick count for an instrument.

        Args:
            instrument: Instrument symbol (e.g., "EURUSD")
            variant: "raw_spread" or "standard"

        Returns:
            Total tick count

        Raises:
            ClickHouseQueryError: If query fails
        """
        table_name = f"{variant}_ticks"
        result = execute_query(
            self.client,
            f"SELECT count() FROM {self.DATABASE}.{table_name} WHERE instrument = {{instrument:String}}",
            parameters={"instrument": instrument.upper()},
        )
        return result.first_row[0]

    def get_date_range(
        self, instrument: str, variant: str = "raw_spread"
    ) -> tuple[pd.Timestamp | None, pd.Timestamp | None]:
        """
        Get earliest and latest tick timestamps for an instrument.

        Args:
            instrument: Instrument symbol (e.g., "EURUSD")
            variant: "raw_spread" or "standard"

        Returns:
            Tuple of (earliest_timestamp, latest_timestamp), or (None, None) if no data

        Raises:
            ClickHouseQueryError: If query fails
        """
        table_name = f"{variant}_ticks"
        result = execute_query(
            self.client,
            f"""
            SELECT min(timestamp), max(timestamp)
            FROM {self.DATABASE}.{table_name}
            WHERE instrument = {{instrument:String}}
            """,
            parameters={"instrument": instrument.upper()},
        )
        row = result.first_row
        if row[0] is None:
            return None, None
        return pd.Timestamp(row[0], tz="UTC"), pd.Timestamp(row[1], tz="UTC")
