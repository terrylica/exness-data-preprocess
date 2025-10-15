"""Functional regression tests for v2.0.0 behavior preservation (v2.1.0).

TRUE End-to-End Testing: Downloads from https://ticks.ex2archive.com/ - No mocking.

SLO Coverage:
- SLO-CR-5: v2.0.0 functional behavior preserved: 0 regressions detected
- SLO-AV-2: Database connections close properly: 100% cleanup rate
- SLO-MA-3: Tests independent (no execution order dependency): 100% isolation
- SLO-MA-4: True end-to-end testing from online source: Downloads real Exness data
"""

import pytest
from pathlib import Path

import pandas as pd

from exness_data_preprocess.models import CoverageInfo, UpdateResult
from exness_data_preprocess.processor import ExnessDataProcessor


class TestSingleFileDatabaseCreation:
    """Test v2.0.0 single-file database architecture with real data."""

    def test_single_file_database_created(self, processor_with_real_data):
        """Test single DuckDB file is created (not monthly files) with real data.

        SLO-CR-5: v2.0.0 functional behavior preserved: 0 regressions.
        SLO-MA-4: No mocking - downloads and processes real Exness data from online source.
        """
        # Load real ZIP files
        raw_spread_zip = processor_with_real_data.temp_dir / "Exness_EURUSD_Raw_Spread_2024_08.zip"
        df_raw = processor_with_real_data._load_ticks_from_zip(raw_spread_zip)

        # Create database
        duckdb_path = processor_with_real_data._get_or_create_db("EURUSD")
        processor_with_real_data._append_ticks_to_db(duckdb_path, df_raw, "raw_spread_ticks")

        # Verify single database file exists
        assert duckdb_path.exists(), "Single database file should exist"
        assert duckdb_path.name == "eurusd.duckdb"
        assert duckdb_path.parent == processor_with_real_data.base_dir

    def test_no_monthly_files_created(self, processor_with_real_data):
        """Test no monthly DuckDB files are created (v1.0.0 legacy pattern).

        SLO-CR-5: v2.0.0 functional behavior preserved: 0 regressions.
        """
        # Load real data
        raw_spread_zip = processor_with_real_data.temp_dir / "Exness_EURUSD_Raw_Spread_2024_08.zip"
        df_raw = processor_with_real_data._load_ticks_from_zip(raw_spread_zip)

        duckdb_path = processor_with_real_data._get_or_create_db("EURUSD")
        processor_with_real_data._append_ticks_to_db(duckdb_path, df_raw, "raw_spread_ticks")

        # Verify no monthly files exist (v1.0.0 pattern: eurusd_ohlc_2024_08.duckdb)
        monthly_pattern = list(processor_with_real_data.base_dir.glob("eurusd_*_2024_*.duckdb"))
        assert len(monthly_pattern) == 0, "No monthly DuckDB files should exist"


class TestPhase7OHLCSchema:
    """Test Phase7 9-column OHLC schema with real data."""

    def test_phase7_nine_column_schema(self, processor_with_real_data):
        """Test Phase7 9-column OHLC schema is preserved with real data.

        SLO-CR-5: v2.0.0 functional behavior preserved: 0 regressions.
        SLO-MA-4: No mocking - downloads and uses real Exness data from online source.
        """
        if not processor_with_real_data.has_standard_data:
            pytest.skip("Standard variant not available for this month")

        # Load real data
        raw_spread_zip = processor_with_real_data.temp_dir / "Exness_EURUSD_Raw_Spread_2024_08.zip"
        standard_zip = processor_with_real_data.temp_dir / "Exness_EURUSD_2024_08.zip"

        df_raw = processor_with_real_data._load_ticks_from_zip(raw_spread_zip)
        df_std = processor_with_real_data._load_ticks_from_zip(standard_zip)

        # Create database and regenerate OHLC
        duckdb_path = processor_with_real_data._get_or_create_db("EURUSD")
        processor_with_real_data._append_ticks_to_db(duckdb_path, df_raw, "raw_spread_ticks")
        processor_with_real_data._append_ticks_to_db(duckdb_path, df_std, "standard_ticks")
        processor_with_real_data._regenerate_ohlc(duckdb_path)

        # Query OHLC data
        df = processor_with_real_data.query_ohlc(
            pair="EURUSD",
            timeframe="1m"
        )

        # Verify Phase7 schema (v1.2.0: 13 columns) - using schema module for DRY
        from exness_data_preprocess.schema import OHLCSchema

        required_cols = OHLCSchema.get_required_columns()

        # Validate all required columns exist (flexible, allows future additions)
        for col in required_cols:
            assert col in df.columns, f"Missing required column: {col}"

        # Validate no unexpected columns
        unexpected = set(df.columns) - set(required_cols)
        assert not unexpected, f"Unexpected columns: {unexpected}"

        assert len(df) > 0, "Should have OHLC bars"

    def test_phase7_dual_spreads(self, processor_with_real_data):
        """Test Phase7 dual spreads are calculated correctly.

        SLO-CR-5: v2.0.0 functional behavior preserved: 0 regressions.
        """
        if not processor_with_real_data.has_standard_data:
            pytest.skip("Standard variant not available for this month")

        # Load real data
        raw_spread_zip = processor_with_real_data.temp_dir / "Exness_EURUSD_Raw_Spread_2024_08.zip"
        standard_zip = processor_with_real_data.temp_dir / "Exness_EURUSD_2024_08.zip"

        df_raw = processor_with_real_data._load_ticks_from_zip(raw_spread_zip)
        df_std = processor_with_real_data._load_ticks_from_zip(standard_zip)

        duckdb_path = processor_with_real_data._get_or_create_db("EURUSD")
        processor_with_real_data._append_ticks_to_db(duckdb_path, df_raw, "raw_spread_ticks")
        processor_with_real_data._append_ticks_to_db(duckdb_path, df_std, "standard_ticks")
        processor_with_real_data._regenerate_ohlc(duckdb_path)

        # Query OHLC
        df = processor_with_real_data.query_ohlc(pair="EURUSD", timeframe="1m")

        # Verify dual spread columns exist and have valid data
        assert "raw_spread_avg" in df.columns
        assert "standard_spread_avg" in df.columns
        assert df["raw_spread_avg"].notna().any(), "Should have raw spread data"
        assert df["standard_spread_avg"].notna().any(), "Should have standard spread data"

        # Verify tick counts exist and have reasonable values
        assert "tick_count_raw_spread" in df.columns
        assert "tick_count_standard" in df.columns
        assert df["tick_count_raw_spread"].sum() > 0, "Should have tick count data"
        assert df["tick_count_standard"].sum() > 0, "Should have tick count data"
        assert df["tick_count_raw_spread"].min() > 0, "All bars should have at least 1 Raw_Spread tick"
        # Standard ticks may be 0 for some bars due to LEFT JOIN (correct behavior)
        assert df["tick_count_standard"].min() >= 0, "Tick counts should be non-negative"


class TestQueryMethods:
    """Test v2.0.0 query methods with real data."""

    def test_query_ticks_returns_real_data(self, processor_with_real_data):
        """Test query_ticks() returns real tick data.

        SLO-CR-5: v2.0.0 functional behavior preserved: 0 regressions.
        SLO-MA-4: No mocking - queries real database.
        """
        # Load real data
        raw_spread_zip = processor_with_real_data.temp_dir / "Exness_EURUSD_Raw_Spread_2024_08.zip"
        df_raw = processor_with_real_data._load_ticks_from_zip(raw_spread_zip)

        duckdb_path = processor_with_real_data._get_or_create_db("EURUSD")
        processor_with_real_data._append_ticks_to_db(duckdb_path, df_raw, "raw_spread_ticks")

        # Query ticks
        df = processor_with_real_data.query_ticks(
            pair="EURUSD",
            variant="raw_spread"
        )

        # Verify tick data structure
        assert len(df) > 0, "Should have ticks from downloaded data"
        assert "Timestamp" in df.columns
        assert "Bid" in df.columns
        assert "Ask" in df.columns

        # Verify data types
        assert pd.api.types.is_datetime64_any_dtype(df["Timestamp"])
        assert pd.api.types.is_float_dtype(df["Bid"])
        assert pd.api.types.is_float_dtype(df["Ask"])

    def test_query_ohlc_returns_dataframe(self, processor_with_real_data):
        """Test query_ohlc() returns DataFrame with real data.

        SLO-CR-5: v2.0.0 functional behavior preserved: 0 regressions.
        """
        if not processor_with_real_data.has_standard_data:
            pytest.skip("Standard variant not available for this month")

        # Load real data
        raw_spread_zip = processor_with_real_data.temp_dir / "Exness_EURUSD_Raw_Spread_2024_08.zip"
        standard_zip = processor_with_real_data.temp_dir / "Exness_EURUSD_2024_08.zip"

        df_raw = processor_with_real_data._load_ticks_from_zip(raw_spread_zip)
        df_std = processor_with_real_data._load_ticks_from_zip(standard_zip)

        duckdb_path = processor_with_real_data._get_or_create_db("EURUSD")
        processor_with_real_data._append_ticks_to_db(duckdb_path, df_raw, "raw_spread_ticks")
        processor_with_real_data._append_ticks_to_db(duckdb_path, df_std, "standard_ticks")
        processor_with_real_data._regenerate_ohlc(duckdb_path)

        # Query OHLC
        df = processor_with_real_data.query_ohlc(
            pair="EURUSD",
            timeframe="1m"
        )

        # Verify DataFrame
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0, "Should have OHLC bars"

        # Verify OHLC columns
        assert "Open" in df.columns
        assert "High" in df.columns
        assert "Low" in df.columns
        assert "Close" in df.columns

    def test_query_ohlc_resampling(self, processor_with_real_data):
        """Test OHLC on-demand resampling works with real data.

        SLO-CR-5: v2.0.0 functional behavior preserved: 0 regressions.
        """
        if not processor_with_real_data.has_standard_data:
            pytest.skip("Standard variant not available for this month")

        # Load real data
        raw_spread_zip = processor_with_real_data.temp_dir / "Exness_EURUSD_Raw_Spread_2024_08.zip"
        standard_zip = processor_with_real_data.temp_dir / "Exness_EURUSD_2024_08.zip"

        df_raw = processor_with_real_data._load_ticks_from_zip(raw_spread_zip)
        df_std = processor_with_real_data._load_ticks_from_zip(standard_zip)

        duckdb_path = processor_with_real_data._get_or_create_db("EURUSD")
        processor_with_real_data._append_ticks_to_db(duckdb_path, df_raw, "raw_spread_ticks")
        processor_with_real_data._append_ticks_to_db(duckdb_path, df_std, "standard_ticks")
        processor_with_real_data._regenerate_ohlc(duckdb_path)

        # Query at different timeframes
        df_1m = processor_with_real_data.query_ohlc(pair="EURUSD", timeframe="1m")
        df_5m = processor_with_real_data.query_ohlc(pair="EURUSD", timeframe="5m")

        # Verify resampling
        assert len(df_5m) <= len(df_1m), "5m bars should be <= 1m bars"
        assert len(df_1m) > 0
        assert len(df_5m) > 0


class TestCoverageInfo:
    """Test get_data_coverage() behavior with real data."""

    def test_coverage_info_for_existing_database(self, processor_with_real_data):
        """Test get_data_coverage() returns correct info for existing database with real data.

        SLO-CR-5: v2.0.0 functional behavior preserved: 0 regressions.
        """
        if not processor_with_real_data.has_standard_data:
            pytest.skip("Standard variant not available for this month")

        # Load real data
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

        # Verify coverage info
        assert isinstance(coverage, CoverageInfo)
        assert coverage.database_exists is True
        assert coverage.raw_spread_ticks > 0
        assert coverage.standard_ticks > 0
        assert coverage.ohlc_bars > 0
        assert coverage.duckdb_size_mb > 0
        assert coverage.earliest_date is not None
        assert coverage.latest_date is not None
        assert coverage.date_range_days >= 0

    def test_coverage_info_for_non_existent_database(self, processor_with_temp_dir):
        """Test get_data_coverage() returns correct info for non-existent database.

        SLO-CR-5: v2.0.0 functional behavior preserved: 0 regressions.
        """
        # Get coverage for non-existent database
        coverage = processor_with_temp_dir.get_data_coverage("EURUSD")

        # Verify coverage info
        assert isinstance(coverage, CoverageInfo)
        assert coverage.database_exists is False
        assert coverage.raw_spread_ticks == 0
        assert coverage.standard_ticks == 0
        assert coverage.ohlc_bars == 0
        assert coverage.duckdb_size_mb == 0
        assert coverage.earliest_date is None
        assert coverage.latest_date is None
        assert coverage.date_range_days == 0


class TestPRIMARYKEYDuplicatePrevention:
    """Test PRIMARY KEY constraints prevent duplicate ticks with real data."""

    def test_primary_key_prevents_duplicates(self, processor_with_real_data):
        """Test PRIMARY KEY constraints prevent duplicate ticks.

        SLO-CR-5: v2.0.0 functional behavior preserved: 0 regressions.
        SLO-MA-4: No mocking - tests real database constraints.
        """
        # Load real data
        raw_spread_zip = processor_with_real_data.temp_dir / "Exness_EURUSD_Raw_Spread_2024_08.zip"
        df_raw = processor_with_real_data._load_ticks_from_zip(raw_spread_zip)

        duckdb_path = processor_with_real_data._get_or_create_db("EURUSD")

        # Append ticks first time
        processor_with_real_data._append_ticks_to_db(duckdb_path, df_raw, "raw_spread_ticks")

        import duckdb
        conn = duckdb.connect(str(duckdb_path), read_only=True)
        count1 = conn.execute("SELECT COUNT(*) FROM raw_spread_ticks").fetchone()[0]
        conn.close()

        # Use actual database count as baseline (source CSV may have duplicates)
        assert count1 > 0, "Should have ticks after first insert"

        # Try to append same ticks again (should not duplicate due to PRIMARY KEY)
        processor_with_real_data._append_ticks_to_db(duckdb_path, df_raw, "raw_spread_ticks")

        conn = duckdb.connect(str(duckdb_path), read_only=True)
        count2 = conn.execute("SELECT COUNT(*) FROM raw_spread_ticks").fetchone()[0]
        conn.close()

        assert count2 == count1, f"PRIMARY KEY should prevent duplicates (still {count1} ticks, not {count2})"
