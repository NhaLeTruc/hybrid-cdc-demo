"""
Schema Mapper
Maps Cassandra types to warehouse-specific types
"""

from pathlib import Path
from typing import Dict, Any, Optional
import yaml
import structlog

logger = structlog.get_logger(__name__)


class SchemaMapper:
    """
    Maps Cassandra types to warehouse types based on configuration
    """

    def __init__(self):
        self.postgres_mappings: Dict[str, str] = {}
        self.clickhouse_mappings: Dict[str, str] = {}
        self.timescaledb_mappings: Dict[str, str] = {}

    def load_mappings(self, config_path: Optional[str] = None) -> None:
        """
        Load type mappings from YAML configuration

        Args:
            config_path: Path to schema-mappings.yaml
        """
        if config_path is None:
            config_path = Path(__file__).parent.parent.parent / "config" / "schema-mappings.yaml"

        try:
            with open(config_path) as f:
                mappings = yaml.safe_load(f)

            global_mappings = mappings.get("global_mappings", {})
            self.postgres_mappings = global_mappings.get("cassandra_to_postgres", {})
            self.clickhouse_mappings = global_mappings.get("cassandra_to_clickhouse", {})
            self.timescaledb_mappings = global_mappings.get("cassandra_to_timescaledb", self.postgres_mappings)

            logger.info("Schema mappings loaded")

        except Exception as e:
            logger.error("Failed to load schema mappings", error=str(e))
            self._use_defaults()

    def _use_defaults(self) -> None:
        """Use default type mappings"""
        self.postgres_mappings = {
            "UUID": "uuid",
            "TEXT": "text",
            "VARCHAR": "varchar",
            "INT": "integer",
            "BIGINT": "bigint",
            "TIMESTAMP": "timestamptz",
        }
        self.clickhouse_mappings = {
            "UUID": "UUID",
            "TEXT": "String",
            "VARCHAR": "String",
            "INT": "Int32",
            "BIGINT": "Int64",
            "TIMESTAMP": "DateTime64(3)",
        }
        self.timescaledb_mappings = self.postgres_mappings.copy()


# Module-level functions for convenience
def map_cassandra_to_postgres(cassandra_type: str) -> str:
    """Map Cassandra type to Postgres type"""
    mapper = SchemaMapper()
    mapper.load_mappings()
    return mapper.postgres_mappings.get(cassandra_type, "text")


def map_cassandra_to_clickhouse(cassandra_type: str) -> str:
    """Map Cassandra type to ClickHouse type"""
    mapper = SchemaMapper()
    mapper.load_mappings()
    return mapper.clickhouse_mappings.get(cassandra_type, "String")


def map_cassandra_to_timescaledb(cassandra_type: str) -> str:
    """Map Cassandra type to TimescaleDB type"""
    mapper = SchemaMapper()
    mapper.load_mappings()
    return mapper.timescaledb_mappings.get(cassandra_type, "text")


def convert_value(value: Any, cassandra_type: str, target: str) -> Any:
    """
    Convert value from Cassandra to target warehouse format

    Args:
        value: Value to convert
        cassandra_type: Cassandra type name
        target: Target warehouse (postgres, clickhouse, timescaledb)

    Returns:
        Converted value
    """
    # For this tech demo, most values pass through unchanged
    # Real implementation would handle type conversions

    if value is None:
        return None

    # UUID: keep as string
    if cassandra_type == "UUID":
        return str(value)

    # TIMESTAMP: keep as integer (microseconds)
    if cassandra_type == "TIMESTAMP":
        return value

    # Default: return as-is
    return value
