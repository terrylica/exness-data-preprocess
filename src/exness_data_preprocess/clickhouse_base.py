"""
ClickHouse client lifecycle mixin for shared connection management.

ADR: /docs/adr/2025-12-09-codebase-pruning.md

Provides:
- Lazy client initialization via `get_client()`
- Connection ownership tracking for proper cleanup
- Consistent `client` property and `close()` method across all ClickHouse modules

Used by:
- ClickHouseManager (schema and tick insertion)
- ClickHouseGapDetector (incremental update detection)
- ClickHouseQueryEngine (tick and OHLC queries)
- ClickHouseOHLCGenerator (Phase7 OHLC generation)
"""

from clickhouse_connect.driver import Client

from exness_data_preprocess.clickhouse_client import get_client


class ClickHouseClientMixin:
    """
    Mixin providing ClickHouse client lifecycle management.

    Handles:
    - Optional client injection for testing/sharing connections
    - Lazy client creation when not provided
    - Proper cleanup of owned connections

    Example:
        >>> class MyClickHouseService(ClickHouseClientMixin):
        ...     DATABASE = "exness"
        ...
        ...     def __init__(self, client: Client | None = None):
        ...         self._init_client(client)
        ...
        ...     def query(self, sql: str):
        ...         return self.client.query(sql)
        ...
        >>> service = MyClickHouseService()
        >>> # service.client lazily creates connection
        >>> service.close()  # cleans up if we own the connection
    """

    _client: Client | None
    _owns_client: bool

    def _init_client(self, client: Client | None = None) -> None:
        """
        Initialize client state.

        Args:
            client: Optional ClickHouse client (creates one on first access if not provided)
        """
        self._client = client
        self._owns_client = client is None

    @property
    def client(self) -> Client:
        """Get or create ClickHouse client (lazy initialization)."""
        if self._client is None:
            self._client = get_client()
        return self._client

    def close(self) -> None:
        """Close client connection if we own it."""
        if self._owns_client and self._client is not None:
            self._client.close()
            self._client = None
