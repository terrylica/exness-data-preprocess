"""assign_tick_seq: the same-timestamp position that keeps distinct ticks under the dedup key."""

import pandas as pd
import pytest

from exness_data_preprocess.clickhouse_manager import assign_tick_seq


def _ts(*values: str) -> pd.Series:
    return pd.Series(pd.to_datetime(list(values), utc=True))


def test_unique_timestamps_all_get_zero():
    seq = assign_tick_seq(_ts("2026-09-01 00:00:00.1", "2026-09-01 00:00:00.2"))
    assert seq.tolist() == [0, 0]


def test_ties_numbered_in_source_order():
    seq = assign_tick_seq(
        _ts(
            "2026-09-01 00:00:01",
            "2026-09-01 00:00:01",
            "2026-09-01 00:00:02",
            "2026-09-01 00:00:01",
        )
    )
    # The third tick at :01 arrives after an intervening :02 tick and still gets position 2.
    assert seq.tolist() == [0, 1, 0, 2]


def test_same_input_same_seq_so_reinsert_deduplicates():
    ts = _ts("2026-09-01 00:00:01", "2026-09-01 00:00:01", "2026-09-01 00:00:03")
    assert assign_tick_seq(ts).tolist() == assign_tick_seq(ts.copy()).tolist()


def test_dtype_is_uint16_and_index_preserved():
    ts = _ts("2026-09-01 00:00:01", "2026-09-01 00:00:01")
    ts.index = [10, 20]
    seq = assign_tick_seq(ts)
    assert seq.dtype == "uint16"
    assert seq.index.tolist() == [10, 20]


def test_overflow_raises():
    ts = pd.Series(pd.to_datetime(["2026-09-01"] * 65537, utc=True))
    with pytest.raises(ValueError, match="overflows"):
        assign_tick_seq(ts)
