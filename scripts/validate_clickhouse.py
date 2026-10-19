#!/usr/bin/env python3
"""End-to-end checks against a ClickHouse server (CLICKHOUSE_HOST/PORT, default localhost:8123).

Usage:
    uv run python scripts/validate_clickhouse.py status       # port probe + client connection check
    uv run python scripts/validate_clickhouse.py schema       # ClickHouseManager().ensure_schema() (creates tables)
    uv run python scripts/validate_clickhouse.py load         # download + insert EURUSD from the month before last (ticks.ex2archive.com)
    uv run python scripts/validate_clickhouse.py data         # query_ticks('EURUSD') returns the expected columns
    uv run python scripts/validate_clickhouse.py pagination   # LIMIT / OFFSET / cursor / batch iteration
    uv run python scripts/validate_clickhouse.py ohlc         # query_ohlc('EURUSD', '1h')
    uv run python scripts/validate_clickhouse.py all          # every check above, in that order

The moon tasks `validate-clickhouse-*` run these checks (`moon run repo:validate-clickhouse`).
The data, pagination and ohlc checks need EURUSD ticks in the `exness` database and fail on an
empty table. `moon run repo:e2e` runs `all` against a throwaway server (scripts/e2e-ephemeral.sh).

Exit codes: 0 = check passed, 1 = check failed (assertion or ClickHouse error).
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import socket
import sys
from collections.abc import Callable

CLICKHOUSE_HOST = os.environ.get("CLICKHOUSE_HOST", "localhost")
CLICKHOUSE_PORT = int(os.environ.get("CLICKHOUSE_PORT", "8123"))


def check_status() -> None:
    """Fail unless the server answers on the port and the client can connect."""
    try:
        with socket.create_connection((CLICKHOUSE_HOST, CLICKHOUSE_PORT), timeout=2):
            pass
    except OSError:
        raise SystemExit(
            f"❌ ClickHouse not running on {CLICKHOUSE_HOST}:{CLICKHOUSE_PORT} "
            "(start it with: moon run repo:clickhouse-start)"
        ) from None

    from exness_data_preprocess import get_clickhouse_client
    from exness_data_preprocess.clickhouse_client import check_connection

    client = get_clickhouse_client()
    check_connection(client)
    print("✅ ClickHouse connection OK")
    client.close()


def check_schema() -> None:
    print("🔍 Validating ClickHouse schema...")
    from exness_data_preprocess import ClickHouseManager

    manager = ClickHouseManager()
    manager.ensure_schema()
    print("  ✓ ticks table created")
    print("  ✓ ohlc table created")
    manager.close()
    print("✅ Schema validation passed")


def check_load() -> None:
    """Load EURUSD (both variants) from the month before last, so the query checks have real rows.

    The month before last, not last month: early in a month, last month's archive may not be
    published yet, and update_data skips unpublished months, which would fail the row assertions.
    """
    first_of_this_month = dt.date.today().replace(day=1)
    first_of_last_month = (first_of_this_month - dt.timedelta(days=1)).replace(day=1)
    start = (first_of_last_month - dt.timedelta(days=1)).replace(day=1)
    print(f"🔍 Loading EURUSD from {start:%Y-%m} via ticks.ex2archive.com...")
    from exness_data_preprocess import ExnessDataProcessor, UpdateResult

    with ExnessDataProcessor() as processor:
        result = processor.update_data("EURUSD", start_date=start.isoformat())
    assert isinstance(result, UpdateResult), f"unexpected result type: {type(result).__name__}"
    with ExnessDataProcessor() as processor:
        coverage = processor.get_data_coverage("EURUSD")
    assert coverage.raw_spread_ticks > 0, "no Raw_Spread ticks after load"
    assert coverage.standard_ticks > 0, "no Standard ticks after load"
    assert coverage.storage_bytes > 0, "storage_bytes is 0 with data loaded"
    assert coverage.ohlc_bars > 0, "no OHLC bars after load"

    # Lossless: after merging (FINAL), every inserted tick is still stored, including distinct
    # ticks that share a timestamp (seq > 0), which the pre-3.0 key collapsed.
    raw_final, std_final, raw_ties = _final_counts()
    assert raw_final == result.raw_ticks_added, (
        f"raw_spread_ticks FINAL={raw_final:,} != inserted {result.raw_ticks_added:,}"
    )
    assert std_final == result.standard_ticks_added, (
        f"standard_ticks FINAL={std_final:,} != inserted {result.standard_ticks_added:,}"
    )
    assert raw_ties > 0, (
        "no same-timestamp ticks stored (seq > 0); the lossless path was not exercised"
    )
    print(
        f"  ✓ lossless: FINAL counts equal inserted ({raw_final:,} / {std_final:,}); {raw_ties:,} ticks with seq > 0"
    )

    # Re-inserting the same months must not add rows: force_redownload re-processes them all.
    with ExnessDataProcessor() as processor:
        forced = processor.update_data(
            "EURUSD", start_date=start.isoformat(), force_redownload=True
        )
    assert isinstance(forced, UpdateResult) and forced.months_added == result.months_added, (
        f"force_redownload processed {getattr(forced, 'months_added', None)} months, expected {result.months_added}"
    )
    assert _final_counts() == (raw_final, std_final, raw_ties), (
        "force_redownload changed FINAL counts"
    )
    assert forced.ohlc_bars == result.ohlc_bars, (
        f"force_redownload reported {forced.ohlc_bars:,} OHLC bars, first load {result.ohlc_bars:,}"
    )
    print(
        f"  ✓ force_redownload re-inserted {forced.months_added} months; FINAL counts unchanged (idempotent)"
    )

    # A second update finds nothing to download; its result must describe the stored data.
    with ExnessDataProcessor() as processor:
        again = processor.update_data("EURUSD", start_date=start.isoformat())
    assert isinstance(again, UpdateResult) and again.months_added == 0, (
        "second update was not a no-op"
    )
    assert again.ohlc_bars == coverage.ohlc_bars, (
        f"up-to-date UpdateResult.ohlc_bars={again.ohlc_bars} != stored bars {coverage.ohlc_bars}"
    )
    assert again.storage_bytes > 0, "up-to-date UpdateResult.storage_bytes is 0"
    print(
        f"  ✓ storage_bytes={coverage.storage_bytes:,} ohlc_bars={coverage.ohlc_bars:,} (no-op update agrees)"
    )
    print(
        f"  ✓ raw_spread_ticks={coverage.raw_spread_ticks:,} standard_ticks={coverage.standard_ticks:,}"
    )
    print("✅ Load passed")


def _final_counts() -> tuple[int, int, int]:
    """(raw_spread FINAL rows, standard FINAL rows, raw_spread FINAL rows with seq > 0) for EURUSD."""
    from exness_data_preprocess import get_clickhouse_client

    client = get_clickhouse_client()
    try:
        row = client.query(
            "SELECT"
            " (SELECT count() FROM exness.raw_spread_ticks FINAL WHERE instrument = 'EURUSD'),"
            " (SELECT count() FROM exness.standard_ticks FINAL WHERE instrument = 'EURUSD'),"
            " (SELECT count() FROM exness.raw_spread_ticks FINAL WHERE instrument = 'EURUSD' AND seq > 0)"
        ).first_row
    finally:
        client.close()
    return int(row[0]), int(row[1]), int(row[2])


def check_migration() -> None:
    """A pre-3.0 tick table (key: instrument, timestamp) migrates in place and keeps its rows."""
    print("🔍 Validating pre-3.0 tick table migration...")
    from exness_data_preprocess import get_clickhouse_client
    from exness_data_preprocess.clickhouse_manager import (
        TICK_SORTING_KEY,
        migrate_ticks_table_to_seq_key,
    )

    db = "exness_migration_check"
    client = get_clickhouse_client(database="")
    try:
        client.command(f"DROP DATABASE IF EXISTS {db}")
        client.command(f"CREATE DATABASE {db}")
        client.command(
            f"CREATE TABLE {db}.raw_spread_ticks (instrument LowCardinality(String),"
            " timestamp DateTime64(6, 'UTC'), bid Float64, ask Float64)"
            " ENGINE = ReplacingMergeTree() PARTITION BY toYYYYMM(timestamp) ORDER BY (instrument, timestamp)"
        )
        client.command(
            f"INSERT INTO {db}.raw_spread_ticks VALUES"
            " ('EURUSD', '2026-09-01 00:00:01', 1.1, 1.1), ('EURUSD', '2026-09-01 00:00:02', 1.2, 1.2)"
        )
        assert migrate_ticks_table_to_seq_key(client, db, "raw_spread_ticks") is True, (
            "did not migrate"
        )
        assert migrate_ticks_table_to_seq_key(client, db, "raw_spread_ticks") is False, (
            "not idempotent"
        )
        key = client.query(
            f"SELECT sorting_key FROM system.tables WHERE database = '{db}' AND name = 'raw_spread_ticks'"
        ).first_row[0]
        assert key == TICK_SORTING_KEY, f"sorting key after migration: {key!r}"
        # A second tick at :01 with seq 1 now survives a merge alongside the migrated seq-0 row.
        client.command(
            f"INSERT INTO {db}.raw_spread_ticks (instrument, timestamp, seq, bid, ask)"
            " VALUES ('EURUSD', '2026-09-01 00:00:01', 1, 1.15, 1.15)"
        )
        client.command(f"OPTIMIZE TABLE {db}.raw_spread_ticks FINAL")
        n = client.query(f"SELECT count() FROM {db}.raw_spread_ticks").first_row[0]
        assert n == 3, f"expected 3 rows after migration + tie insert + merge, got {n}"
        print(f"  ✓ sorting key -> ({key}); existing rows kept; same-timestamp tick survives merge")
    finally:
        client.command(f"DROP DATABASE IF EXISTS {db}")
        client.close()
    print("✅ Migration validation passed")


def check_ties() -> None:
    """Cursor pagination through a run of same-timestamp ticks returns every one of them."""
    print("🔍 Validating pagination across same-timestamp ticks...")
    from exness_data_preprocess import ClickHouseQueryEngine, get_clickhouse_client

    client = get_clickhouse_client()
    try:
        ts, n = client.query(
            "SELECT timestamp, count() AS n FROM exness.raw_spread_ticks FINAL"
            " WHERE instrument = 'EURUSD' GROUP BY timestamp HAVING n > 1 ORDER BY n DESC, timestamp LIMIT 1"
        ).first_row
    finally:
        client.close()
    engine = ClickHouseQueryEngine()
    seen = 0
    cursor = None
    # page_size=1 puts a page boundary between every pair of tied ticks.
    while True:
        page = engine.query_ticks_paginated(
            "EURUSD", page_size=1, cursor=cursor, start_date=str(ts), end_date=str(ts)
        )
        seen += len(page.data)
        if not page.has_more:
            break
        cursor = page.next_cursor
    engine.close()
    assert seen == n, f"paginated {seen} ticks at {ts}, expected {n}"
    print(f"  ✓ {n} ticks share {ts}; page_size=1 pagination returned all {seen}")
    print("✅ Tie pagination passed")


def check_data() -> None:
    print("🔍 Validating ClickHouse data operations...")
    from exness_data_preprocess import ClickHouseQueryEngine

    engine = ClickHouseQueryEngine()

    df = engine.query_ticks("EURUSD", limit=1000)
    assert len(df) > 0, (
        "query_ticks returned no rows (load EURUSD first: validate_clickhouse.py load)"
    )
    print(f"  ✓ query_ticks returned {len(df)} rows")

    for col in ["timestamp", "bid", "ask"]:
        assert col in df.columns, f"Missing column: {col}"
    print("  ✓ All expected columns present")

    # A date-only end_date includes that whole day (it used to stop at 00:00:00 of that day).
    day = str(df["timestamp"].iloc[-1])[:10]
    whole_day = engine.query_ticks("EURUSD", start_date=day, end_date=day)
    days = {str(t)[:10] for t in whole_day["timestamp"]}
    assert len(whole_day) > 1 and days == {day}, (
        f"start_date=end_date={day} returned {len(whole_day)} ticks on days {sorted(days)}"
    )
    print(f"  ✓ start_date=end_date={day} returned the whole day: {len(whole_day):,} ticks")

    engine.close()
    print("✅ Data validation passed")


def check_pagination() -> None:
    print("🔍 Validating ClickHouse pagination...")
    from exness_data_preprocess import ClickHouseQueryEngine

    engine = ClickHouseQueryEngine()

    df1 = engine.query_ticks("EURUSD", limit=100)
    assert len(df1) == 100, f"LIMIT failed: got {len(df1)} rows, expected 100"
    print(f"  ✓ LIMIT=100 returned {len(df1)} rows")

    df2 = engine.query_ticks("EURUSD", limit=100, offset=100)
    assert len(df2) == 100, f"OFFSET failed: got {len(df2)} rows, expected 100"
    assert not df1["timestamp"].equals(df2["timestamp"]), "OFFSET returned the same page as LIMIT"
    print(f"  ✓ LIMIT=100 OFFSET=100 returned {len(df2)} rows")

    result = engine.query_ticks_paginated("EURUSD", page_size=1000)
    print(f"  ✓ Cursor pagination: {len(result.data)} rows, has_more={result.has_more}")

    assert len(result.data) > 0, "cursor pagination returned no rows"
    batches = list(engine.query_ticks_batches("EURUSD", batch_size=1000, max_batches=3))
    assert len(batches) == 3, f"batch iterator yielded {len(batches)} batches, expected 3"
    print(f"  ✓ Batch iterator: {len(batches)} batches")

    engine.close()
    print("✅ Pagination validation passed")


def check_ohlc() -> None:
    print("🔍 Validating ClickHouse OHLC queries...")
    from exness_data_preprocess import ClickHouseQueryEngine

    engine = ClickHouseQueryEngine()

    df = engine.query_ohlc("EURUSD", timeframe="1h", limit=100)
    print(f"  ✓ query_ohlc(1h) returned {len(df)} bars")

    assert len(df) > 0, (
        "query_ohlc returned no bars (load EURUSD first: validate_clickhouse.py load)"
    )
    for col in ["open", "high", "low", "close"]:
        assert col in df.columns, f"Missing OHLC column: {col}"
    print("  ✓ All OHLC columns present")

    engine.close()
    print("✅ OHLC validation passed")


CHECKS: dict[str, Callable[[], None]] = {
    "status": check_status,
    "schema": check_schema,
    "migration": check_migration,
    "load": check_load,
    "data": check_data,
    "pagination": check_pagination,
    "ties": check_ties,
    "ohlc": check_ohlc,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="End-to-end checks against a ClickHouse server (CLICKHOUSE_HOST/PORT).",
    )
    parser.add_argument(
        "check",
        choices=[*CHECKS, "all"],
        help="which check to run; 'all' runs every check in order",
    )
    args = parser.parse_args(argv)

    names = list(CHECKS) if args.check == "all" else [args.check]
    for name in names:
        CHECKS[name]()
    return 0


if __name__ == "__main__":
    sys.exit(main())
