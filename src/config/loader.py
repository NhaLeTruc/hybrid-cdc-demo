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
