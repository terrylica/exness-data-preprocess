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
- 27-column OHLC schema (ADR: 2025-12-11-duckdb-removal-clickhouse)

Codec Selection (research-validated):
- DateTime64: DoubleDelta + LZ4 (1.76x faster decompression)
- Float64: Gorilla + ZSTD (8-15x compression)
- UInt8/UInt32: T64 + ZSTD (5-10x compression)
- LowCardinality(String): Dictionary encoding (4x query speed)
"""

import logging

import pandas as pd
from clickhouse_connect.driver import Client

from exness_data_preprocess.clickhouse_base import ClickHouseClientMixin
from exness_data_preprocess.clickhouse_client import (
    ClickHouseQueryError,
    execute_command,
    execute_query,
    get_client,
)

# Module-level constant mirrored by ClickHouseManager.DATABASE for callers
# that need to bootstrap the database BEFORE constructing a ClickHouseManager
# (chicken-and-egg: a default `get_client()` binds to database='exness' and
# fails immediately with UNKNOWN_DATABASE if the DB doesn't exist yet, so
# the schema-creator inside ClickHouseManager would never get a chance to
# run). Keep this name + value identical to ClickHouseManager.DATABASE.
DATABASE_NAME = "exness"

logger = logging.getLogger(__name__)

# Every table ClickHouseManager.ensure_schema() creates; get_storage_bytes() sums exactly these.
PACKAGE_TABLES = ("raw_spread_ticks", "standard_ticks", "ohlc_1m", "exchange_sessions", "holidays")


TICK_SORTING_KEY = "instrument, timestamp, seq"


def assign_tick_seq(timestamps: pd.Series) -> pd.Series:
    """
    Position of each tick among the ticks sharing its timestamp, in source order (0, 1, 2, ...).

    Exness archives contain distinct ticks with identical timestamps. Making ``seq`` part of the
    ReplacingMergeTree key keeps them, while re-inserting the same file reproduces the same
    ``seq`` values, so re-loading a month still deduplicates.

    Raises:
        ValueError: If any timestamp is NaT, or more than 65,536 ticks share one timestamp (seq is UInt16).
    """
    if timestamps.isna().any():
        raise ValueError(
            f"{int(timestamps.isna().sum())} tick(s) have no timestamp (NaT); refusing to insert"
        )
    seq = timestamps.groupby(timestamps, sort=False).cumcount()
    if len(seq) and int(seq.max()) > 65535:
        raise ValueError(f"{int(seq.max()) + 1} ticks share one timestamp; seq (UInt16) overflows")
    return seq.astype("uint16")


def migrate_ticks_table_to_seq_key(client: Client, database: str, table: str) -> bool:
    """
    Migrate a pre-3.0 tick table (sorted by instrument, timestamp) to the lossless key in place.

    Adds ``seq UInt16`` (implicit default 0) and extends the sorting key to (instrument, timestamp, seq) in
    one ALTER; existing rows get seq = 0 and are not rewritten. Ticks that the old key already
    collapsed are not recoverable from the table: re-download those months
    (``update_data(..., force_redownload=True)``) to restore them. Idempotent.

    Returns:
        True if the table was migrated, False if it already had the lossless key or does not exist.
    """
    result = execute_query(
        client,
        "SELECT sorting_key FROM system.tables WHERE database = {database:String} AND name = {table:String}",
        parameters={"database": database, "table": table},
    )
    if not result.result_rows or result.first_row[0] == TICK_SORTING_KEY:
        return False
    logger.warning(
        "Migrating %s.%s sorting key %r -> (%s); re-download affected months to restore "
        "same-timestamp ticks the old key collapsed",
        database,
        table,
        result.first_row[0],
        TICK_SORTING_KEY,
    )
    execute_command(
        client,
        f"ALTER TABLE {database}.{table} "
        "ADD COLUMN IF NOT EXISTS seq UInt16 CODEC(T64, ZSTD) AFTER timestamp, "  # no DEFAULT: a sort-key column added in the same ALTER may not have one
        f"MODIFY ORDER BY ({TICK_SORTING_KEY})",
    )
    return True


def get_storage_bytes(client: Client, database: str = DATABASE_NAME) -> int:
    """
    On-disk size of this package's tables, from ``system.tables.total_bytes``.

    The tick and OHLC tables hold every instrument, so this is database-wide, not per pair.
    Tables that do not exist yet contribute nothing; an empty schema returns 0.

    Raises:
        ClickHouseQueryError: If the query fails
    """
    result = execute_query(
        client,
        "SELECT ifNull(sum(total_bytes), 0) FROM system.tables "
        "WHERE database = {database:String} AND name IN {tables:Array(String)}",
        parameters={"database": database, "tables": list(PACKAGE_TABLES)},
    )
    return int(result.first_row[0])


def ensure_database_bootstrap() -> None:
    """
    Idempotently ensure the `exness` ClickHouse database exists.

    Issues `CREATE DATABASE IF NOT EXISTS exness` against a no-database
    connection. Callers MUST invoke this before constructing any object
    whose constructor calls `get_client()` with the default database
    (e.g. `ExnessDataProcessor.__init__`), otherwise the default
    `get_client()` will fail with UNKNOWN_DATABASE before the schema
    creator can run.

    This function is idempotent (CREATE DATABASE IF NOT EXISTS) and
    cheap (one round-trip). Safe to call on every process start.

    Discovered necessary during a 2026-05-13 mql5 pueue-job kickoff
    incident: pueue job 294 failed in 10 seconds with
    `UNKNOWN_DATABASE: Database exness does not exist` because
    `ExnessDataProcessor()` was the first thing the sibling-repo
    consumer touched on a freshly-cloned bigblack — and `get_client()`
    was called BEFORE `ClickHouseManager.ensure_schema()`. Hot-patched
    out-of-band by invoking `ClickHouseManager().ensure_schema()`
    manually; this function makes that bootstrap automatic.

    See mql5 audit: findings/audits/2026-05-13-pillar-restoration-pueue-kickoff.md
    (Hot-patch — Exness schema bootstrap section).

    Raises:
        ClickHouseConnectionError: If ClickHouse itself is unreachable.
        ClickHouseQueryError: If the CREATE DATABASE statement fails.
    """
    bootstrap_client = get_client(database="")  # Empty string = no database context
    try:
        execute_command(bootstrap_client, f"CREATE DATABASE IF NOT EXISTS {DATABASE_NAME}")
    finally:
        bootstrap_client.close()


class ClickHouseManager(ClickHouseClientMixin):
    """
    Manage ClickHouse database schema and connections.

    Responsibilities:
    - Create database and tables with proper schema
    - Add self-documenting COMMENT statements
    - Insert tick data with batch optimization
    - Ensure 27-column OHLC schema

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
        - ohlc_1m table (ReplacingMergeTree, 27 columns)
        - exchange_sessions table (MergeTree)
        - holidays table (MergeTree)

        All tables include self-documenting COMMENT statements.

        Raises:
            ClickHouseQueryError: If schema creation fails
        """
        # Idempotently create the `exness` database. Delegated to the
        # module-level helper so that callers needing a pre-`get_client()`
        # bootstrap (e.g. ExnessDataProcessor.__init__) can invoke the same
        # logic without instantiating a ClickHouseManager (which would
        # itself try to bind a client to the not-yet-existing database).
        ensure_database_bootstrap()

        # Create tick tables
        self._create_raw_spread_ticks_table()
        self._create_standard_ticks_table()

        # Create OHLC table
        self._create_ohlc_table()

        # Create lookup tables
        self._create_exchange_sessions_table()
        self._create_holidays_table()

    def _create_raw_spread_ticks_table(self) -> None:
        self._create_ticks_table(
            "raw_spread_ticks",
            "Raw_Spread tick data from Exness. Columns: instrument (forex pair), timestamp "
            "(microsecond precision), seq (position among same-timestamp ticks in source order), "
            "bid/ask (mostly zero-spread execution prices). Deduplication via ReplacingMergeTree "
            "on (instrument, timestamp, seq).",
        )

    def _create_standard_ticks_table(self) -> None:
        self._create_ticks_table(
            "standard_ticks",
            "Standard tick data from Exness. Columns: instrument (forex pair), timestamp "
            "(microsecond), seq (position among same-timestamp ticks in source order), bid/ask "
            "(traditional quotes, Bid < Ask). Aggregated per minute into ohlc_1m.",
        )

    def _create_ticks_table(self, table: str, comment: str) -> None:
        """Create a tick table, or migrate an existing pre-3.0 one to the lossless key.

        Note: Column-level COMMENTs removed - ClickHouse doesn't support CODEC + COMMENT together.
        Schema documentation is in the table-level COMMENT and README.md#schema.
        """
        assert "'" not in comment, "table comment is inlined into DDL and must not contain quotes"
        execute_command(
            self.client,
            f"""
            CREATE TABLE IF NOT EXISTS {self.DATABASE}.{table} (
                instrument LowCardinality(String),
                timestamp DateTime64(6, 'UTC') CODEC(DoubleDelta, LZ4),
                seq UInt16 CODEC(T64, ZSTD),
                bid Float64 CODEC(Gorilla, ZSTD),
                ask Float64 CODEC(Gorilla, ZSTD)
            ) ENGINE = ReplacingMergeTree()
            PARTITION BY toYYYYMM(timestamp)
            ORDER BY (instrument, timestamp, seq)
            COMMENT '{comment}'
            """,
        )
        migrate_ticks_table_to_seq_key(self.client, self.DATABASE, table)

    def _create_ohlc_table(self) -> None:
        """Create ohlc_1m table with 27-column schema.

        ADR: 2025-12-11-duckdb-removal-clickhouse
        Note: 4 normalized metric columns removed (range_per_*, body_per_*) - can't aggregate correctly.
        Schema summary: README.md#schema
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
            COMMENT '27-column OHLC bars at 1-minute resolution. BID-only prices from raw_spread_ticks. Supports on-demand resampling to 5m/1h/1d. Column summary: README.md#schema in exness-data-preprocess.'
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

        # Add instrument column and the same-timestamp position (part of the dedup key)
        df["instrument"] = instrument.upper()
        df["seq"] = assign_tick_seq(df["timestamp"])

        # Ensure correct column order
        df = df[["instrument", "timestamp", "seq", "bid", "ask"]]

        # Insert using clickhouse-connect
        try:
            self.client.insert_df(
                table=table_name,
                df=df,
                database=self.DATABASE,
                column_names=["instrument", "timestamp", "seq", "bid", "ask"],
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
            f"SELECT count() FROM {self.DATABASE}.{table_name} FINAL WHERE instrument = {{instrument:String}}",
            parameters={"instrument": instrument.upper()},
        )
        return int(result.first_row[0])

    def get_ohlc_bar_count(self, instrument: str) -> int:
        """
        Number of 1-minute bars stored in ohlc_1m for an instrument.

        Raises:
            ClickHouseQueryError: If query fails
        """
        result = execute_query(
            self.client,
            f"SELECT count() FROM {self.DATABASE}.ohlc_1m FINAL WHERE instrument = {{instrument:String}}",
            parameters={"instrument": instrument.upper()},
        )
        return int(result.first_row[0])

    def get_storage_bytes(self) -> int:
        """On-disk size of this package's tables (database-wide); see get_storage_bytes()."""
        return get_storage_bytes(self.client, self.DATABASE)

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
        # pd.Timestamp(...) widens to Timestamp | NaTType in stubs (NaT for
        # invalid input). row[0] and row[1] are guaranteed non-null DateTime64
        # values from min()/max() above — NULL would have short-circuited at
        # the `row[0] is None` check above. The isinstance narrowing below is
        # what both mypy (which sees the Timestamp branch directly) and ty
        # (which uses the wider stub) accept as a return-type proof.
        earliest = pd.Timestamp(row[0], tz="UTC")
        latest = pd.Timestamp(row[1], tz="UTC")
        if not isinstance(earliest, pd.Timestamp) or not isinstance(latest, pd.Timestamp):
            # Unreachable in practice — min()/max() never return NaT when the
            # row is non-null. The branch is defensive against future stub
            # surprises and keeps the narrowing observable to both checkers.
            return None, None
        return earliest, latest
