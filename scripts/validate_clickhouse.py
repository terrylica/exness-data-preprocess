#!/usr/bin/env python3
"""End-to-end checks against a ClickHouse server (CLICKHOUSE_HOST/PORT, default localhost:8123).

Usage:
    uv run python scripts/validate_clickhouse.py status       # port probe + client connection check
    uv run python scripts/validate_clickhouse.py schema       # ClickHouseManager().ensure_schema() (creates tables)
    uv run python scripts/validate_clickhouse.py load         # download + insert last month's EURUSD from ticks.ex2archive.com
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
    """Load last month's EURUSD (both variants) so the query checks have real rows."""
    first_of_this_month = dt.date.today().replace(day=1)
    start = (first_of_this_month - dt.timedelta(days=1)).replace(day=1)
    print(f"🔍 Loading EURUSD from {start:%Y-%m} via ticks.ex2archive.com...")
    from exness_data_preprocess import ExnessDataProcessor, UpdateResult

    with ExnessDataProcessor() as processor:
        result = processor.update_data("EURUSD", start_date=start.isoformat())
    assert isinstance(result, UpdateResult), f"unexpected result type: {type(result).__name__}"
    with ExnessDataProcessor() as processor:
        coverage = processor.get_data_coverage("EURUSD")
    assert coverage.raw_spread_ticks > 0, "no Raw_Spread ticks after load"
    assert coverage.standard_ticks > 0, "no Standard ticks after load"
    print(f"  ✓ raw_spread_ticks={coverage.raw_spread_ticks:,} standard_ticks={coverage.standard_ticks:,}")
    print("✅ Load passed")


def check_data() -> None:
    print("🔍 Validating ClickHouse data operations...")
    from exness_data_preprocess import ClickHouseQueryEngine

    engine = ClickHouseQueryEngine()

    df = engine.query_ticks("EURUSD", limit=1000)
    assert len(df) > 0, "query_ticks returned no rows (load EURUSD first: validate_clickhouse.py load)"
    print(f"  ✓ query_ticks returned {len(df)} rows")

    for col in ["timestamp", "bid", "ask"]:
        assert col in df.columns, f"Missing column: {col}"
    print("  ✓ All expected columns present")

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

    assert len(df) > 0, "query_ohlc returned no bars (load EURUSD first: validate_clickhouse.py load)"
    for col in ["open", "high", "low", "close"]:
        assert col in df.columns, f"Missing OHLC column: {col}"
    print("  ✓ All OHLC columns present")

    engine.close()
    print("✅ OHLC validation passed")


CHECKS: dict[str, Callable[[], None]] = {
    "status": check_status,
    "schema": check_schema,
    "load": check_load,
    "data": check_data,
    "pagination": check_pagination,
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
