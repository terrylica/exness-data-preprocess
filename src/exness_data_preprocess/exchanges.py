"""
Exchange registry for dynamic session column generation (v1.6.0).

Schema Version: v1.6.0
Purpose: Single source of truth for all supported exchanges and metadata
Pattern: Adding new exchange requires ONLY updating EXCHANGES dict

Architecture:
- Dataclass with frozen=True for immutability
- ISO 10383 MIC codes for exchange identification
- IANA timezone database for DST handling via exchange_calendars

Error Handling: Raise exceptions on invalid exchange lookup (no fallbacks)
"""

from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class ExchangeConfig:
    """
    Immutable configuration for a single exchange.

    Attributes:
        code: ISO 10383 MIC code (e.g., "XNYS" for NYSE)
        name: Full exchange name (e.g., "New York Stock Exchange")
        currency: Primary currency (e.g., "USD")
        timezone: IANA timezone (e.g., "America/New_York")
        country: Country name (e.g., "United States")
        open_hour: Trading start hour in local time (24-hour format)
        open_minute: Trading start minute in local time
        close_hour: Trading close hour in local time (24-hour format)
        close_minute: Trading close minute in local time

    Validation: frozen=True prevents modification after instantiation
    """

    code: str
    name: str
    currency: str
    timezone: str
    country: str
    open_hour: int
    open_minute: int
    close_hour: int
    close_minute: int


# Registry: v1.6.0 supports 10 major forex exchanges
# Order: NYSE, LSE (existing v1.4.0) + 8 new exchanges
# Maintenance: Add new exchanges here ONLY (propagates to schema + processor)
EXCHANGES: Dict[str, ExchangeConfig] = {
    # Existing v1.4.0 exchanges (maintain backward compat)
    "nyse": ExchangeConfig(
        code="XNYS",
        name="New York Stock Exchange",
        currency="USD",
        timezone="America/New_York",
        country="United States",
        open_hour=9,
        open_minute=30,
        close_hour=16,
        close_minute=0,
    ),
    "lse": ExchangeConfig(
        code="XLON",
        name="London Stock Exchange",
        currency="GBP",
        timezone="Europe/London",
        country="United Kingdom",
        open_hour=8,
        open_minute=0,
        close_hour=16,
        close_minute=30,
    ),
    # New v1.6.0 exchanges (8 additions)
    "xswx": ExchangeConfig(
        code="XSWX",
        name="SIX Swiss Exchange",
        currency="CHF",
        timezone="Europe/Zurich",
        country="Switzerland",
        open_hour=9,
        open_minute=0,
        close_hour=17,
        close_minute=30,
    ),
    "xfra": ExchangeConfig(
        code="XFRA",
        name="Frankfurt Stock Exchange",
        currency="EUR",
        timezone="Europe/Berlin",
        country="Germany",
        open_hour=9,
        open_minute=0,
        close_hour=17,
        close_minute=30,
    ),
    "xtse": ExchangeConfig(
        code="XTSE",
        name="Toronto Stock Exchange",
        currency="CAD",
        timezone="America/Toronto",
        country="Canada",
        open_hour=9,
        open_minute=30,
        close_hour=16,
        close_minute=0,
    ),
    "xnze": ExchangeConfig(
        code="XNZE",
        name="New Zealand Exchange",
        currency="NZD",
        timezone="Pacific/Auckland",
        country="New Zealand",
        open_hour=10,
        open_minute=0,
        close_hour=16,
        close_minute=45,
    ),
    "xtks": ExchangeConfig(
        code="XTKS",
        name="Tokyo Stock Exchange",
        currency="JPY",
        timezone="Asia/Tokyo",
        country="Japan",
        open_hour=9,
        open_minute=0,
        close_hour=15,
        close_minute=0,
    ),
    "xasx": ExchangeConfig(
        code="XASX",
        name="Australian Securities Exchange",
        currency="AUD",
        timezone="Australia/Sydney",
        country="Australia",
        open_hour=10,
        open_minute=0,
        close_hour=16,
        close_minute=0,
    ),
    "xhkg": ExchangeConfig(
        code="XHKG",
        name="Hong Kong Stock Exchange",
        currency="HKD",
        timezone="Asia/Hong_Kong",
        country="Hong Kong",
        open_hour=9,
        open_minute=30,
        close_hour=16,
        close_minute=0,
    ),
    "xses": ExchangeConfig(
        code="XSES",
        name="Singapore Exchange",
        currency="SGD",
        timezone="Asia/Singapore",
        country="Singapore",
        open_hour=9,
        open_minute=0,
        close_hour=17,
        close_minute=0,
    ),
}


def get_exchange_names() -> list[str]:
    """
    Get list of all exchange names (registry keys).

    Returns:
        List of lowercase exchange names (e.g., ["nyse", "lse", ...])

    Example:
        >>> names = get_exchange_names()
        >>> len(names)
        10
        >>> "nyse" in names
        True
    """
    return list(EXCHANGES.keys())


def get_exchange_config(name: str) -> ExchangeConfig:
    """
    Get configuration for specific exchange.

    Args:
        name: Lowercase exchange name (e.g., "nyse", "lse")

    Returns:
        ExchangeConfig with code, name, currency, timezone, country

    Raises:
        ValueError: If exchange name not in registry (no fallbacks)

    Example:
        >>> config = get_exchange_config("nyse")
        >>> config.code
        'XNYS'
        >>> config.currency
        'USD'

        >>> get_exchange_config("invalid")
        ValueError: Unknown exchange: invalid. Available: nyse, lse, ...
    """
    if name not in EXCHANGES:
        available = ", ".join(EXCHANGES.keys())
        raise ValueError(f"Unknown exchange: {name}. Available: {available}")
    return EXCHANGES[name]
