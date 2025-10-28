"""
Config file support for exness-data-preprocess.

Loads user preferences from ~/.exness-preprocess.yaml with Pydantic validation.
Config values override defaults but are overridden by explicit CLI flags.

Example config file (~/.exness-preprocess.yaml):
    base_dir: ~/eon/exness-data
    default_pair: EURUSD
    default_timeframe: 1h

Usage:
    >>> from exness_data_preprocess.config import load_config
    >>> config = load_config()  # Returns None if file doesn't exist
    >>> if config:
    ...     print(f"Base dir: {config.base_dir}")
"""

from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field, field_validator

from exness_data_preprocess.models import PairType, TimeframeType


class ConfigModel(BaseModel):
    """
    User configuration loaded from ~/.exness-preprocess.yaml.

    Attributes:
        base_dir: Default base directory for data storage
        default_pair: Default currency pair for CLI commands
        default_timeframe: Default OHLC timeframe for queries

    Example:
        >>> config = ConfigModel(
        ...     base_dir="~/eon/exness-data",
        ...     default_pair="EURUSD",
        ...     default_timeframe="1h"
        ... )
        >>> print(config.base_dir)  # Path object with expanduser() applied
    """

    base_dir: Optional[Path] = Field(
        default=None,
        description="Default base directory for data storage (supports ~ expansion)"
    )
    default_pair: Optional[PairType] = Field(
        default=None,
        description="Default currency pair for CLI commands"
    )
    default_timeframe: Optional[TimeframeType] = Field(
        default=None,
        description="Default OHLC timeframe for queries"
    )

    @field_validator('base_dir', mode='before')
    @classmethod
    def expand_base_dir(cls, v: Optional[str]) -> Optional[Path]:
        """Expand ~ and convert to absolute Path."""
        if v is None:
            return None
        return Path(v).expanduser().resolve()

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "base_dir": "~/eon/exness-data",
                    "default_pair": "EURUSD",
                    "default_timeframe": "1h"
                }
            ]
        }
    }


def get_default_config_path() -> Path:
    """
    Get default config file path.

    Returns:
        Path to ~/.exness-preprocess.yaml

    Example:
        >>> path = get_default_config_path()
        >>> print(path)  # /Users/username/.exness-preprocess.yaml
    """
    return Path.home() / ".exness-preprocess.yaml"


def load_config(path: Optional[Path] = None) -> Optional[ConfigModel]:
    """
    Load config file with Pydantic validation.

    Args:
        path: Custom config file path (default: ~/.exness-preprocess.yaml)

    Returns:
        ConfigModel if file exists and is valid, None if file doesn't exist

    Raises:
        yaml.YAMLError: If YAML syntax is invalid
        pydantic.ValidationError: If config values are invalid

    Example:
        >>> config = load_config()
        >>> if config:
        ...     print(f"Loaded config from {get_default_config_path()}")
        >>> else:
        ...     print("No config file found, using defaults")
    """
    config_path = path or get_default_config_path()

    # Return None if file doesn't exist (not an error)
    if not config_path.exists():
        return None

    # Load YAML file
    with open(config_path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)

    # Validate with Pydantic (raises ValidationError if invalid)
    return ConfigModel(**data)
