# Test Suite - v2.0.0 (To Be Rewritten)

## Status

The test suite needs to be completely rewritten for the v2.0.0 architecture.

**Previous test files (removed)**:
- `test_processor.py` - Tested v1.0.0 Parquet-based storage and monthly DuckDB files
- `test_api.py` - Tested v1.0.0 API functions (process_month, analyze_ticks, etc.)
- `test_cli.py` - Tested v1.0.0 CLI commands

## v2.0.0 Architecture Changes

The v2.0.0 refactoring introduced significant changes that require new tests:

### Storage Architecture
- **Old**: Monthly DuckDB files (eurusd_ohlc_2024_08.duckdb) + Parquet tick storage
- **New**: Single DuckDB file per instrument (eurusd.duckdb) with all years

### API Changes
- **Old**: `process_month(year, month)`, `query_ohlc(year, month)`, `analyze_ticks(year, month)`
- **New**: `update_data(pair, start_date)`, `query_ohlc(pair, timeframe, start_date, end_date)`, `query_ticks(pair, variant, start_date, end_date)`

### Schema Changes
- **Old**: 7-column OHLC (Timestamp, Open, High, Low, Close, spread_avg, tick_count)
- **New**: Phase7 9-column OHLC (Timestamp, Open, High, Low, Close, raw_spread_avg, standard_spread_avg, tick_count_raw_spread, tick_count_standard)

## Required Test Coverage

### Unit Tests (test_processor.py)

1. **Initialization**
   - `test_processor_initialization()` - Test base_dir setup
   - `test_get_or_create_db()` - Test database creation with schema

2. **Data Download**
   - `test_download_exness_zip()` - Test ZIP download for both variants
   - `test_discover_missing_months()` - Test gap detection

3. **Data Loading**
   - `test_load_ticks_from_zip()` - Test CSV parsing and DataFrame creation
   - `test_append_ticks_to_db()` - Test PRIMARY KEY constraint enforcement

4. **OHLC Generation**
   - `test_regenerate_ohlc()` - Test Phase7 9-column OHLC generation
   - `test_ohlc_dual_variant_join()` - Test LEFT JOIN between Raw_Spread and Standard

5. **Query Methods**
   - `test_query_ticks()` - Test tick queries with date ranges
   - `test_query_ohlc_1m()` - Test 1-minute OHLC queries
   - `test_query_ohlc_resampling()` - Test on-demand resampling (5m, 1h, 1d)
   - `test_query_with_sql_filter()` - Test SQL WHERE clause filtering

6. **Coverage Tracking**
   - `test_get_data_coverage()` - Test coverage information retrieval
   - `test_update_metadata()` - Test metadata table updates

7. **Incremental Updates**
   - `test_update_data_initial()` - Test initial download
   - `test_update_data_incremental()` - Test incremental updates (should add 0 months when up to date)
   - `test_update_data_gap_filling()` - Test filling gaps in coverage

### Integration Tests (test_integration.py)

1. **End-to-End Workflow**
   - `test_full_workflow()` - Download → Store → Query → Validate
   - `test_multi_instrument()` - Process multiple instruments
   - `test_incremental_update_workflow()` - Initial → Incremental → Validate

2. **Data Quality**
   - `test_no_duplicates()` - Verify PRIMARY KEY constraints work
   - `test_phase7_schema()` - Verify 9-column OHLC schema
   - `test_date_range_accuracy()` - Verify date range filtering accuracy

### API Tests (test_api.py)

1. **Convenience Functions**
   - Test wrapper functions if any exist in v2.0.0

### CLI Tests (test_cli.py)

1. **CLI Commands**
   - Tests will depend on CLI implementation for v2.0.0

## Test Data

### Mock Data Requirements

1. **Sample Ticks**
   - Create fixture with ~1000 ticks for both Raw_Spread and Standard variants
   - Include various timestamps to test resampling
   - Include zero-spread and non-zero-spread ticks

2. **Sample Database**
   - Create fixture with pre-populated eurusd.duckdb for query tests
   - Include multiple months of data to test date range queries

### Fixtures (conftest.py)

```python
@pytest.fixture
def temp_dir():
    """Temporary directory for test data."""
    ...

@pytest.fixture
def sample_raw_spread_ticks():
    """Sample Raw_Spread tick data."""
    ...

@pytest.fixture
def sample_standard_ticks():
    """Sample Standard tick data."""
    ...

@pytest.fixture
def sample_unified_database(temp_dir):
    """Pre-populated eurusd.duckdb for testing."""
    ...

@pytest.fixture
def processor_with_temp_dir(temp_dir):
    """ExnessDataProcessor instance with temporary directory."""
    ...
```

## Running Tests

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=exness_data_preprocess --cov-report=html

# Run specific test
uv run pytest tests/test_processor.py -v

# Run integration tests only
uv run pytest tests/test_integration.py -v
```

## Contributing

When writing new tests:
1. Follow pytest conventions
2. Use descriptive test names
3. Mock external dependencies (network calls, file I/O when appropriate)
4. Test both success and failure cases
5. Include docstrings explaining what is being tested

## Reference

**Validation Test**: `/tmp/exness-duckdb-test/test_refactored_processor.py` - Real data validation test
**Query Test**: `/tmp/exness-duckdb-test/test_queries_only.py` - Query method validation

These tests can serve as reference implementations for the new test suite.
