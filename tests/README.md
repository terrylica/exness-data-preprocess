# Test Suite - v2.0.0 (ClickHouse Backend)

## Status

The test suite covers the v2.0.0 ClickHouse-only architecture.

**Architecture**: ClickHouse Cloud backend (ReplacingMergeTree for deduplication)

**ADR**: [DuckDB Removal - ClickHouse Migration](/docs/adr/2025-12-11-duckdb-removal-clickhouse.md)

## v2.0.0 Architecture

### Storage Architecture

- **Database**: `exness` (single database for all instruments)
- **Tables**: `raw_spread_ticks`, `standard_ticks`, `ohlc_1m`
- **Engine**: ReplacingMergeTree (deduplication at merge time)
- **Connection**: localhost:8123 (local) or ClickHouse Cloud via env vars

### API

- `update_data(pair, start_date)` — Download and store tick data
- `query_ohlc(pair, timeframe, start_date, end_date)` — Query OHLC data
- `query_ticks(pair, variant, start_date, end_date)` — Query raw ticks

### Schema

- **OHLC**: 26-column schema — See [`/docs/DATABASE_SCHEMA.md`](/docs/DATABASE_SCHEMA.md)
- **Ticks**: `timestamp_ms`, `bid`, `ask`, `symbol`, `variant`

## Test Coverage

### Unit Tests (test_processor.py)

1. **Initialization**
   - `test_processor_initialization()` - Test ClickHouse connection setup
   - `test_get_or_create_tables()` - Test table creation with schema

2. **Data Download**
   - `test_download_exness_zip()` - Test ZIP download for both variants
   - `test_discover_missing_months()` - Test gap detection

3. **Data Loading**
   - `test_load_ticks_from_zip()` - Test CSV parsing and DataFrame creation
   - `test_append_ticks_to_db()` - Test ReplacingMergeTree deduplication

4. **OHLC Generation**
   - `test_regenerate_ohlc()` - Test 26-column OHLC generation
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
   - `test_update_data_incremental()` - Test incremental updates
   - `test_update_data_gap_filling()` - Test filling gaps in coverage

### Integration Tests (test_integration.py)

1. **End-to-End Workflow**
   - `test_full_workflow()` - Download → Store → Query → Validate
   - `test_multi_instrument()` - Process multiple instruments
   - `test_incremental_update_workflow()` - Initial → Incremental → Validate

2. **Data Quality**
   - `test_no_duplicates()` - Verify ReplacingMergeTree deduplication
   - `test_schema_columns()` - Verify 26-column OHLC schema
   - `test_date_range_accuracy()` - Verify date range filtering accuracy

## Test Data

### Mock Data Requirements

1. **Sample Ticks**
   - Create fixture with ~1000 ticks for both Raw_Spread and Standard variants
   - Include various timestamps to test resampling
   - Include zero-spread and non-zero-spread ticks

2. **ClickHouse Test Instance**
   - Use local ClickHouse server for integration tests
   - Create isolated test database to avoid polluting production data

### Fixtures (conftest.py)

```python
@pytest.fixture
def sample_raw_spread_ticks():
    """Sample Raw_Spread tick data."""
    ...

@pytest.fixture
def sample_standard_ticks():
    """Sample Standard tick data."""
    ...

@pytest.fixture
def clickhouse_test_db():
    """Isolated ClickHouse test database."""
    ...

@pytest.fixture
def processor_with_clickhouse(clickhouse_test_db):
    """ExnessDataProcessor instance with test ClickHouse."""
    ...
```

## Running Tests

```bash
# Ensure ClickHouse is running
mise run clickhouse:ensure

# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=exness_data_preprocess --cov-report=html

# Run specific test
uv run pytest tests/test_processor.py -v

# Run integration tests only
uv run pytest tests/test_integration.py -v

# Full E2E validation (requires ClickHouse)
mise run validate
```

## ClickHouse Requirements

Tests require a ClickHouse instance:

```bash
# Start local ClickHouse (mise-installed)
mise run clickhouse:start

# Or use Docker
docker run -d -p 8123:8123 -p 9000:9000 clickhouse/clickhouse-server

# Verify connection
mise run clickhouse:status
```

## Contributing

When writing new tests:

1. Follow pytest conventions
2. Use descriptive test names
3. Mock external dependencies (network calls)
4. Test both success and failure cases
5. Include docstrings explaining what is being tested
6. Ensure tests work with local ClickHouse instance

## Reference

- **Schema**: [`/docs/DATABASE_SCHEMA.md`](/docs/DATABASE_SCHEMA.md) - 26-column OHLC specification
- **Architecture**: [`/docs/MODULE_ARCHITECTURE.md`](/docs/MODULE_ARCHITECTURE.md) - 13 modules with SLOs
- **ADR**: [`/docs/adr/2025-12-11-duckdb-removal-clickhouse.md`](/docs/adr/2025-12-11-duckdb-removal-clickhouse.md) - Migration decision
