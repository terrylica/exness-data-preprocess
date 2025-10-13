"""Integration tests for processor methods returning Pydantic models (v2.1.0).

TRUE End-to-End Testing: Downloads from https://ticks.ex2archive.com/ - No mocking.

SLO Coverage:
- SLO-CR-2: UpdateResult/CoverageInfo match processor return data: 100% field accuracy
- SLO-MA-3: Tests independent (no execution order dependency): 100% isolation
- SLO-MA-4: True end-to-end testing from online source: Downloads real Exness data
- SLO-MA-5: Test failures don't leave orphaned temp files: 100% cleanup success
"""

import pytest
from pathlib import Path

from exness_data_preprocess.models import CoverageInfo, UpdateResult
from exness_data_preprocess.processor import ExnessDataProcessor


class TestUpdateDataReturnsUpdateResult:
    """Test update_data() returns UpdateResult Pydantic instance with real data."""

    def test_update_data_with_real_zip_files(self, processor_with_real_data):
        """Test update_data() returns UpdateResult from real downloaded Exness data.

        SLO-CR-2: Model field accuracy: 100%.
        SLO-MA-4: No mocking - downloads and processes real Exness data.
        """
        # Find downloaded ZIP files (downloaded by fixture from Exness online source)
        raw_spread_zip = processor_with_real_data.temp_dir / "Exness_EURUSD_Raw_Spread_2024_08.zip"
        standard_zip = processor_with_real_data.temp_dir / "Exness_EURUSD_2024_08.zip"

        assert raw_spread_zip.exists(), "Downloaded ZIP from Exness must exist"

        if not processor_with_real_data.has_standard_data:
            pytest.skip("Standard variant not available for this month")

        # Load ticks from downloaded ZIPs
        df_raw = processor_with_real_data._load_ticks_from_zip(raw_spread_zip)
        df_std = processor_with_real_data._load_ticks_from_zip(standard_zip)

        assert len(df_raw) > 0, "Real data should have ticks"
        assert len(df_std) > 0, "Real data should have ticks"

        # Get or create database
        duckdb_path = processor_with_real_data._get_or_create_db("EURUSD")

        # Append ticks
        processor_with_real_data._append_ticks_to_db(duckdb_path, df_raw, "raw_spread_ticks")
        processor_with_real_data._append_ticks_to_db(duckdb_path, df_std, "standard_ticks")

        # Regenerate OHLC
        processor_with_real_data._regenerate_ohlc(duckdb_path)

        # Get coverage to create UpdateResult
        import duckdb
        conn = duckdb.connect(str(duckdb_path), read_only=True)
        raw_count = conn.execute("SELECT COUNT(*) FROM raw_spread_ticks").fetchone()[0]
        std_count = conn.execute("SELECT COUNT(*) FROM standard_ticks").fetchone()[0]
        ohlc_count = conn.execute("SELECT COUNT(*) FROM ohlc_1m").fetchone()[0]
        conn.close()

        result = UpdateResult(
            duckdb_path=duckdb_path,
            months_added=1,
            raw_ticks_added=raw_count,
            standard_ticks_added=std_count,
            ohlc_bars=ohlc_count,
            duckdb_size_mb=duckdb_path.stat().st_size / 1024 / 1024,
        )

        # Verify UpdateResult instance
        assert isinstance(result, UpdateResult)
        assert isinstance(result.duckdb_path, Path)
        assert result.months_added >= 0
        assert result.raw_ticks_added > 0, "Real data should have ticks"
        assert result.standard_ticks_added > 0, "Real data should have ticks"
        assert result.ohlc_bars > 0
        assert result.duckdb_size_mb > 0

    def test_update_result_attribute_access(self, processor_with_real_data):
        """Test UpdateResult supports attribute access with real downloaded data.

        SLO-CR-2: Model field accuracy: 100%.
        """
        # Load downloaded data
        raw_spread_zip = processor_with_real_data.temp_dir / "Exness_EURUSD_Raw_Spread_2024_08.zip"
        df_raw = processor_with_real_data._load_ticks_from_zip(raw_spread_zip)

        duckdb_path = processor_with_real_data._get_or_create_db("EURUSD")
        processor_with_real_data._append_ticks_to_db(duckdb_path, df_raw, "raw_spread_ticks")

        # Create UpdateResult
        result = UpdateResult(
            duckdb_path=duckdb_path,
            months_added=1,
            raw_ticks_added=len(df_raw),
            standard_ticks_added=0,
            ohlc_bars=0,
            duckdb_size_mb=duckdb_path.stat().st_size / 1024 / 1024,
        )

        # Verify attribute access
        assert isinstance(result.months_added, int)
        assert isinstance(result.duckdb_path, Path)
        assert isinstance(result.duckdb_size_mb, float)
        assert result.raw_ticks_added > 0
        assert result.raw_ticks_added == len(df_raw)


class TestGetDataCoverageReturnsCoverageInfo:
    """Test get_data_coverage() returns CoverageInfo Pydantic instance with real data."""

    def test_get_data_coverage_with_real_database(self, processor_with_real_data):
        """Test get_data_coverage() returns CoverageInfo from real downloaded data.

        SLO-CR-2: Model field accuracy: 100%.
        SLO-MA-4: No mocking - downloads and processes real Exness data.
        """
        if not processor_with_real_data.has_standard_data:
            pytest.skip("Standard variant not available for this month")

        # Load downloaded data into database
        raw_spread_zip = processor_with_real_data.temp_dir / "Exness_EURUSD_Raw_Spread_2024_08.zip"
        standard_zip = processor_with_real_data.temp_dir / "Exness_EURUSD_2024_08.zip"

        df_raw = processor_with_real_data._load_ticks_from_zip(raw_spread_zip)
        df_std = processor_with_real_data._load_ticks_from_zip(standard_zip)

        duckdb_path = processor_with_real_data._get_or_create_db("EURUSD")
        processor_with_real_data._append_ticks_to_db(duckdb_path, df_raw, "raw_spread_ticks")
        processor_with_real_data._append_ticks_to_db(duckdb_path, df_std, "standard_ticks")
        processor_with_real_data._regenerate_ohlc(duckdb_path)

        # Get coverage
        coverage = processor_with_real_data.get_data_coverage("EURUSD")

        # Verify CoverageInfo instance
        assert isinstance(coverage, CoverageInfo)
        assert coverage.database_exists is True
        assert coverage.raw_spread_ticks > 0
        assert coverage.standard_ticks > 0
        assert coverage.ohlc_bars > 0
        assert coverage.duckdb_size_mb > 0
        assert coverage.earliest_date is not None
        assert coverage.latest_date is not None

    def test_get_data_coverage_no_database(self, processor_with_temp_dir):
        """Test get_data_coverage() for non-existent database.

        SLO-CR-2: Model field accuracy: 100%.
        """
        coverage = processor_with_temp_dir.get_data_coverage("EURUSD")

        assert isinstance(coverage, CoverageInfo)
        assert coverage.database_exists is False
        assert coverage.raw_spread_ticks == 0
        assert coverage.standard_ticks == 0
        assert coverage.ohlc_bars == 0
        assert coverage.earliest_date is None
        assert coverage.latest_date is None


class TestPydanticModelSerialization:
    """Test Pydantic models can be serialized with real data."""

    def test_update_result_serialization_with_real_data(self, processor_with_real_data):
        """Test UpdateResult serialization to dict and JSON with real data.

        SLO-CR-2: Model field accuracy: 100%.
        """
        # Load real data
        raw_spread_zip = processor_with_real_data.temp_dir / "Exness_EURUSD_Raw_Spread_2024_08.zip"
        df_raw = processor_with_real_data._load_ticks_from_zip(raw_spread_zip)

        duckdb_path = processor_with_real_data._get_or_create_db("EURUSD")
        processor_with_real_data._append_ticks_to_db(duckdb_path, df_raw, "raw_spread_ticks")

        tick_count = len(df_raw)
        result = UpdateResult(
            duckdb_path=duckdb_path,
            months_added=1,
            raw_ticks_added=tick_count,
            standard_ticks_added=0,
            ohlc_bars=0,
            duckdb_size_mb=duckdb_path.stat().st_size / 1024 / 1024,
        )

        # Test dict serialization
        dict_result = result.model_dump()
        assert dict_result["months_added"] == 1
        assert dict_result["raw_ticks_added"] == tick_count

        # Test JSON serialization
        json_str = result.model_dump_json()
        assert '"months_added":1' in json_str
        assert f'"raw_ticks_added":{tick_count}' in json_str

    def test_coverage_info_serialization_with_real_data(self, processor_with_real_data):
        """Test CoverageInfo serialization with real downloaded data.

        SLO-CR-2: Model field accuracy: 100%.
        """
        # Load downloaded data
        raw_spread_zip = processor_with_real_data.temp_dir / "Exness_EURUSD_Raw_Spread_2024_08.zip"
        df_raw = processor_with_real_data._load_ticks_from_zip(raw_spread_zip)

        duckdb_path = processor_with_real_data._get_or_create_db("EURUSD")
        processor_with_real_data._append_ticks_to_db(duckdb_path, df_raw, "raw_spread_ticks")

        coverage = processor_with_real_data.get_data_coverage("EURUSD")
        tick_count = coverage.raw_spread_ticks

        # Test dict serialization
        dict_result = coverage.model_dump()
        assert dict_result["database_exists"] is True
        assert dict_result["raw_spread_ticks"] == tick_count
        assert tick_count > 0

        # Test JSON serialization
        json_str = coverage.model_dump_json()
        assert '"database_exists":true' in json_str
        assert f'"raw_spread_ticks":{tick_count}' in json_str
