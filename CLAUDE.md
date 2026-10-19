# CLAUDE.md

`exness-data-preprocess`: downloads Exness forex ticks from ticks.ex2archive.com into ClickHouse (database `exness`: `raw_spread_ticks`, `standard_ticks`, `ohlc_1m`, plus `exchange_sessions` and `holidays`) and serves tick and OHLC queries. Entry point: `ExnessDataProcessor`. User docs: [README.md](/README.md); index of the rest: [docs/README.md](/docs/README.md).

## Commands

```bash
uv sync --dev
moon run repo:check      # offline gate: ruff check + ruff format --check + mypy + pytest
moon run repo:e2e        # hermetic: throwaway ClickHouse on free ports, pytest with ClickHouse required,
                         # validate_clickhouse.py all (incl. a real one-month EURUSD download), examples/basic_usage.py
moon run repo:build      # sdist + wheel into dist/
```

`repo:validate`, `repo:clickhouse-start` / `repo:clickhouse-stop` and `repo:validate-clickhouse-*` target a persistent local server on :8123 (see [moon.yml](/moon.yml)).

## Toolchain

- proto pins uv (`.prototools`); uv owns Python. `.python-version` pins 3.11 and wins. If `UV_PYTHON` is exported in the shell, it overrides the pin, so run `env -u UV_PYTHON uv ...` or the venv is built on the wrong interpreter.
- Releases: semantic-release (`npm run release`) runs `uv version <next> --frozen`. pyproject.toml is the only place the version lives; `__version__` reads installed metadata. Publishing is `.github/workflows/publish.yml` (PyPI Trusted Publishing on a GitHub Release), the only publish path.
- Dependency update PRs come from `.github/dependabot.yml`. No other CI runs in Actions; gates are local.

## Invariants

- `ensure_database_bootstrap()` must run before the first `get_client()` that binds the `exness` database (`tests/test_database_bootstrap_order.py`).
- Insert DataFrames with `client.insert_df(...)`, never `client.insert(data=df)` (that takes row sequences).
- Tables are ReplacingMergeTree: re-inserting a month is safe; duplicates collapse at merge time, so counts can be higher until a merge or `FINAL`.
- ClickHouse-backed tests are marked `clickhouse` or use `processor_with_clickhouse`; `conftest.py` skips them with the probe's reason unless `EXNESS_REQUIRE_CLICKHOUSE=1`. A server that holds :8123 but rejects the credentials (el02's shared system ClickHouse) counts as unavailable. Use `repo:e2e`, not that server.
- `gapless-crypto-clickhouse` also uses localhost:8123. `clickhouse-stop` only stops the PID in this repo's pidfile.
- ADRs and design specs under `docs/adr/` and `docs/design/` are historical records: add new ones, don't rewrite old ones.
