"""
Configuration Loader - Load YAML configuration files
"""

import logging
from pathlib import Path
from typing import Any, Dict

import yaml

logger = logging.getLogger(__name__)


def load_yaml_config(file_path: str) -> Dict[str, Any]:
    """
    Load YAML configuration file

    Args:
        file_path: Path to YAML file

    Returns:
        Dictionary containing configuration

    Raises:
        FileNotFoundError: If configuration file doesn't exist
        yaml.YAMLError: If YAML parsing fails
    """
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"Configuration file not found: {file_path}")

    try:
        with open(path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        if config is None:
            logger.warning(f"Empty configuration file: {file_path}")
            return {}

        logger.info(f"Loaded configuration from {file_path}")
        return config

    except yaml.YAMLError as e:
        logger.error(f"Failed to parse YAML file {file_path}: {e}")
        raise


def merge_configs(*configs: Dict[str, Any]) -> Dict[str, Any]:
    """
    Merge multiple configuration dictionaries (later configs override earlier ones)

    Args:
        *configs: Variable number of configuration dictionaries

    Returns:
        Merged configuration dictionary
    """
    merged = {}

    for config in configs:
        if not config:
            continue
        _deep_merge(merged, config)

    return merged


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> None:
    """
    Deep merge override dictionary into base dictionary (in-place)

    Args:
        base: Base dictionary (modified in-place)
        override: Override dictionary
    """
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            # Recursively merge nested dictionaries
            _deep_merge(base[key], value)
        else:
            # Override value
            base[key] = value


def load_masking_rules(file_path: str) -> Dict[str, Any]:
    """
    Load PII/PHI masking rules from YAML file

    Args:
        file_path: Path to masking-rules.yaml

    Returns:
        Dictionary containing masking rules per table
    """
    return load_yaml_config(file_path)


def load_schema_mappings(file_path: str) -> Dict[str, Any]:
    """
    Load Cassandra → warehouse type mappings from YAML file

    Args:
        file_path: Path to schema-mappings.yaml

    Returns:
        Dictionary containing type mappings per table
    """
    return load_yaml_config(file_path)


def load_config(config_path: str | None = None):
    """
    Load CDC pipeline configuration from YAML file or environment variables.

    This is the main entry point for loading configuration. It supports:
    - Loading from YAML file if config_path is provided
    - Loading from environment variables if config_path is None
    - Merging YAML config with environment variable overrides

    Args:
        config_path: Optional path to YAML config file. If None, uses environment variables.

    Returns:
        CDCSettings: Validated configuration object

    Raises:
        FileNotFoundError: If config file specified but not found
        yaml.YAMLError: If YAML parsing fails
        ValidationError: If configuration validation fails

    Examples:
        >>> # Load from environment variables
        >>> config = load_config()

        >>> # Load from YAML file
        >>> config = load_config("config/pipeline.yaml")
    """
    from src.config.settings import CDCSettings

    if config_path:
        # Load from YAML file
        try:
            yaml_config = load_yaml_config(config_path)
            logger.info(f"Loaded configuration from {config_path}")

            # Create CDCSettings from YAML, allowing env vars to override
            config = CDCSettings(**yaml_config)
        except FileNotFoundError as e:
            logger.error(f"Configuration file not found: {config_path}")
            raise
        except yaml.YAMLError as e:
            logger.error(f"Invalid YAML in configuration file: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to load configuration from {config_path}: {e}")
            raise
    else:
        # Load from environment variables
        try:
            config = CDCSettings()
            logger.info("Loaded configuration from environment variables")
        except Exception as e:
            logger.error(f"Failed to load configuration from environment: {e}")
            raise

    logger.debug(f"Configuration loaded successfully")
    return config
