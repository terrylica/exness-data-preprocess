# CLAUDE.md

`exness-data-preprocess`: downloads Exness forex ticks from ticks.ex2archive.com into ClickHouse (database `exness`: `raw_spread_ticks`, `standard_ticks`, `ohlc_1m`, plus `exchange_sessions` and `holidays`) and serves tick and OHLC queries. Entry point: `ExnessDataProcessor`. User docs: [README.md](/README.md); index of the rest: [docs/README.md](/docs/README.md).

## Commands

```bash
uv sync --dev
moon run repo:check      # offline gate: ruff check + ruff format --check + mypy + pytest
moon run repo:e2e        # hermetic: throwaway ClickHouse on free ports, pytest with ClickHouse required,
                         # validate_clickhouse.py all (incl. a real EURUSD download), examples/basic_usage.py
moon run repo:build      # sdist + wheel into dist/
```

`repo:validate`, `repo:clickhouse-start` / `repo:clickhouse-stop` and `repo:validate-clickhouse-*` target a persistent local server on :8123 (see [moon.yml](/moon.yml)).

## Toolchain

- proto pins uv (`.prototools`); uv owns Python. `.python-version` pins 3.11 and wins. If `UV_PYTHON` is exported in the shell, it overrides the pin, so run `env -u UV_PYTHON uv ...` or the venv is built on the wrong interpreter.
- Releases: write `docs/release-notes/<next>.md` (narrative paragraph + Keep a Changelog bullets, one line each) in the PR before releasing; semantic-release (`npm run release`) refuses to release without it, runs `uv version <next> --frozen`, and `scripts/publish-release-notes.sh` rebuilds the GitHub Release body as narrative + generated section. pyproject.toml is the only place the version lives; `__version__` reads installed metadata. Publishing is `.github/workflows/publish.yml` (PyPI Trusted Publishing on a GitHub Release), the only publish path.
- Dependency update PRs come from `.github/dependabot.yml`. No other CI runs in Actions; gates are local.

## Invariants

- `ensure_database_bootstrap()` must run before the first `get_client()` that binds the `exness` database (`tests/test_database_bootstrap_order.py`).
- Insert DataFrames with `client.insert_df(...)`, never `client.insert(data=df)` (that takes row sequences).
- Tables are ReplacingMergeTree. Tick tables dedupe on `(instrument, timestamp, seq)`: `seq` (`assign_tick_seq`) numbers same-timestamp ticks in source order, so distinct ticks sharing a timestamp are kept and re-inserting a month is idempotent. Duplicates only collapse at merge time, so every read whose answer depends on duplicates (counts, tick/OHLC rows, the OHLC build) uses `FINAL`; keep it that way.
- Datetime query parameters are typed `DateTime64(6, 'UTC')`, never bare `DateTime64`: a bare one parses naive text in the server's time zone and shifts every filter on a non-UTC server. `repo:e2e` runs its server in America/New_York to catch this.
- ClickHouse-backed tests are marked `clickhouse` or use `processor_with_clickhouse` (fixture users get the marker at collection, so `-m clickhouse` selects them); `conftest.py` skips them with the probe's reason unless `EXNESS_REQUIRE_CLICKHOUSE=1`. A server that holds :8123 but rejects the credentials (el02's shared system ClickHouse) counts as unavailable. Use `repo:e2e`, not that server.
- `gapless-crypto-clickhouse` also uses localhost:8123. `clickhouse-stop` only stops the PID in this repo's pidfile.
- ADRs and design specs under `docs/adr/` and `docs/design/` are historical records: add new ones, don't rewrite old ones.
