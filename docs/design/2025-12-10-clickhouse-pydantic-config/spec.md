---
title: ClickHouse Pydantic Config Integration
adr: /docs/adr/2025-12-10-clickhouse-pydantic-config.md
status: accepted
created: 2025-12-10
---

# Design Spec: ClickHouse Pydantic Config Integration

**ADR**: [ClickHouse Pydantic Config Integration](/docs/adr/2025-12-10-clickhouse-pydantic-config.md)

## Goal

Generate DBeaver database client configurations from Pydantic v2 models using mise `[env]` as Single Source of Truth (SSoT).

## Canonical Reference

`/Users/terryli/eon/cc-skills/plugins/devops-tools/skills/clickhouse-pydantic-config/`

---

## Adaptation Requirements

| Aspect             | Current State               | Target State                         |
| ------------------ | --------------------------- | ------------------------------------ |
| **SSL config**     | `CLICKHOUSE_SECURE` env var | `CLICKHOUSE_MODE` (local/cloud)      |
| **Database**       | `exness` (hardcoded)        | `exness` via `CLICKHOUSE_DATABASE`   |
| **mise [env]**     | No CLICKHOUSE\_\* vars      | Full SSoT configuration              |
| **DBeaver config** | Does not exist              | `.dbeaver/data-sources.json`         |
| **Scripts**        | None                        | `scripts/generate_dbeaver_config.py` |

---

## Implementation Tasks

### Task 1: Update `.mise.toml` [env] Section

Add ClickHouse SSoT configuration:

```toml
# ADR: 2025-12-10-clickhouse-pydantic-config
# ClickHouse SSoT Configuration

# Connection identity
CLICKHOUSE_NAME = "exness-clickhouse-local"
CLICKHOUSE_MODE = "local"  # "local" or "cloud"
CLICKHOUSE_TYPE = "dev"    # "dev", "test", or "prod"

# Connection parameters (match existing clickhouse_client.py defaults)
CLICKHOUSE_HOST = "localhost"
CLICKHOUSE_PORT = "8123"
CLICKHOUSE_DATABASE = "exness"

# Output paths
DBEAVER_CONFIG_PATH = ".dbeaver/data-sources.json"

# Cloud credentials (read from .env for security)
# CLICKHOUSE_USER_READONLY - set in .env
# CLICKHOUSE_PASSWORD_READONLY - set in .env
```

### Task 2: Create `scripts/generate_dbeaver_config.py`

Copy and adapt from canonical implementation:

- Source: `/Users/terryli/eon/cc-skills/plugins/devops-tools/skills/clickhouse-pydantic-config/scripts/generate_dbeaver_config.py`
- Adaptations:
  - Change default database from `"default"` to `"exness"`
  - Change default name from `"clickhouse-local"` to `"exness-clickhouse-local"`

Key components:

- `ClickHouseConnection` Pydantic model with `@model_validator` for mode-aware SSL
- `DBeaver JSON format` with folders and connections structure
- PEP 723 inline dependencies (`# /// script`)

### Task 3: Add mise Tasks

```toml
[tasks.db-client-generate]
description = "Generate DBeaver config from Pydantic model"
run = "uv run scripts/generate_dbeaver_config.py --output ${DBEAVER_CONFIG_PATH}"

[tasks."db-client:cloud"]
description = "Generate config for ClickHouse Cloud"
run = "uv run scripts/generate_dbeaver_config.py --mode cloud --output ${DBEAVER_CONFIG_PATH}"

[tasks."db-client:dry-run"]
description = "Preview generated config without writing"
run = "uv run scripts/generate_dbeaver_config.py --dry-run"

[tasks.dbeaver]
description = "Launch DBeaver with project workspace"
run = '"/Applications/DBeaver.app/Contents/MacOS/dbeaver" -data .dbeaver-workspace &'
```

### Task 4: Update `.gitignore`

Add DBeaver entries:

```
# DBeaver (credentials in generated JSON)
.dbeaver/
.dbeaver-workspace/
```

### Task 5: Update `clickhouse_client.py` (Backward Compatibility)

Add `CLICKHOUSE_MODE` support while keeping `CLICKHOUSE_SECURE` as fallback:

```python
# Mode-based SSL detection (canonical pattern)
mode = os.environ.get("CLICKHOUSE_MODE", "").lower()
if mode == "cloud":
    resolved_secure = True
    resolved_port = port or int(os.environ.get("CLICKHOUSE_PORT", "8443"))
elif mode == "local":
    resolved_secure = False
else:
    # Fallback: existing CLICKHOUSE_SECURE logic
    env_secure = os.environ.get("CLICKHOUSE_SECURE", "").lower()
    # ... existing logic
```

---

## Critical Files

| File                                              | Action                      |
| ------------------------------------------------- | --------------------------- |
| `.mise.toml`                                      | Add `[env]` vars + tasks    |
| `scripts/generate_dbeaver_config.py`              | **CREATE** - PEP 723 script |
| `.gitignore`                                      | Add `.dbeaver/` entries     |
| `src/exness_data_preprocess/clickhouse_client.py` | Add MODE support            |

---

## Validation Checklist

- [ ] `mise run db-client:dry-run` - Preview config
- [ ] `mise run db-client-generate` - Generate local config
- [ ] `jq . .dbeaver/data-sources.json` - Validate JSON
- [ ] `mise run db-client:cloud` - Generate cloud config (requires .env)
- [ ] DBeaver can import the connection
- [ ] Existing `clickhouse_client.py` tests still pass

---

## Dependencies

- `pydantic>=2.0.0` (already in pyproject.toml)
- `clickhouse-connect>=0.7.0` (already in pyproject.toml)
- DBeaver Community Edition (manual install)
