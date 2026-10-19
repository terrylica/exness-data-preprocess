# Contributing

## Setup

```bash
git clone https://github.com/terrylica/exness-data-preprocess.git
cd exness-data-preprocess
uv sync --dev                 # Python version comes from .python-version
```

You also need [moon](https://moonrepo.dev/) (pinned through proto) for the task runner and a `clickhouse` binary on `PATH` for the end-to-end run.

## Before you open a pull request

```bash
moon run repo:check   # ruff check, ruff format --check, mypy, pytest
moon run repo:e2e     # throwaway ClickHouse + full pytest + validate checks + examples
```

Both gates run locally; GitHub Actions only publishes releases and runs Dependabot. See [tests/README.md](/tests/README.md) for how ClickHouse-backed tests are selected and skipped.

## Commits and releases

Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `docs:`, `test:`, `refactor:`, `perf:`, `chore:`, `ci:`); the commitizen pre-commit hook checks them (`uv run pre-commit install --hook-type commit-msg --hook-type pre-push`). semantic-release derives the next version and the changelog from them, so never edit the version or `CHANGELOG.md` by hand.

## Reporting issues

Include the package version (`uv pip show exness-data-preprocess`), Python version, OS, a minimal reproduction, and the full traceback.

## License

Contributions are licensed under the MIT License.
