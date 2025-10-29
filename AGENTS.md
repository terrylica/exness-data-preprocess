# Repository Guidelines

## Project Structure & Module Organization

Core Python packages sit in `src/exness_data_preprocess`, with `processor.py`, `api.py`, and `cli.py` defining the public surface. Tests live in `tests/` and mirror module names (`test_processor.py`, `test_api.py`, `test_cli.py`). Longer-form docs are in `docs/`, and runnable usage samples stay under `examples/`. The `data/` and `eurusd/` folders ship fixture datasets; treat them as read-only. Prefer the top-level `Makefile` for repeatable workflows.

## Build, Test, and Development Commands

Run `uv sync --dev` to install runtime plus contributor dependencies. Execute `uv run pytest -v --tb=short` (or `make test`) for the suite, and `make test-cov` when you need HTML coverage in `htmlcov/`. Format with `uv run ruff format .`, lint using `uv run ruff check --fix .`, and type-check via `uv run mypy src/`. For insights, `make module-complexity` and `make module-deps` wrap `radon` and `pipdeptree`—install ad hoc tools through `uv pip install …`.

## Coding Style & Naming Conventions

Target Python 3.9 and keep lines ≤100 characters (Ruff and Black enforce this). Group imports as standard library, third party, then `exness_data_preprocess`; Ruff’s isort rules preserve the order. Modules stay snake_case, classes PascalCase, constants upper snake case. Guard new public APIs via `src/exness_data_preprocess/__init__.py`, and include type hints unless they obscure readability. Stick to ASCII identifiers so DuckDB jobs remain portable.

## Testing Guidelines

The suite uses `pytest` with marks defined in `pyproject.toml`; apply `@pytest.mark.integration` to tests that hit the network or download large archives. Mirror source filenames when adding test modules and keep fixtures small enough for CI execution. Generate coverage with `make test-cov` and review `htmlcov/index.html` before major refactors. Favor deterministic samples in `data/` and stream heavier artifacts into temporary directories during tests.

## Commit & Pull Request Guidelines

Adopt conventional commits (`feat:`, `fix:`, `docs:`, `chore:`) as in the existing history. Pull requests should summarize the change, call out data impacts (schema tweaks, new endpoints), and link issues when relevant. Attach screenshots or terminal snippets when adjusting CLI UX. Confirm `pytest`, `ruff`, and `mypy` succeed before review, noting any intentionally skipped checks.

## Data Handling & Configuration Notes

Generated DuckDB files land in `~/eon/exness-data/`—never commit them. Temporary ZIPs should live in that directory’s `temp/` subfolder. When documenting new instruments or timeframes, update `docs/DATABASE_SCHEMA.md` and check `src/exness_data_preprocess/schema.py` so storage metadata stays synchronized.
