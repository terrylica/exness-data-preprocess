# Tests

## Running

```bash
moon run repo:test     # pytest; ClickHouse-backed tests skip (with the probe's reason) if no server is usable
moon run repo:check    # offline gate: ruff + mypy + pytest
moon run repo:e2e      # hermetic: throwaway ClickHouse on free ports, full pytest with ClickHouse required,
                       # then scripts/validate_clickhouse.py all (schema, a real EURUSD load, queries)
```

## ClickHouse-backed tests

A test needs ClickHouse if it is marked `@pytest.mark.clickhouse` or uses the `processor_with_clickhouse` fixture. `conftest.py` probes once per session with a real authenticated query through `get_client()`, so it honours `CLICKHOUSE_HOST`, `CLICKHOUSE_PORT`, `CLICKHOUSE_USER` and `CLICKHOUSE_PASSWORD`. A server that holds the port but rejects the credentials (for example a shared, password-protected system server on `:8123`) counts as unavailable.

Set `EXNESS_REQUIRE_CLICKHOUSE=1` to turn those skips into a session error; `repo:e2e` does this so it cannot pass by skipping.

## Files

| File                               | Covers                                                              |
| ---------------------------------- | ------------------------------------------------------------------- |
| `test_basic.py`                    | Import, `__version__`, processor instantiation (ClickHouse)         |
| `test_package_structure.py`        | Every public export imports; the ClickHouse classes share the mixin |
| `test_models.py`                   | Pydantic models, computed fields, JSON schema                       |
| `test_processor_pydantic.py`       | Processor methods return the Pydantic models (partly ClickHouse)    |
| `test_functional_regression.py`    | Query, coverage, schema and close against ClickHouse                |
| `test_database_bootstrap_order.py` | `exness` database is created before the first default-database bind |
| `test_types.py`                    | `PairType` / `TimeframeType` / `VariantType` literals and helpers   |
