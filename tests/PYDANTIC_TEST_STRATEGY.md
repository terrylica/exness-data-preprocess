# Pydantic Refactoring - Regression Test Strategy (v2.1.0)

**Status**: Design Complete - Ready for Implementation
**Date**: 2025-10-12
**Purpose**: Comprehensive regression testing for Pydantic v2 refactoring

---

## Executive Summary

The v2.1.0 Pydantic refactoring introduces **type-safe API responses** with Pydantic models. This test strategy ensures:

1. **Zero Functional Regressions**: All v2.0.0 functionality preserved
2. **Pydantic Validation**: All models validate correctly
3. **Type Safety**: Literal types enforce valid values
4. **AI Discovery**: JSON Schema generation works

**No Backward Compatibility Testing**: Dict access patterns (`result['key']`) removed - only attribute access (`result.key`) supported.

---

## Test Categories

### Category 1: Pydantic Model Validation (NEW)

**File**: `tests/test_models.py`

Tests the new Pydantic models for correctness, validation, and serialization.

#### 1.1 UpdateResult Model
```python
def test_update_result_creation():
    """Test UpdateResult model instantiation."""
    result = UpdateResult(
        duckdb_path=Path("/tmp/eurusd.duckdb"),
        months_added=12,
        raw_ticks_added=18600000,
        standard_ticks_added=19600000,
        ohlc_bars=413000,
        duckdb_size_mb=2080.5
    )
    assert result.months_added == 12
    assert result.duckdb_path == Path("/tmp/eurusd.duckdb")

def test_update_result_validation_constraints():
    """Test UpdateResult field validation (ge=0)."""
    with pytest.raises(ValidationError):
        UpdateResult(
            duckdb_path=Path("/tmp/test.duckdb"),
            months_added=-1,  # Should fail (ge=0)
            raw_ticks_added=100,
            standard_ticks_added=100,
            ohlc_bars=50,
            duckdb_size_mb=10.0
        )

def test_update_result_serialization():
    """Test UpdateResult serialization."""
    result = UpdateResult(
        duckdb_path=Path("/tmp/eurusd.duckdb"),
        months_added=12,
        raw_ticks_added=100000,
        standard_ticks_added=100000,
        ohlc_bars=5000,
        duckdb_size_mb=150.5
    )
    # Test dict conversion
    dict_result = result.model_dump()
    assert dict_result['months_added'] == 12

    # Test JSON serialization
    json_str = result.model_dump_json()
    assert '"months_added":12' in json_str

def test_update_result_json_schema():
    """Test UpdateResult JSON Schema generation."""
    schema = UpdateResult.model_json_schema()
    assert 'properties' in schema
    assert 'months_added' in schema['properties']
    assert schema['properties']['months_added']['type'] == 'integer'
```

#### 1.2 CoverageInfo Model
```python
def test_coverage_info_creation():
    """Test CoverageInfo model instantiation."""
    coverage = CoverageInfo(
        database_exists=True,
        duckdb_path="/tmp/eurusd.duckdb",
        duckdb_size_mb=2080.5,
        raw_spread_ticks=18600000,
        standard_ticks=19600000,
        ohlc_bars=413000,
        earliest_date="2024-10-01 00:00:00+00:00",
        latest_date="2025-10-31 23:59:59+00:00",
        date_range_days=395
    )
    assert coverage.database_exists == True
    assert coverage.raw_spread_ticks == 18600000

def test_coverage_info_optional_fields():
    """Test CoverageInfo with None values."""
    coverage = CoverageInfo(
        database_exists=False,
        duckdb_path="/tmp/missing.duckdb",
        duckdb_size_mb=0,
        raw_spread_ticks=0,
        standard_ticks=0,
        ohlc_bars=0,
        earliest_date=None,  # Optional field
        latest_date=None,    # Optional field
        date_range_days=0
    )
    assert coverage.earliest_date is None
    assert coverage.latest_date is None
```

### Category 2: Type Safety Tests (NEW)

**File**: `tests/test_types.py`

Tests Literal types and helper functions.

#### 2.1 PairType Tests
```python
def test_pair_type_valid_values():
    """Test valid PairType values."""
    from typing import get_args
    from exness_data_preprocess.models import PairType

    valid_pairs = get_args(PairType)
    assert "EURUSD" in valid_pairs
    assert "GBPUSD" in valid_pairs
    assert len(valid_pairs) == 10  # Exact count

def test_supported_pairs_helper():
    """Test supported_pairs() helper function."""
    import exness_data_preprocess as edp

    pairs = edp.supported_pairs()
    assert isinstance(pairs, tuple)
    assert "EURUSD" in pairs
    assert "XAUUSD" in pairs
```

#### 2.2 TimeframeType Tests
```python
def test_timeframe_type_valid_values():
    """Test valid TimeframeType values."""
    from typing import get_args
    from exness_data_preprocess.models import TimeframeType

    valid_timeframes = get_args(TimeframeType)
    assert "1m" in valid_timeframes
    assert "1h" in valid_timeframes
    assert "1d" in valid_timeframes
    assert len(valid_timeframes) == 7  # 1m, 5m, 15m, 30m, 1h, 4h, 1d
```

#### 2.3 VariantType Tests
```python
def test_variant_type_valid_values():
    """Test valid VariantType values."""
    from typing import get_args
    from exness_data_preprocess.models import VariantType

    valid_variants = get_args(VariantType)
    assert "raw_spread" in valid_variants
    assert "standard" in valid_variants
    assert len(valid_variants) == 2
```

### Category 3: Integration Tests (REGRESSION)

**File**: `tests/test_processor_pydantic.py`

Tests that processor methods return Pydantic models correctly.

#### 3.1 update_data() Returns UpdateResult
```python
def test_update_data_returns_update_result(processor_with_temp_dir, mock_exness_zip):
    """Test update_data() returns UpdateResult instance."""
    from exness_data_preprocess.models import UpdateResult

    # Mock network download to avoid real downloads
    # ... (implementation details)

    result = processor_with_temp_dir.update_data(
        pair="EURUSD",
        start_date="2024-09-01"
    )

    # Verify type
    assert isinstance(result, UpdateResult)

    # Verify attribute access works
    assert isinstance(result.months_added, int)
    assert result.months_added >= 0
    assert isinstance(result.duckdb_path, Path)
    assert isinstance(result.duckdb_size_mb, float)
```

#### 3.2 get_data_coverage() Returns CoverageInfo
```python
def test_get_data_coverage_returns_coverage_info(processor_with_temp_dir):
    """Test get_data_coverage() returns CoverageInfo instance."""
    from exness_data_preprocess.models import CoverageInfo

    coverage = processor_with_temp_dir.get_data_coverage("EURUSD")

    # Verify type
    assert isinstance(coverage, CoverageInfo)

    # Verify attribute access works
    assert isinstance(coverage.database_exists, bool)
    assert isinstance(coverage.raw_spread_ticks, int)
    assert coverage.raw_spread_ticks >= 0
```

### Category 4: Functional Regression Tests

**File**: `tests/test_functional_regression.py`

Tests that all v2.0.0 functionality still works after Pydantic refactoring.

#### 4.1 Database Creation
```python
def test_single_file_database_creation(processor_with_temp_dir):
    """Test single DuckDB file is created (not monthly files)."""
    # Based on test_refactored_processor.py reference
    result = processor_with_temp_dir.update_data(
        pair="EURUSD",
        start_date="2024-09-01"
    )

    duckdb_path = processor_with_temp_dir.base_dir / "eurusd.duckdb"
    assert duckdb_path.exists(), "Single database file should exist"
    assert result.months_added >= 0
```

#### 4.2 Incremental Updates
```python
def test_incremental_update_zero_months(processor_with_temp_dir):
    """Test incremental update returns 0 months_added when up to date."""
    # First update
    result1 = processor_with_temp_dir.update_data(
        pair="EURUSD",
        start_date="2024-09-01"
    )

    # Second update (should be up to date)
    result2 = processor_with_temp_dir.update_data(
        pair="EURUSD",
        start_date="2024-09-01"
    )

    assert result2.months_added == 0, "Should be up to date"
```

#### 4.3 Phase7 9-Column OHLC Schema
```python
def test_phase7_ohlc_schema(processor_with_temp_dir):
    """Test Phase7 9-column OHLC schema is preserved."""
    df = processor_with_temp_dir.query_ohlc(
        pair="EURUSD",
        timeframe="1m",
        start_date="2024-09-01",
        end_date="2024-09-01"
    )

    expected_cols = [
        "Timestamp", "Open", "High", "Low", "Close",
        "raw_spread_avg", "standard_spread_avg",
        "tick_count_raw_spread", "tick_count_standard"
    ]

    for col in expected_cols:
        assert col in df.columns, f"Missing column: {col}"
```

#### 4.4 Query Methods
```python
def test_query_ticks_with_date_range(processor_with_temp_dir):
    """Test query_ticks() with date range filtering."""
    df = processor_with_temp_dir.query_ticks(
        pair="EURUSD",
        variant="raw_spread",
        start_date="2024-09-01",
        end_date="2024-09-30"
    )

    assert len(df) > 0, "Should have ticks"
    assert "Timestamp" in df.columns
    assert "Bid" in df.columns
    assert "Ask" in df.columns

def test_query_ohlc_resampling(processor_with_temp_dir):
    """Test OHLC on-demand resampling works."""
    df_1m = processor_with_temp_dir.query_ohlc(
        pair="EURUSD",
        timeframe="1m",
        start_date="2024-09-01",
        end_date="2024-09-01"
    )

    df_1h = processor_with_temp_dir.query_ohlc(
        pair="EURUSD",
        timeframe="1h",
        start_date="2024-09-01",
        end_date="2024-09-01"
    )

    # 1h should have fewer bars than 1m
    assert len(df_1h) <= len(df_1m), "1h bars should be <= 1m bars"
```

---

## Test Fixtures Enhancement

**File**: `tests/conftest.py` (add new fixtures)

```python
@pytest.fixture
def sample_update_result():
    """Sample UpdateResult for testing."""
    from exness_data_preprocess.models import UpdateResult
    from pathlib import Path

    return UpdateResult(
        duckdb_path=Path("/tmp/test.duckdb"),
        months_added=12,
        raw_ticks_added=18600000,
        standard_ticks_added=19600000,
        ohlc_bars=413000,
        duckdb_size_mb=2080.5
    )

@pytest.fixture
def sample_coverage_info():
    """Sample CoverageInfo for testing."""
    from exness_data_preprocess.models import CoverageInfo

    return CoverageInfo(
        database_exists=True,
        duckdb_path="/tmp/eurusd.duckdb",
        duckdb_size_mb=2080.5,
        raw_spread_ticks=18600000,
        standard_ticks=19600000,
        ohlc_bars=413000,
        earliest_date="2024-10-01 00:00:00+00:00",
        latest_date="2025-10-31 23:59:59+00:00",
        date_range_days=395
    )

@pytest.fixture
def mock_download(monkeypatch):
    """Mock network downloads to avoid real API calls."""
    def _mock_download_exness_zip(self, year, month, pair, variant):
        # Return mock zip path
        return self.temp_dir / f"Exness_{pair}_{variant}_{year}_{month:02d}.zip"

    from exness_data_preprocess import processor
    monkeypatch.setattr(processor.ExnessDataProcessor, "download_exness_zip", _mock_download_exness_zip)
```

---

## Test Execution Plan

### Phase 4A: Model Tests (1 hour)
1. Implement `test_models.py` - Pydantic model validation
2. Implement `test_types.py` - Type safety and helpers
3. Run: `uv run pytest tests/test_models.py tests/test_types.py -v`

### Phase 4B: Integration Tests (1.5 hours)
1. Implement `test_processor_pydantic.py` - Processor returns Pydantic models
2. Add mock fixtures to `conftest.py`
3. Run: `uv run pytest tests/test_processor_pydantic.py -v`

### Phase 4C: Functional Regression Tests (1 hour)
1. Implement `test_functional_regression.py` - v2.0.0 functionality preserved
2. Run: `uv run pytest tests/test_functional_regression.py -v`

### Phase 4D: Full Test Suite (30 minutes)
1. Run all tests: `uv run pytest -v`
2. Generate coverage report: `uv run pytest --cov=exness_data_preprocess --cov-report=html`
3. Verify 100% pass rate
4. Review coverage report (target: >80% coverage)

---

## Success Criteria

✅ All tests pass (100% pass rate)
✅ Code coverage > 80% for src/exness_data_preprocess/models.py
✅ Code coverage > 70% for src/exness_data_preprocess/processor.py
✅ Zero functional regressions from v2.0.0
✅ All Pydantic models validate correctly
✅ JSON Schema generation works
✅ Type safety enforced (Literal types)

---

## Risk Mitigation

**Risk 1**: Network-dependent tests fail
**Mitigation**: Mock all network calls with `monkeypatch`

**Risk 2**: Database tests interfere with each other
**Mitigation**: Use `temp_dir` fixture for isolation

**Risk 3**: Tests are slow
**Mitigation**: Use small sample datasets, mark slow tests with `@pytest.mark.slow`

**Risk 4**: Pydantic validation failures
**Mitigation**: Test edge cases (None values, negative numbers, etc.)

---

## References

- **v2.0.0 Validation**: `/tmp/exness-duckdb-test/test_refactored_processor.py`
- **Query Validation**: `/tmp/exness-duckdb-test/test_queries_only.py`
- **Test TODO**: `/Users/terryli/eon/exness-data-preprocess/tests/README.md`
- **Pydantic Docs**: https://docs.pydantic.dev/latest/

---

**Next Step**: Implement tests in order (4A → 4B → 4C → 4D)
