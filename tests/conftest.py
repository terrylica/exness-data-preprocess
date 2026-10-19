"""
Pytest configuration and fixtures for exness-data-preprocess tests.

End-to-end testing with the ClickHouse backend, no mocking.

ClickHouse-backed tests are marked ``clickhouse`` (explicitly, or implicitly by using the
``processor_with_clickhouse`` fixture). One session-wide probe decides whether they run: it opens a
real, authenticated client through ``get_client()``, so it honours ``CLICKHOUSE_HOST``,
``CLICKHOUSE_PORT``, ``CLICKHOUSE_USER`` and ``CLICKHOUSE_PASSWORD``. A server that holds the port but
rejects the credentials counts as unavailable, not as a test failure.

When unavailable, the tests are skipped with the probe's reason, unless ``EXNESS_REQUIRE_CLICKHOUSE=1``
is set (``moon run repo:e2e`` sets it), in which case the session aborts instead of skipping.
"""

import functools
import os
import shutil
import tempfile
from pathlib import Path

import pytest

CLICKHOUSE_FIXTURE = "processor_with_clickhouse"


@functools.cache
def clickhouse_unavailable_reason() -> str | None:
    """Return why ClickHouse cannot be used, or None when an authenticated query succeeds."""
    from exness_data_preprocess.clickhouse_client import ClickHouseConnectionError, get_client

    try:
        # database="" binds no database, so the probe works before the `exness` database exists.
        client = get_client(database="")
        try:
            client.command("SELECT 1")
        finally:
            client.close()
    except ClickHouseConnectionError as e:
        return str(e).splitlines()[0]
    except Exception as e:  # noqa: BLE001 - any query failure means the server is unusable
        return f"{type(e).__name__}: {str(e).splitlines()[0] if str(e) else ''}"
    return None


def pytest_itemcollected(item: pytest.Item) -> None:
    """Mark fixture users ``clickhouse`` at collection, before ``-m`` deselection reads markers."""
    if CLICKHOUSE_FIXTURE in getattr(item, "fixturenames", ()) and not item.get_closest_marker(
        "clickhouse"
    ):
        item.add_marker(pytest.mark.clickhouse)


@pytest.hookimpl(trylast=True)
def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Probe once, over the items that survived ``-m`` / ``-k`` deselection."""
    needs_clickhouse = [item for item in items if item.get_closest_marker("clickhouse")]
    if not needs_clickhouse:
        return
    reason = clickhouse_unavailable_reason()
    if reason is None:
        return
    if os.environ.get("EXNESS_REQUIRE_CLICKHOUSE") == "1":
        raise pytest.UsageError(
            f"EXNESS_REQUIRE_CLICKHOUSE=1 but ClickHouse is unavailable: {reason}"
        )
    skip = pytest.mark.skip(reason=f"ClickHouse unavailable: {reason}")
    for item in needs_clickhouse:
        item.add_marker(skip)


@pytest.fixture
def temp_dir():
    """Temporary directory, removed after the test."""
    temp_path = Path(tempfile.mkdtemp())
    yield temp_path
    if temp_path.exists():
        shutil.rmtree(temp_path)


@pytest.fixture
def fixtures_dir():
    """Path to test fixtures directory containing real Exness-format ZIP files."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def processor_with_clickhouse():
    """ExnessDataProcessor bound to the ClickHouse server the probe reached."""
    from exness_data_preprocess.processor import ExnessDataProcessor

    processor = ExnessDataProcessor()
    yield processor
    processor.close()
