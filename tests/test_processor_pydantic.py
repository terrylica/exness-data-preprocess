"""Integration tests for processor methods returning Pydantic models (v2.0.0).

ADR: 2025-12-11-duckdb-removal-clickhouse

ClickHouse-only backend - No DuckDB.
Requires: ClickHouse running on localhost:8123

SLO Coverage:
- SLO-CR-2: UpdateResult/CoverageInfo match processor return data: 100% field accuracy
- SLO-MA-3: Tests independent (no execution order dependency): 100% isolation
- SLO-MA-4: True end-to-end testing from online source: Downloads real Exness data
- SLO-MA-5: Test failures don't leave orphaned temp files: 100% cleanup success
"""

import pytest

from exness_data_preprocess.models import CoverageInfo, UpdateResult


def clickhouse_available() -> bool:
    """Check if ClickHouse is running on localhost:8123."""
    import socket

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(("localhost", 8123))
        sock.close()
        return result == 0
    except Exception:
        return False


# Skip all tests in this module if ClickHouse is not available
pytestmark = pytest.mark.skipif(
    not clickhouse_available(),
    reason="ClickHouse not running on localhost:8123",
)


class TestUpdateResultModel:
    """Test UpdateResult Pydantic model with v2.0.0 field names."""

    def test_update_result_model_creation(self):
        """Test UpdateResult can be created with v2.0.0 fields.

        SLO-CR-2: Model field accuracy: 100%.
        """
        result = UpdateResult(
            database="exness",
            months_added=1,
            raw_ticks_added=1000000,
            standard_ticks_added=1000000,
            ohlc_bars=50000,
            storage_bytes=2181038080,
        )

        # Verify field types (v2.0.0 - renamed fields)
        assert isinstance(result, UpdateResult)
        assert isinstance(result.database, str)
        assert result.database == "exness"
        assert isinstance(result.months_added, int)
        assert isinstance(result.storage_bytes, int)
        assert result.storage_bytes == 2181038080

    def test_update_result_computed_fields(self):
        """Test UpdateResult computed fields work correctly.

        SLO-CR-2: Model field accuracy: 100%.
        """
        result = UpdateResult(
            database="exness",
            months_added=2,
            raw_ticks_added=1000000,
            standard_ticks_added=1000000,
            ohlc_bars=50000,
            storage_bytes=2181038080,
        )

        # Test computed fields
        assert result.avg_ticks_per_month == 1000000.0  # 2M / 2 months
        assert result.storage_efficiency_mb_per_million_ticks > 0

    def test_update_result_serialization(self):
        """Test UpdateResult serialization to dict and JSON.

        SLO-CR-2: Model field accuracy: 100%.
        """
        result = UpdateResult(
            database="exness",
            months_added=1,
            raw_ticks_added=1000000,
            standard_ticks_added=1000000,
            ohlc_bars=50000,
            storage_bytes=2181038080,
        )

        # Test dict serialization
        dict_result = result.model_dump()
        assert dict_result["database"] == "exness"
        assert dict_result["months_added"] == 1
        assert dict_result["storage_bytes"] == 2181038080

        # Test JSON serialization
        json_str = result.model_dump_json()
        assert '"database":"exness"' in json_str
        assert '"months_added":1' in json_str


class TestCoverageInfoModel:
    """Test CoverageInfo Pydantic model with v2.0.0 field names."""

    def test_coverage_info_model_creation(self):
        """Test CoverageInfo can be created with v2.0.0 fields.

        SLO-CR-2: Model field accuracy: 100%.
        """
        coverage = CoverageInfo(
            database="exness",
            storage_bytes=2181038080,
            raw_spread_ticks=1000000,
            standard_ticks=1000000,
            ohlc_bars=50000,
            earliest_date="2024-01-01 00:00:00+00:00",
            latest_date="2024-12-31 23:59:59+00:00",
            date_range_days=365,
        )

        # Verify field types (v2.0.0 - renamed fields)
        assert isinstance(coverage, CoverageInfo)
        assert isinstance(coverage.database, str)
        assert coverage.database == "exness"
        assert isinstance(coverage.storage_bytes, int)
        assert coverage.storage_bytes == 2181038080

    def test_coverage_info_computed_fields(self):
        """Test CoverageInfo computed fields work correctly.

        SLO-CR-2: Model field accuracy: 100%.
        """
        coverage = CoverageInfo(
            database="exness",
            storage_bytes=2181038080,
            raw_spread_ticks=1000000,
            standard_ticks=1000000,
            ohlc_bars=50000,
            earliest_date="2024-01-01 00:00:00+00:00",
            latest_date="2024-12-31 23:59:59+00:00",
            date_range_days=365,
        )

        # Test computed fields
        assert coverage.total_ticks == 2000000
        assert coverage.coverage_percentage > 0
        assert coverage.storage_efficiency_mb_per_million_ticks > 0

    def test_coverage_info_empty_database(self):
        """Test CoverageInfo for empty database.

        SLO-CR-2: Model field accuracy: 100%.
        """
        coverage = CoverageInfo(
            database="exness",
            storage_bytes=0,
            raw_spread_ticks=0,
            standard_ticks=0,
            ohlc_bars=0,
            earliest_date=None,
            latest_date=None,
            date_range_days=0,
        )

        assert coverage.total_ticks == 0
        assert coverage.coverage_percentage == 0.0
        assert coverage.storage_efficiency_mb_per_million_ticks == 0.0


class TestGetDataCoverageIntegration:
    """Test get_data_coverage() returns CoverageInfo with ClickHouse backend."""

    def test_get_data_coverage_returns_coverage_info(self, processor_with_clickhouse):
        """Test get_data_coverage() returns CoverageInfo model.

        SLO-CR-2: Model field accuracy: 100%.
        """
        processor = processor_with_clickhouse

        # Get coverage
        coverage = processor.get_data_coverage("EURUSD")

        # Verify CoverageInfo instance with v2.0.0 fields
        assert isinstance(coverage, CoverageInfo)
        assert isinstance(coverage.database, str)
        assert isinstance(coverage.storage_bytes, int)
        assert coverage.storage_bytes >= 0
        assert isinstance(coverage.raw_spread_ticks, int)
        assert isinstance(coverage.standard_ticks, int)
        assert isinstance(coverage.ohlc_bars, int)

    def test_coverage_info_serialization(self, processor_with_clickhouse):
        """Test CoverageInfo serialization from processor.

        SLO-CR-2: Model field accuracy: 100%.
        """
        processor = processor_with_clickhouse

        coverage = processor.get_data_coverage("EURUSD")

        # Test dict serialization
        dict_result = coverage.model_dump()
        assert "database" in dict_result
        assert "storage_bytes" in dict_result

        # Test JSON serialization
        json_str = coverage.model_dump_json()
        assert '"database"' in json_str
        assert '"storage_bytes"' in json_str
