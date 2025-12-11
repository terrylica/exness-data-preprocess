"""Pydantic model validation tests for v2.0.0.

ADR: 2025-12-11-duckdb-removal-clickhouse

SLO Coverage:
- SLO-CR-1: Pydantic models validate all fields per schema: 100% validation coverage
- SLO-CR-2: UpdateResult/CoverageInfo match processor return data: 100% field accuracy
- SLO-CR-3: Literal types enforce only valid values: 100% type constraint enforcement
- SLO-CR-4: JSON Schema generation produces valid schemas: 100% schema validity
"""

import pytest
from pydantic import ValidationError

from exness_data_preprocess.models import CoverageInfo, UpdateResult


class TestUpdateResult:
    """Test UpdateResult Pydantic model validation."""

    def test_update_result_creation(self):
        """Test UpdateResult model instantiation with v2.0.0 fields.

        SLO-CR-1: Pydantic models validate all fields per schema.
        """
        result = UpdateResult(
            database="exness",
            months_added=12,
            raw_ticks_added=18600000,
            standard_ticks_added=19600000,
            ohlc_bars=413000,
            storage_bytes=2181038080,
        )
        assert result.months_added == 12
        assert result.database == "exness"
        assert result.raw_ticks_added == 18600000
        assert result.standard_ticks_added == 19600000
        assert result.ohlc_bars == 413000
        assert result.storage_bytes == 2181038080

    def test_update_result_validation_negative_months(self):
        """Test UpdateResult field validation (months_added ge=0).

        SLO-CR-3: Type constraint enforcement: 100%.
        """
        with pytest.raises(ValidationError) as exc_info:
            UpdateResult(
                database="exness",
                months_added=-1,  # Should fail (ge=0)
                raw_ticks_added=100,
                standard_ticks_added=100,
                ohlc_bars=50,
                storage_bytes=10000,
            )

        # SLO-OB-3: ValidationError includes field name
        assert "months_added" in str(exc_info.value)

    def test_update_result_validation_negative_ticks(self):
        """Test UpdateResult field validation (raw_ticks_added ge=0).

        SLO-CR-3: Type constraint enforcement: 100%.
        """
        with pytest.raises(ValidationError) as exc_info:
            UpdateResult(
                database="exness",
                months_added=12,
                raw_ticks_added=-1000,  # Should fail (ge=0)
                standard_ticks_added=100,
                ohlc_bars=50,
                storage_bytes=10000,
            )

        assert "raw_ticks_added" in str(exc_info.value)

    def test_update_result_validation_negative_storage(self):
        """Test UpdateResult field validation (storage_bytes ge=0).

        SLO-CR-3: Type constraint enforcement: 100%.
        """
        with pytest.raises(ValidationError) as exc_info:
            UpdateResult(
                database="exness",
                months_added=12,
                raw_ticks_added=100,
                standard_ticks_added=100,
                ohlc_bars=50,
                storage_bytes=-5,  # Should fail (ge=0)
            )

        assert "storage_bytes" in str(exc_info.value)

    def test_update_result_serialization_dict(self):
        """Test UpdateResult serialization to dict.

        SLO-CR-2: Model field accuracy: 100%.
        """
        result = UpdateResult(
            database="exness",
            months_added=12,
            raw_ticks_added=100000,
            standard_ticks_added=100000,
            ohlc_bars=5000,
            storage_bytes=157810688,
        )

        # Test dict conversion
        dict_result = result.model_dump()
        assert dict_result["months_added"] == 12
        assert dict_result["raw_ticks_added"] == 100000
        assert dict_result["standard_ticks_added"] == 100000
        assert dict_result["ohlc_bars"] == 5000
        assert dict_result["storage_bytes"] == 157810688
        assert dict_result["database"] == "exness"

    def test_update_result_serialization_json(self):
        """Test UpdateResult serialization to JSON.

        SLO-CR-2: Model field accuracy: 100%.
        """
        result = UpdateResult(
            database="exness",
            months_added=12,
            raw_ticks_added=100000,
            standard_ticks_added=100000,
            ohlc_bars=5000,
            storage_bytes=157810688,
        )

        # Test JSON serialization
        json_str = result.model_dump_json()
        assert '"months_added":12' in json_str
        assert '"raw_ticks_added":100000' in json_str
        assert '"standard_ticks_added":100000' in json_str
        assert '"ohlc_bars":5000' in json_str
        assert '"storage_bytes":157810688' in json_str

    def test_update_result_json_schema(self):
        """Test UpdateResult JSON Schema generation.

        SLO-CR-4: JSON Schema validity: 100%.
        """
        schema = UpdateResult.model_json_schema()

        # Verify schema structure
        assert "properties" in schema
        assert "required" in schema

        # Verify all fields present (v2.0.0 fields)
        assert "database" in schema["properties"]
        assert "months_added" in schema["properties"]
        assert "raw_ticks_added" in schema["properties"]
        assert "standard_ticks_added" in schema["properties"]
        assert "ohlc_bars" in schema["properties"]
        assert "storage_bytes" in schema["properties"]

        # Verify field types
        assert schema["properties"]["database"]["type"] == "string"
        assert schema["properties"]["months_added"]["type"] == "integer"
        assert schema["properties"]["raw_ticks_added"]["type"] == "integer"
        assert schema["properties"]["standard_ticks_added"]["type"] == "integer"
        assert schema["properties"]["ohlc_bars"]["type"] == "integer"
        assert schema["properties"]["storage_bytes"]["type"] == "integer"

        # Verify constraints (ge=0)
        assert schema["properties"]["months_added"]["minimum"] == 0
        assert schema["properties"]["raw_ticks_added"]["minimum"] == 0
        assert schema["properties"]["standard_ticks_added"]["minimum"] == 0
        assert schema["properties"]["ohlc_bars"]["minimum"] == 0
        assert schema["properties"]["storage_bytes"]["minimum"] == 0

        # Verify descriptions
        assert "description" in schema["properties"]["months_added"]
        assert "description" in schema["properties"]["storage_bytes"]


class TestCoverageInfo:
    """Test CoverageInfo Pydantic model validation."""

    def test_coverage_info_creation(self):
        """Test CoverageInfo model instantiation with v2.0.0 fields.

        SLO-CR-1: Pydantic models validate all fields per schema.
        """
        coverage = CoverageInfo(
            database="exness",
            storage_bytes=2181038080,
            raw_spread_ticks=18600000,
            standard_ticks=19600000,
            ohlc_bars=413000,
            earliest_date="2024-10-01 00:00:00+00:00",
            latest_date="2025-10-31 23:59:59+00:00",
            date_range_days=395,
        )

        assert coverage.database == "exness"
        assert coverage.storage_bytes == 2181038080
        assert coverage.raw_spread_ticks == 18600000
        assert coverage.standard_ticks == 19600000
        assert coverage.ohlc_bars == 413000
        assert coverage.earliest_date == "2024-10-01 00:00:00+00:00"
        assert coverage.latest_date == "2025-10-31 23:59:59+00:00"
        assert coverage.date_range_days == 395

    def test_coverage_info_optional_fields(self):
        """Test CoverageInfo with None values for optional fields.

        SLO-CR-1: Pydantic models validate all fields per schema.
        """
        coverage = CoverageInfo(
            database="exness",
            storage_bytes=0,
            raw_spread_ticks=0,
            standard_ticks=0,
            ohlc_bars=0,
            earliest_date=None,  # Optional field
            latest_date=None,  # Optional field
            date_range_days=0,
        )

        assert coverage.database == "exness"
        assert coverage.earliest_date is None
        assert coverage.latest_date is None
        assert coverage.raw_spread_ticks == 0
        assert coverage.standard_ticks == 0

    def test_coverage_info_validation_negative_storage(self):
        """Test CoverageInfo field validation (storage_bytes ge=0).

        SLO-CR-3: Type constraint enforcement: 100%.
        """
        with pytest.raises(ValidationError) as exc_info:
            CoverageInfo(
                database="exness",
                storage_bytes=-10,  # Should fail (ge=0)
                raw_spread_ticks=100,
                standard_ticks=100,
                ohlc_bars=50,
                earliest_date="2024-01-01",
                latest_date="2024-12-31",
                date_range_days=365,
            )

        assert "storage_bytes" in str(exc_info.value)

    def test_coverage_info_validation_negative_ticks(self):
        """Test CoverageInfo field validation (raw_spread_ticks ge=0).

        SLO-CR-3: Type constraint enforcement: 100%.
        """
        with pytest.raises(ValidationError) as exc_info:
            CoverageInfo(
                database="exness",
                storage_bytes=10000,
                raw_spread_ticks=-1000,  # Should fail (ge=0)
                standard_ticks=100,
                ohlc_bars=50,
                earliest_date="2024-01-01",
                latest_date="2024-12-31",
                date_range_days=365,
            )

        assert "raw_spread_ticks" in str(exc_info.value)

    def test_coverage_info_serialization_dict(self):
        """Test CoverageInfo serialization to dict.

        SLO-CR-2: Model field accuracy: 100%.
        """
        coverage = CoverageInfo(
            database="exness",
            storage_bytes=2181038080,
            raw_spread_ticks=18600000,
            standard_ticks=19600000,
            ohlc_bars=413000,
            earliest_date="2024-10-01 00:00:00+00:00",
            latest_date="2025-10-31 23:59:59+00:00",
            date_range_days=395,
        )

        dict_result = coverage.model_dump()
        assert dict_result["database"] == "exness"
        assert dict_result["raw_spread_ticks"] == 18600000
        assert dict_result["standard_ticks"] == 19600000
        assert dict_result["ohlc_bars"] == 413000
        assert dict_result["date_range_days"] == 395

    def test_coverage_info_json_schema(self):
        """Test CoverageInfo JSON Schema generation.

        SLO-CR-4: JSON Schema validity: 100%.
        """
        schema = CoverageInfo.model_json_schema()

        # Verify schema structure
        assert "properties" in schema
        assert "required" in schema

        # Verify all fields present (v2.0.0 fields)
        assert "database" in schema["properties"]
        assert "storage_bytes" in schema["properties"]
        assert "raw_spread_ticks" in schema["properties"]
        assert "standard_ticks" in schema["properties"]
        assert "ohlc_bars" in schema["properties"]
        assert "earliest_date" in schema["properties"]
        assert "latest_date" in schema["properties"]
        assert "date_range_days" in schema["properties"]

        # Verify field types
        assert schema["properties"]["database"]["type"] == "string"
        assert schema["properties"]["storage_bytes"]["type"] == "integer"
        assert schema["properties"]["raw_spread_ticks"]["type"] == "integer"
        assert schema["properties"]["standard_ticks"]["type"] == "integer"
        assert schema["properties"]["ohlc_bars"]["type"] == "integer"
        assert schema["properties"]["date_range_days"]["type"] == "integer"

        # Verify constraints (ge=0)
        assert schema["properties"]["storage_bytes"]["minimum"] == 0
        assert schema["properties"]["raw_spread_ticks"]["minimum"] == 0
        assert schema["properties"]["standard_ticks"]["minimum"] == 0
        assert schema["properties"]["ohlc_bars"]["minimum"] == 0
        assert schema["properties"]["date_range_days"]["minimum"] == 0

        # Verify optional fields (earliest_date, latest_date)
        # Optional fields are represented with anyOf: [type, null]
        assert "anyOf" in schema["properties"]["earliest_date"] or schema["properties"][
            "earliest_date"
        ].get("type") in ["string", ["string", "null"]]
        assert "anyOf" in schema["properties"]["latest_date"] or schema["properties"][
            "latest_date"
        ].get("type") in ["string", ["string", "null"]]
