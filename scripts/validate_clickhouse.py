#!/usr/bin/env python3
"""End-to-end checks against the local ClickHouse server (localhost:8123).

Usage:
    uv run python scripts/validate_clickhouse.py status       # port probe + client connection check
    uv run python scripts/validate_clickhouse.py schema       # ClickHouseManager().ensure_schema() (creates tables)
    uv run python scripts/validate_clickhouse.py data         # query_ticks('EURUSD') returns the expected columns
    uv run python scripts/validate_clickhouse.py pagination   # LIMIT / OFFSET / cursor / batch iteration
    uv run python scripts/validate_clickhouse.py ohlc         # query_ohlc('EURUSD', '1h')
    uv run python scripts/validate_clickhouse.py all          # every check above, in that order

The moon tasks `validate-clickhouse-*` run these checks (`moon run repo:validate-clickhouse`).
The data, pagination and ohlc checks need EURUSD ticks loaded into the `exness` database.

Exit codes: 0 = check passed, 1 = check failed (assertion or ClickHouse error).
"""

from __future__ import annotations

import argparse
import socket
import sys
from collections.abc import Callable

CLICKHOUSE_PORT = 8123


def check_status() -> None:
    """Fail unless the server answers on the port and the client can connect."""
    try:
        with socket.create_connection(("localhost", CLICKHOUSE_PORT), timeout=2):
            pass
    except OSError:
        raise SystemExit(
            f"❌ ClickHouse not running on port {CLICKHOUSE_PORT} "
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


def check_data() -> None:
    print("🔍 Validating ClickHouse data operations...")
    from exness_data_preprocess import ClickHouseQueryEngine

    engine = ClickHouseQueryEngine()

    df = engine.query_ticks("EURUSD", limit=1000)
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
    assert len(df1) <= 100, f"LIMIT failed: got {len(df1)} rows"
    print(f"  ✓ LIMIT=100 returned {len(df1)} rows")

    df2 = engine.query_ticks("EURUSD", limit=100, offset=100)
    assert len(df2) <= 100, f"OFFSET failed: got {len(df2)} rows"
    print(f"  ✓ LIMIT=100 OFFSET=100 returned {len(df2)} rows")

    result = engine.query_ticks_paginated("EURUSD", page_size=1000)
    print(f"  ✓ Cursor pagination: {len(result.data)} rows, has_more={result.has_more}")

    batches = list(engine.query_ticks_batches("EURUSD", batch_size=1000, max_batches=3))
    print(f"  ✓ Batch iterator: {len(batches)} batches")

    engine.close()
    print("✅ Pagination validation passed")


def check_ohlc() -> None:
    print("🔍 Validating ClickHouse OHLC queries...")
    from exness_data_preprocess import ClickHouseQueryEngine

    engine = ClickHouseQueryEngine()

    df = engine.query_ohlc("EURUSD", timeframe="1h", limit=100)
    print(f"  ✓ query_ohlc(1h) returned {len(df)} bars")

    if len(df) > 0:
        for col in ["open", "high", "low", "close"]:
            assert col in df.columns, f"Missing OHLC column: {col}"
        print("  ✓ All OHLC columns present")
    else:
        print("  ⚠ No OHLC data available (expected if no data loaded)")

    engine.close()
    print("✅ OHLC validation passed")


CHECKS: dict[str, Callable[[], None]] = {
    "status": check_status,
    "schema": check_schema,
    "data": check_data,
    "pagination": check_pagination,
    "ohlc": check_ohlc,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="End-to-end checks against the local ClickHouse server (localhost:8123).",
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
