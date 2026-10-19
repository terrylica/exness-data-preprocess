"""End-to-end usage of exness-data-preprocess against ClickHouse.

Usage:
    uv run python examples/basic_usage.py [PAIR ...] [--start YYYY-MM-DD]

Defaults: EURUSD, starting at the first day of last month (one or two months of downloads).
Connection comes from CLICKHOUSE_HOST / CLICKHOUSE_PORT / CLICKHOUSE_USER / CLICKHOUSE_PASSWORD
(default localhost:8123, user `default`). `moon run repo:e2e` runs this script against its
throwaway server, so it is kept working by the E2E gate.
"""

from __future__ import annotations

import argparse
import datetime as dt
from typing import get_args

import exness_data_preprocess as edp
from exness_data_preprocess.models import PairType


def last_month_start() -> str:
    first_of_this_month = dt.date.today().replace(day=1)
    return (first_of_this_month - dt.timedelta(days=1)).replace(day=1).isoformat()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "pairs",
        nargs="*",
        metavar="PAIR",
        help=f"default EURUSD; one of {', '.join(get_args(PairType))}",
    )
    parser.add_argument("--start", default=last_month_start(), help="first month to load")
    args = parser.parse_args()

    with edp.ExnessDataProcessor() as processor:
        for pair in args.pairs or ["EURUSD"]:
            # Preview first: which months are missing and roughly how big they are.
            plan = processor.update_data(pair, start_date=args.start, dry_run=True)
            print(f"{pair}: would download {plan.would_download_months} month(s)")

            # Download both variants, insert ticks, regenerate 1m OHLC. Re-running is a no-op.
            result = processor.update_data(pair, start_date=args.start)
            print(f"{pair}: +{result.months_added} months, +{result.raw_ticks_added:,} raw ticks")

            coverage = processor.get_data_coverage(pair)
            print(
                f"{pair}: {coverage.earliest_date} .. {coverage.latest_date}, "
                f"{coverage.raw_spread_ticks:,} raw / {coverage.standard_ticks:,} standard ticks, "
                f"{coverage.storage_bytes / 1e6:.1f} MB"
            )

            ticks = processor.query_ticks(pair, "raw_spread", limit=5)
            print(ticks)

            # 1m bars are stored; other timeframes are resampled in ClickHouse on read.
            bars = processor.query_ohlc(pair, "1h", limit=5)
            print(bars[["timestamp", "open", "high", "low", "close"]])


if __name__ == "__main__":
    main()
