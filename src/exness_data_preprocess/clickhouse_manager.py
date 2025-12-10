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
- Phase7 30-column OHLC schema

Codec Selection (research-validated):
- DateTime64: DoubleDelta + LZ4 (1.76x faster decompression)
- Float64: Gorilla + ZSTD (8-15x compression)
- UInt8/UInt32: T64 + ZSTD (5-10x compression)
- LowCardinality(String): Dictionary encoding (4x query speed)
"""

import pandas as pd
from clickhouse_connect.driver import Client

from exness_data_preprocess.clickhouse_client import (
    ClickHouseQueryError,
    execute_command,
    execute_query,
    get_client,
)


class ClickHouseManager:
    """
    Manage ClickHouse database schema and connections.

    Responsibilities:
    - Create database and tables with proper schema
    - Add self-documenting COMMENT statements
    - Insert tick data with batch optimization
    - Ensure Phase7 30-column OHLC schema

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
        self._client = client
        self._owns_client = client is None

    @property
    def client(self) -> Client:
        """Get or create ClickHouse client."""
        if self._client is None:
            self._client = get_client()
        return self._client

    def close(self) -> None:
        """Close client connection if we own it."""
        if self._owns_client and self._client is not None:
            self._client.close()
            self._client = None

    def ensure_schema(self) -> None:
        """
        Ensure database and all tables exist with proper schema.

        Creates:
        - exness database
        - raw_spread_ticks table (ReplacingMergeTree)
        - standard_ticks table (ReplacingMergeTree)
        - ohlc_1m table (ReplacingMergeTree, 30 columns)
        - exchange_sessions table (MergeTree)
        - holidays table (MergeTree)

        All tables include self-documenting COMMENT statements.

        Raises:
            ClickHouseQueryError: If schema creation fails
        """
        # Create database
        execute_command(self.client, f"CREATE DATABASE IF NOT EXISTS {self.DATABASE}")

        # Create tick tables
        self._create_raw_spread_ticks_table()
        self._create_standard_ticks_table()

        # Create OHLC table
        self._create_ohlc_table()

        # Create lookup tables
        self._create_exchange_sessions_table()
        self._create_holidays_table()

    def _create_raw_spread_ticks_table(self) -> None:
        """Create raw_spread_ticks table with proper codecs and comments."""
        execute_command(
            self.client,
            f"""
            CREATE TABLE IF NOT EXISTS {self.DATABASE}.raw_spread_ticks (
                instrument LowCardinality(String)
                    COMMENT 'Forex pair symbol (e.g., EURUSD). FK: conceptually links to instrument metadata.',
                timestamp DateTime64(6, 'UTC') CODEC(DoubleDelta, LZ4)
                    COMMENT 'Tick timestamp with microsecond precision. Primary time dimension.',
                bid Float64 CODEC(Gorilla, ZSTD)
                    COMMENT 'Bid price from Raw_Spread variant (97.81% zero-spread execution prices).',
                ask Float64 CODEC(Gorilla, ZSTD)
                    COMMENT 'Ask price from Raw_Spread variant. Often equals bid (zero-spread).'
            ) ENGINE = ReplacingMergeTree()
            PARTITION BY toYYYYMM(timestamp)
            ORDER BY (instrument, timestamp)
            COMMENT 'Raw_Spread tick data from Exness. Primary source for BID-only OHLC construction. Deduplication via ReplacingMergeTree on (instrument, timestamp).'
            """,
        )

    def _create_standard_ticks_table(self) -> None:
        """Create standard_ticks table with proper codecs and comments."""
        execute_command(
            self.client,
            f"""
            CREATE TABLE IF NOT EXISTS {self.DATABASE}.standard_ticks (
                instrument LowCardinality(String)
                    COMMENT 'Forex pair symbol (e.g., EURUSD). FK: conceptually links to instrument metadata.',
                timestamp DateTime64(6, 'UTC') CODEC(DoubleDelta, LZ4)
                    COMMENT 'Tick timestamp with microsecond precision. Primary time dimension.',
                bid Float64 CODEC(Gorilla, ZSTD)
                    COMMENT 'Bid price from Standard variant (traditional quotes, always Bid < Ask).',
                ask Float64 CODEC(Gorilla, ZSTD)
                    COMMENT 'Ask price from Standard variant. Always > bid (never zero-spread).'
            ) ENGINE = ReplacingMergeTree()
            PARTITION BY toYYYYMM(timestamp)
            ORDER BY (instrument, timestamp)
            COMMENT 'Standard tick data from Exness. Reference quotes for position ratio calculation. ASOF merged with raw_spread_ticks.'
            """,
        )

    def _create_ohlc_table(self) -> None:
        """Create ohlc_1m table with Phase7 30-column schema."""
        execute_command(
            self.client,
            f"""
            CREATE TABLE IF NOT EXISTS {self.DATABASE}.ohlc_1m (
                instrument LowCardinality(String)
                    COMMENT 'Forex pair symbol. FK: links to raw_spread_ticks and standard_ticks.',
                timestamp DateTime64(0, 'UTC') CODEC(DoubleDelta, LZ4)
                    COMMENT 'Minute-aligned bar timestamp. Primary time dimension for OHLC.',
                open Float64 CODEC(Gorilla, ZSTD)
                    COMMENT 'First BID price in minute from raw_spread_ticks.',
                high Float64 CODEC(Gorilla, ZSTD)
                    COMMENT 'Maximum BID price in minute from raw_spread_ticks.',
                low Float64 CODEC(Gorilla, ZSTD)
                    COMMENT 'Minimum BID price in minute from raw_spread_ticks.',
                close Float64 CODEC(Gorilla, ZSTD)
                    COMMENT 'Last BID price in minute from raw_spread_ticks.',
                raw_spread_avg Nullable(Float64) CODEC(Gorilla, ZSTD)
                    COMMENT 'AVG(ask-bid) from raw_spread_ticks. Usually ~0 (97.81% zero-spread).',
                standard_spread_avg Nullable(Float64) CODEC(Gorilla, ZSTD)
                    COMMENT 'AVG(ask-bid) from standard_ticks. Always > 0 (~0.7 pips).',
                tick_count_raw_spread Nullable(UInt32) CODEC(T64, ZSTD)
                    COMMENT 'COUNT(*) from raw_spread_ticks in this minute.',
                tick_count_standard Nullable(UInt32) CODEC(T64, ZSTD)
                    COMMENT 'COUNT(*) from standard_ticks in this minute.',
                range_per_spread Nullable(Float32) CODEC(Gorilla, ZSTD)
                    COMMENT 'Normalized metric: (high-low) / raw_spread_avg.',
                range_per_tick Nullable(Float32) CODEC(Gorilla, ZSTD)
                    COMMENT 'Normalized metric: (high-low) / tick_count_raw_spread.',
                body_per_spread Nullable(Float32) CODEC(Gorilla, ZSTD)
                    COMMENT 'Normalized metric: |close-open| / raw_spread_avg.',
                body_per_tick Nullable(Float32) CODEC(Gorilla, ZSTD)
                    COMMENT 'Normalized metric: |close-open| / tick_count_raw_spread.',
                ny_hour UInt8 CODEC(T64, ZSTD)
                    COMMENT 'Hour in New York timezone (0-23). FK: joins with exchange_sessions.',
                london_hour UInt8 CODEC(T64, ZSTD)
                    COMMENT 'Hour in London timezone (0-23). FK: joins with exchange_sessions.',
                ny_session LowCardinality(String)
                    COMMENT 'NY session label: pre_market, market_open, post_market, closed.',
                london_session LowCardinality(String)
                    COMMENT 'London session label: pre_market, market_open, post_market, closed.',
                is_us_holiday UInt8
                    COMMENT 'Boolean: 1 if US market holiday. FK: joins with holidays table.',
                is_uk_holiday UInt8
                    COMMENT 'Boolean: 1 if UK market holiday. FK: joins with holidays table.',
                is_major_holiday UInt8
                    COMMENT 'Boolean: 1 if major holiday (Christmas, New Year, etc.).',
                is_nyse_session UInt8
                    COMMENT 'Boolean: 1 if NYSE is open. FK: joins with exchange_sessions (NYSE).',
                is_lse_session UInt8
                    COMMENT 'Boolean: 1 if LSE is open. FK: joins with exchange_sessions (LSE).',
                is_xswx_session UInt8
                    COMMENT 'Boolean: 1 if SIX Swiss Exchange is open.',
                is_xfra_session UInt8
                    COMMENT 'Boolean: 1 if Frankfurt Stock Exchange is open.',
                is_xtse_session UInt8
                    COMMENT 'Boolean: 1 if Toronto Stock Exchange is open.',
                is_xnze_session UInt8
                    COMMENT 'Boolean: 1 if New Zealand Stock Exchange is open.',
                is_xtks_session UInt8
                    COMMENT 'Boolean: 1 if Tokyo Stock Exchange is open.',
                is_xasx_session UInt8
                    COMMENT 'Boolean: 1 if Australian Securities Exchange is open.',
                is_xhkg_session UInt8
                    COMMENT 'Boolean: 1 if Hong Kong Stock Exchange is open.',
                is_xses_session UInt8
                    COMMENT 'Boolean: 1 if Singapore Exchange is open.'
            ) ENGINE = ReplacingMergeTree()
            PARTITION BY toYYYYMM(timestamp)
            ORDER BY (instrument, timestamp)
            COMMENT 'Phase7 30-column OHLC bars at 1-minute resolution. BID-only prices from raw_spread_ticks. Supports on-demand resampling to 5m/1h/1d.'
            """,
        )

    def _create_exchange_sessions_table(self) -> None:
        """Create exchange_sessions lookup table."""
        execute_command(
            self.client,
            f"""
            CREATE TABLE IF NOT EXISTS {self.DATABASE}.exchange_sessions (
                exchange_code LowCardinality(String)
                    COMMENT 'Exchange MIC code (NYSE, LSE, XHKG, etc.). Primary key.',
                name String
                    COMMENT 'Full exchange name (e.g., New York Stock Exchange).',
                timezone String
                    COMMENT 'IANA timezone (e.g., America/New_York).',
                open_hour UInt8
                    COMMENT 'Market open hour in local timezone (0-23).',
                open_minute UInt8
                    COMMENT 'Market open minute (0-59). Usually 0 or 30.',
                close_hour UInt8
                    COMMENT 'Market close hour in local timezone (0-23).',
                close_minute UInt8
                    COMMENT 'Market close minute (0-59). Usually 0 or 30.'
            ) ENGINE = MergeTree()
            ORDER BY exchange_code
            COMMENT 'Exchange trading hours. ~10 rows. JOIN with ohlc_1m on is_*_session columns.'
            """,
        )

    def _create_holidays_table(self) -> None:
        """Create holidays lookup table."""
        execute_command(
            self.client,
            f"""
            CREATE TABLE IF NOT EXISTS {self.DATABASE}.holidays (
                date Date
                    COMMENT 'Holiday date. Part of composite primary key.',
                exchange_code LowCardinality(String)
                    COMMENT 'Exchange MIC code. FK: exchange_sessions.exchange_code.',
                holiday_name String
                    COMMENT 'Holiday name (e.g., Christmas Day, Independence Day).'
            ) ENGINE = MergeTree()
            ORDER BY (exchange_code, date)
            COMMENT 'Exchange holidays. ~1000 rows/year. JOIN with ohlc_1m on is_*_holiday columns.'
            """,
        )

    def insert_ticks(
        self, df: pd.DataFrame, instrument: str, variant: str = "raw_spread"
    ) -> int:
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
