# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pydantic>=2.0",
# ]
# ///
"""Generate DBeaver data-sources.json from Pydantic ClickHouse connection model.

ADR: /docs/adr/2025-12-10-clickhouse-pydantic-config.md

This script uses Pydantic v2 as the Single Source of Truth (SSoT) for ClickHouse
connection configuration. All configurable values are read from environment
variables (mise `[env]` section) with sensible defaults.

Usage:
    uv run scripts/generate_dbeaver_config.py --output .dbeaver/data-sources.json
    uv run scripts/generate_dbeaver_config.py --mode cloud --output .dbeaver/data-sources.json
    uv run scripts/generate_dbeaver_config.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import sys
from enum import Enum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, computed_field, model_validator


class ConnectionMode(str, Enum):
    """Connection mode determines SSL and port defaults."""

    LOCAL = "local"
    CLOUD = "cloud"


class ClickHouseConnection(BaseModel):
    """ClickHouse connection configuration - Single Source of Truth.

    ADR: /docs/adr/2025-12-10-clickhouse-pydantic-config.md

    This model defines all connection parameters. Values are read from
    environment variables with the CLICKHOUSE_ prefix by default.
    """

    name: str = Field(default="exness-clickhouse-local", description="Connection display name")
    mode: ConnectionMode = Field(default=ConnectionMode.LOCAL, description="local or cloud")
    host: str = Field(default="localhost", description="ClickHouse hostname")
    port: int = Field(default=8123, description="HTTP port (8123 local, 8443 cloud)")
    database: str = Field(default="exness", description="Default database")
    ssl_enabled: bool = Field(default=False, description="Enable SSL/TLS")
    ssl_mode: Literal["disable", "require", "verify-ca", "verify-full"] = Field(default="disable")
    connection_type: Literal["dev", "test", "prod"] = Field(default="dev")

    @model_validator(mode="after")
    def validate_mode_settings(self) -> ClickHouseConnection:
        """Apply cloud-specific defaults when mode is CLOUD."""
        if self.mode == ConnectionMode.CLOUD:
            self.port = 8443
            self.ssl_enabled = True
            self.ssl_mode = "require"
        return self

    @computed_field
    @property
    def jdbc_url(self) -> str:
        """Generate JDBC URL for DBeaver."""
        protocol = "https" if self.ssl_enabled else "http"
        return f"jdbc:clickhouse:{protocol}://{self.host}:{self.port}/{self.database}"

    @computed_field
    @property
    def connection_id(self) -> str:
        """Generate unique connection ID for DBeaver."""
        return f"clickhouse-jdbc-{secrets.token_hex(8)}"

    def to_dbeaver_config(self) -> dict:
        """Generate DBeaver data-sources.json connection entry.

        Credential handling by mode:
        - LOCAL: Hardcode `default` user, empty password (zero friction)
        - CLOUD: Pre-populate from environment (gitignored output)
        """
        config = {
            "provider": "clickhouse",
            "driver": "com_clickhouse",
            "name": self.name,
            "configuration": {
                "host": self.host,
                "port": str(self.port),
                "database": self.database,
                "url": self.jdbc_url,
                "type": self.connection_type,
                "auth-model": "native",
            },
        }

        if self.ssl_enabled:
            config["configuration"]["handler-ssl"] = "openssl"
            config["configuration"]["ssl-mode"] = self.ssl_mode

        # Credential handling by mode
        if self.mode == ConnectionMode.LOCAL:
            # Local: hardcode default credentials (no security concern)
            config["configuration"]["user"] = "default"
            config["configuration"]["password"] = ""
        elif self.mode == ConnectionMode.CLOUD:
            # Cloud: read from environment (gitignored output)
            config["configuration"]["user"] = os.environ.get("CLICKHOUSE_USER_READONLY", "default")
            config["configuration"]["password"] = os.environ.get("CLICKHOUSE_PASSWORD_READONLY", "")

        return config

    @classmethod
    def from_env(cls, prefix: str = "CLICKHOUSE_") -> ClickHouseConnection:
        """Create connection from environment variables.

        Reads from mise `[env]` section with backward-compatible defaults.
        Works with or without mise installed.
        """
        mode_str = os.environ.get(f"{prefix}MODE", "local")
        return cls(
            name=os.environ.get(f"{prefix}NAME", "exness-clickhouse-local"),
            mode=ConnectionMode(mode_str),
            host=os.environ.get(f"{prefix}HOST", "localhost"),
            port=int(os.environ.get(f"{prefix}PORT", "8123")),
            database=os.environ.get(f"{prefix}DATABASE", "exness"),
            connection_type=os.environ.get(f"{prefix}TYPE", "dev"),
        )


def generate_dbeaver_datasources(connection: ClickHouseConnection) -> dict:
    """Generate complete DBeaver data-sources.json structure."""
    return {
        "folders": {},
        "connections": {connection.connection_id: connection.to_dbeaver_config()},
    }


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Generate DBeaver config from Pydantic ClickHouse model"
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=Path(".dbeaver/data-sources.json"),
        help="Output path for data-sources.json",
    )
    parser.add_argument(
        "--mode",
        "-m",
        choices=["local", "cloud"],
        help="Override connection mode (default: from CLICKHOUSE_MODE env var)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print config to stdout without writing file",
    )

    args = parser.parse_args()

    # Create connection from environment
    connection = ClickHouseConnection.from_env()

    # Override mode if specified
    if args.mode:
        connection = ClickHouseConnection(
            name=connection.name,
            mode=ConnectionMode(args.mode),
            host=connection.host,
            port=connection.port,
            database=connection.database,
            connection_type=connection.connection_type,
        )

    # Generate DBeaver config
    config = generate_dbeaver_datasources(connection)
    config_json = json.dumps(config, indent=2)

    if args.dry_run:
        print(config_json)
        return 0

    # Ensure output directory exists
    args.output.parent.mkdir(parents=True, exist_ok=True)

    # Write config
    args.output.write_text(config_json)
    print(f"Generated: {args.output}")
    print(f"  Connection: {connection.name}")
    print(f"  Mode: {connection.mode.value}")
    print(f"  Host: {connection.host}:{connection.port}")
    print(f"  Database: {connection.database}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
