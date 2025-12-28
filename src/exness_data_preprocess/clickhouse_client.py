"""
ClickHouse connection management.

ADR: /docs/adr/2025-12-09-exness-clickhouse-migration.md
ADR: /docs/adr/2025-12-10-clickhouse-pydantic-config.md

Provides a thin wrapper around clickhouse-connect for:
- Connection configuration via environment variables
- Health checks and connection validation
- Query execution with proper error propagation

Configuration (environment variables):
- CLICKHOUSE_MODE: Connection mode - "local" or "cloud" (preferred over CLICKHOUSE_SECURE)
- CLICKHOUSE_HOST: ClickHouse server hostname (default: localhost)
- CLICKHOUSE_PORT: Native protocol port (default: 8123 local, 8443 cloud)
- CLICKHOUSE_USER: Username (default: default)
- CLICKHOUSE_PASSWORD: Password (default: empty)
- CLICKHOUSE_DATABASE: Default database (default: exness)
- CLICKHOUSE_SECURE: Use HTTPS (fallback if MODE not set, default: false for local)
"""

import os
from typing import Any

import clickhouse_connect
from clickhouse_connect.driver import Client

# Connection defaults
DEFAULT_HOST = "localhost"
DEFAULT_PORT = 8123
DEFAULT_USER = "default"
DEFAULT_PASSWORD = ""
DEFAULT_DATABASE = "exness"


class ClickHouseConnectionError(Exception):
    """Raised when ClickHouse connection fails."""

    pass


class ClickHouseQueryError(Exception):
    """Raised when a ClickHouse query fails."""

    pass


def get_client(
    host: str | None = None,
    port: int | None = None,
    user: str | None = None,
    password: str | None = None,
    database: str | None = None,
    secure: bool | None = None,
) -> Client:
    """
    Create a ClickHouse client with configuration from parameters or environment.

    Args:
        host: ClickHouse server hostname (env: CLICKHOUSE_HOST)
        port: HTTP interface port (env: CLICKHOUSE_PORT)
        user: Username (env: CLICKHOUSE_USER)
        password: Password (env: CLICKHOUSE_PASSWORD)
        database: Default database (env: CLICKHOUSE_DATABASE)
        secure: Use HTTPS (env: CLICKHOUSE_SECURE)

    Returns:
        Connected ClickHouse client

    Raises:
        ClickHouseConnectionError: If connection fails

    Example:
        >>> client = get_client()
        >>> result = client.query("SELECT 1")
        >>> client.close()
    """
    # Resolve configuration from parameters or environment
    resolved_host = host or os.environ.get("CLICKHOUSE_HOST", DEFAULT_HOST)
    resolved_user = user or os.environ.get("CLICKHOUSE_USER", DEFAULT_USER)
    resolved_password = password or os.environ.get("CLICKHOUSE_PASSWORD", DEFAULT_PASSWORD)
    # Database can be None for initial schema creation (CREATE DATABASE needs no database context)
    resolved_database = (
        database
        if database is not None
        else os.environ.get("CLICKHOUSE_DATABASE", DEFAULT_DATABASE)
    )

    # Mode-based SSL detection (ADR: 2025-12-10-clickhouse-pydantic-config)
    # CLICKHOUSE_MODE takes precedence over CLICKHOUSE_SECURE for clarity
    if secure is None:
        mode = os.environ.get("CLICKHOUSE_MODE", "").lower()
        if mode == "cloud":
            # Cloud mode: SSL enabled, port 8443
            resolved_secure = True
            resolved_port = port or int(os.environ.get("CLICKHOUSE_PORT", "8443"))
        elif mode == "local":
            # Local mode: SSL disabled, port 8123
            resolved_secure = False
            resolved_port = port or int(os.environ.get("CLICKHOUSE_PORT", str(DEFAULT_PORT)))
        else:
            # Fallback: existing CLICKHOUSE_SECURE logic for backward compatibility
            resolved_port = port or int(os.environ.get("CLICKHOUSE_PORT", str(DEFAULT_PORT)))
            env_secure = os.environ.get("CLICKHOUSE_SECURE", "").lower()
            if env_secure in ("true", "1", "yes"):
                resolved_secure = True
            elif env_secure in ("false", "0", "no"):
                resolved_secure = False
            else:
                # Auto-detect: secure for non-localhost
                resolved_secure = resolved_host not in ("localhost", "127.0.0.1")
    else:
        resolved_secure = secure
        resolved_port = port or int(os.environ.get("CLICKHOUSE_PORT", str(DEFAULT_PORT)))

    try:
        client = clickhouse_connect.get_client(
            host=resolved_host,
            port=resolved_port,
            username=resolved_user,
            password=resolved_password,
            database=resolved_database,
            secure=resolved_secure,
        )
        return client
    except Exception as e:
        raise ClickHouseConnectionError(
            f"Failed to connect to ClickHouse at {resolved_host}:{resolved_port}: {e}"
        ) from e


def check_connection(client: Client) -> bool:
    """
    Verify ClickHouse connection is healthy.

    Args:
        client: ClickHouse client instance

    Returns:
        True if connection is healthy

    Raises:
        ClickHouseConnectionError: If connection check fails
    """
    try:
        result = client.query("SELECT 1")
        return result.first_row[0] == 1
    except Exception as e:
        raise ClickHouseConnectionError(f"ClickHouse connection check failed: {e}") from e


def execute_query(client: Client, query: str, parameters: dict[str, Any] | None = None) -> Any:
    """
    Execute a query and return the result.

    Args:
        client: ClickHouse client instance
        query: SQL query string
        parameters: Optional query parameters

    Returns:
        Query result object

    Raises:
        ClickHouseQueryError: If query execution fails
    """
    try:
        if parameters:
            return client.query(query, parameters=parameters)
        return client.query(query)
    except Exception as e:
        raise ClickHouseQueryError(f"Query execution failed: {e}\nQuery: {query}") from e


def execute_command(
    client: Client, command: str, parameters: dict | None = None
) -> None:
    """
    Execute a DDL command (CREATE, ALTER, DROP, INSERT SELECT, etc.).

    Args:
        client: ClickHouse client instance
        command: SQL DDL command
        parameters: Optional query parameters for parameterized queries

    Raises:
        ClickHouseQueryError: If command execution fails
    """
    try:
        if parameters:
            client.command(command, parameters=parameters)
        else:
            client.command(command)
    except Exception as e:
        raise ClickHouseQueryError(f"Command execution failed: {e}\nCommand: {command}") from e
