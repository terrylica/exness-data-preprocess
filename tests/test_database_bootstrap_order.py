"""
Regression test for the database-bootstrap-before-get_client ordering invariant.

Background
----------
Before 2026-05-13, instantiating ExnessDataProcessor on a host where the
`exness` ClickHouse database did NOT yet exist would fail immediately with::

    ClickHouseConnectionError: Failed to connect to ClickHouse at
    localhost:8123: Code: 81. DB::Exception: Database exness does not exist.
    (UNKNOWN_DATABASE)

The bug was a chicken-and-egg in `ExnessDataProcessor.__init__`:

    self._ch_client = get_client()                  # <-- binds to 'exness'; fails here
    ...
    self.ch_manager = ClickHouseManager(self._ch_client)
    ...
    self.ch_manager.ensure_schema()                  # <-- would create 'exness', but unreachable

The fix added a module-level `ensure_database_bootstrap()` helper to
`clickhouse_manager.py` and wired `ExnessDataProcessor.__init__` to call
it BEFORE the first default-database `get_client()`. The helper uses
`get_client(database="")` (no database context) to issue
`CREATE DATABASE IF NOT EXISTS exness`, then closes that bootstrap client.

This regression test asserts the ordering invariant via static-source
inspection: it does NOT require a live ClickHouse, so it runs in any CI
environment.

Provenance
----------
- Discovered: 2026-05-13 mql5 pueue-job 294 incident (10s failure window).
- Hot-patched: out-of-band invocation of `ClickHouseManager().ensure_schema()`.
- Permanent fix: this PR.
- mql5 audit: findings/audits/2026-05-13-pillar-restoration-pueue-kickoff.md
              findings/audits/2026-05-13-surveillance-watchdog-deployment.md
"""

import inspect

from exness_data_preprocess.clickhouse_manager import (
    ClickHouseManager,
    ensure_database_bootstrap,
)
from exness_data_preprocess.processor import ExnessDataProcessor


def test_ensure_database_bootstrap_is_callable_module_level() -> None:
    """The helper must be importable at module level (callers cannot
    instantiate ClickHouseManager first — that would trigger the same
    chicken-and-egg the helper exists to prevent)."""
    assert callable(ensure_database_bootstrap)
    # Helper docstring must mention the failure mode + remediation context.
    doc = ensure_database_bootstrap.__doc__ or ""
    assert "UNKNOWN_DATABASE" in doc, "helper docstring must document the failure mode it prevents"
    assert "before" in doc.lower(), "docstring must explain WHEN to call the helper"


def test_processor_init_calls_bootstrap_before_first_get_client() -> None:
    """ExnessDataProcessor.__init__ must call `ensure_database_bootstrap()`
    BEFORE `get_client()` — otherwise the default-database get_client binds
    to 'exness' and raises UNKNOWN_DATABASE on freshly-provisioned hosts."""
    source = inspect.getsource(ExnessDataProcessor.__init__)
    bootstrap_pos = source.find("ensure_database_bootstrap()")
    get_client_pos = source.find("self._ch_client = get_client()")
    assert bootstrap_pos >= 0, "ExnessDataProcessor.__init__ must call ensure_database_bootstrap()"
    assert get_client_pos >= 0, "ExnessDataProcessor.__init__ must call get_client()"
    assert bootstrap_pos < get_client_pos, (
        "ensure_database_bootstrap() must precede get_client() in __init__ "
        "— otherwise the get_client default-database bind fails on hosts "
        "where the 'exness' database does not yet exist (UNKNOWN_DATABASE, CH code 81)"
    )


def test_clickhouse_manager_ensure_schema_delegates_to_bootstrap_helper() -> None:
    """ClickHouseManager.ensure_schema() must use the module-level helper
    (no inline CREATE DATABASE) so that both call sites converge on the
    same idempotent bootstrap path. Prevents drift between the two."""
    source = inspect.getsource(ClickHouseManager.ensure_schema)
    assert "ensure_database_bootstrap()" in source, (
        "ClickHouseManager.ensure_schema must delegate to the module-level "
        "ensure_database_bootstrap() helper (single source of truth for the "
        "CREATE DATABASE IF NOT EXISTS step)"
    )
    # Belt-and-suspenders: no inline CREATE DATABASE statements should remain.
    assert "CREATE DATABASE" not in source, (
        "ClickHouseManager.ensure_schema must not contain its own inline "
        "CREATE DATABASE statement — that would diverge from the helper"
    )
