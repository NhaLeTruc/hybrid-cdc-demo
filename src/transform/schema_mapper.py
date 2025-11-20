"""
Schema Mapper
Maps Cassandra types to warehouse-specific types
Handles schema evolution and incompatibility detection
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog
import yaml

from src.models.schema import ChangeType, SchemaChange, TableSchema

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

            # TimescaleDB inherits from Postgres, then overrides with specific mappings
            self.timescaledb_mappings = self.postgres_mappings.copy()
            timescaledb_overrides = global_mappings.get("cassandra_to_timescaledb", {})
            self.timescaledb_mappings.update(timescaledb_overrides)

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
            "DECIMAL": "numeric",
            "DOUBLE": "double precision",
            "FLOAT": "real",
            "BOOLEAN": "boolean",
        }
        self.clickhouse_mappings = {
            "UUID": "UUID",
            "TEXT": "String",
            "VARCHAR": "String",
            "INT": "Int32",
            "BIGINT": "Int64",
            "TIMESTAMP": "DateTime64(3)",
            "DECIMAL": "Decimal(38, 10)",
            "DOUBLE": "Float64",
            "FLOAT": "Float32",
            "BOOLEAN": "UInt8",
        }
        self.timescaledb_mappings = self.postgres_mappings.copy()

    def apply_schema_change(
        self,
        schema: TableSchema,
        change: SchemaChange,
        target_warehouse: str,
    ) -> Dict[str, str]:
        """
        Apply schema change to get updated column mappings

        Args:
            schema: Current table schema
            change: Schema change to apply
            target_warehouse: Target warehouse (postgres, clickhouse, timescaledb)

        Returns:
            Updated column name -> warehouse type mappings
        """
        mappings = self._get_target_mappings(target_warehouse)
        result = {}

        # Start with existing columns
        for col_name, col_type in schema.columns.items():
            warehouse_type = mappings.get(col_type.upper(), "text")
            result[col_name] = warehouse_type

        # Apply the change
        if change.change_type == ChangeType.ADD_COLUMN:
            # Add new column mapping
            if change.new_type:
                warehouse_type = mappings.get(change.new_type.upper(), "text")
                result[change.column_name] = warehouse_type

        elif change.change_type == ChangeType.DROP_COLUMN:
            # Remove column from mappings
            result.pop(change.column_name, None)

        elif change.change_type == ChangeType.ALTER_TYPE:
            # Update column type mapping
            if change.new_type:
                warehouse_type = mappings.get(change.new_type.upper(), "text")
                result[change.column_name] = warehouse_type

        return result

    def _get_target_mappings(self, target_warehouse: str) -> Dict[str, str]:
        """Get type mappings for target warehouse"""
        if target_warehouse.lower() == "postgres":
            return self.postgres_mappings
        elif target_warehouse.lower() == "clickhouse":
            return self.clickhouse_mappings
        elif target_warehouse.lower() == "timescaledb":
            return self.timescaledb_mappings
        else:
            return self.postgres_mappings

    def detect_incompatible_types(self, cassandra_type: str, target_warehouse: str) -> bool:
        """
        Detect if a Cassandra type cannot be mapped to target warehouse

        Args:
            cassandra_type: Cassandra CQL type
            target_warehouse: Target warehouse name

        Returns:
            True if incompatible (no mapping exists), False if compatible
        """
        mappings = self._get_target_mappings(target_warehouse)
        type_upper = cassandra_type.upper()

        # Check for complex/unsupported types
        unsupported_patterns = [
            "FROZEN<",  # Frozen collections
            "TUPLE<",  # Tuples
            "COUNTER",  # Counters
        ]

        for pattern in unsupported_patterns:
            if pattern in type_upper:
                logger.warning(
                    "Unsupported Cassandra type detected",
                    cassandra_type=cassandra_type,
                    target=target_warehouse,
                )
                return True

        # Check if mapping exists
        if type_upper not in mappings:
            logger.warning(
                "No type mapping found",
                cassandra_type=cassandra_type,
                target=target_warehouse,
            )
            return True

        return False

    def get_incompatible_columns(self, schema: TableSchema, target_warehouse: str) -> List[str]:
        """
        Get list of columns with incompatible types

        Args:
            schema: Table schema to check
            target_warehouse: Target warehouse name

        Returns:
            List of column names with incompatible types
        """
        incompatible = []

        for col_name, col_type in schema.columns.items():
            if self.detect_incompatible_types(col_type, target_warehouse):
                incompatible.append(col_name)

        return incompatible

    def is_schema_change_compatible(self, change: SchemaChange, target_warehouse: str) -> bool:
        """
        Check if a schema change is compatible with target warehouse

        Args:
            change: Schema change to check
            target_warehouse: Target warehouse name

        Returns:
            True if compatible, False if incompatible
        """
        # First check if the change itself is compatible
        if not change.is_compatible():
            return False

        # For ADD COLUMN, check if new type is supported
        if change.change_type == ChangeType.ADD_COLUMN and change.new_type:
            return not self.detect_incompatible_types(change.new_type, target_warehouse)

        # For ALTER TYPE, check if new type is supported
        if change.change_type == ChangeType.ALTER_TYPE and change.new_type:
            return not self.detect_incompatible_types(change.new_type, target_warehouse)

        # DROP COLUMN is always compatible
        return True


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
