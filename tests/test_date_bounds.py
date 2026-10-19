"""_date_bounds: inclusive, UTC-typed start/end filters shared by the tick and OHLC queries."""

from exness_data_preprocess.clickhouse_query_engine import _date_bounds


def test_no_bounds():
    assert _date_bounds(None, None) == ([], {})


def test_date_only_end_covers_whole_day():
    parts, params = _date_bounds("2026-08-01", "2026-08-31")
    assert parts == [
        "timestamp >= {start_date:DateTime64(6, 'UTC')}",
        "timestamp < addDays(toDateTime64({end_date:Date}, 6, 'UTC'), 1)",
    ]
    assert params == {"start_date": "2026-08-01", "end_date": "2026-08-31"}


def test_timestamp_end_is_exact_inclusive():
    parts, params = _date_bounds(None, "2026-08-19 18:05:44.736")
    assert parts == ["timestamp <= {end_date:DateTime64(6, 'UTC')}"]
    assert params == {"end_date": "2026-08-19 18:05:44.736"}


def test_every_bound_is_utc_typed():
    for start, end in [
        ("2026-08-01", "2026-08-02"),
        ("2026-08-01 00:00:00", "2026-08-02 12:00:00"),
    ]:
        parts, _ = _date_bounds(start, end)
        assert all("'UTC'" in p for p in parts), parts
