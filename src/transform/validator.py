"""
Schema validation for CDC events
Validates events against current schema and detects incompatibilities
"""

import structlog
from typing import Dict, Any, Optional, List
from src.models.event import ChangeEvent
from src.models.schema import TableSchema, SchemaChange, ChangeType

logger = structlog.get_logger(__name__)


class SchemaValidationError(Exception):
    """Raised when event validation fails due to schema incompatibility"""

    pass


class SchemaValidator:
    """
    Validates CDC events against table schemas

    Tracks schema versions per table and validates events
    against the current schema.
    """

    def __init__(self):
        """Initialize schema validator"""
        self._schemas: Dict[str, TableSchema] = {}
        logger.info("Schema validator initialized")

    def register_schema(self, schema: TableSchema) -> None:
        """
        Register or update a table schema

        Args:
            schema: TableSchema to register

        """
        key = f"{schema.keyspace}.{schema.table_name}"
        self._schemas[key] = schema
        logger.info(
            "Schema registered",
            keyspace=schema.keyspace,
            table=schema.table_name,
            version=schema.version,
        )

    def get_schema(self, keyspace: str, table_name: str) -> Optional[TableSchema]:
        """
        Get registered schema for a table

        Args:
            keyspace: Keyspace name
            table_name: Table name

        Returns:
            TableSchema if registered, None otherwise
        """
        key = f"{keyspace}.{table_name}"
        return self._schemas.get(key)

    def validate_event(self, event: ChangeEvent) -> None:
        """
        Validate event against registered schema

        Args:
            event: ChangeEvent to validate

        Raises:
            SchemaValidationError: If event is invalid for current schema
        """
        schema = self.get_schema(event.keyspace, event.table_name)

        if schema is None:
            # No schema registered yet - allow event (schema will be discovered)
            logger.debug(
                "No schema registered for table, allowing event",
                keyspace=event.keyspace,
                table=event.table_name,
            )
            return

        # Validate partition keys
        for pk in schema.partition_keys:
            if pk not in event.partition_key:
                raise SchemaValidationError(
                    f"Missing partition key '{pk}' in event for {schema.keyspace}.{schema.table_name}"
                )

        # Validate that event doesn't contain unknown columns
        event_columns = set(event.columns.keys())
        schema_columns = set(schema.columns.keys())

        unknown_columns = event_columns - schema_columns
        if unknown_columns:
            logger.warning(
                "Event contains unknown columns (schema may have changed)",
                keyspace=event.keyspace,
                table=event.table_name,
                unknown_columns=list(unknown_columns),
            )
            # Don't fail - this might be a schema change we need to detect

    def is_schema_compatible(
        self, old_schema: TableSchema, new_schema: TableSchema
    ) -> bool:
        """
        Check if schema change is compatible

        Args:
            old_schema: Previous schema version
            new_schema: New schema version

        Returns:
            True if all changes are compatible, False otherwise
        """
        changes = old_schema.compare(new_schema)

        if not changes:
            return True

        # Check if all changes are compatible
        for change in changes:
            if not change.is_compatible():
                logger.warning(
                    "Incompatible schema change detected",
                    keyspace=old_schema.keyspace,
                    table=old_schema.table_name,
                    change_type=change.change_type.value,
                    column=change.column_name,
                    old_type=change.old_type,
                    new_type=change.new_type,
                )
                return False

        return True

    def get_incompatible_changes(
        self, old_schema: TableSchema, new_schema: TableSchema
    ) -> List[SchemaChange]:
        """
        Get list of incompatible schema changes

        Args:
            old_schema: Previous schema version
            new_schema: New schema version

        Returns:
            List of incompatible SchemaChange objects
        """
        changes = old_schema.compare(new_schema)
        return [change for change in changes if not change.is_compatible()]

    def validate_column_type(
        self, column_name: str, value: Any, expected_type: str
    ) -> bool:
        """
        Validate that a column value matches expected type

        Args:
            column_name: Column name
            value: Column value
            expected_type: Expected CQL type

        Returns:
            True if type matches, False otherwise
        """
        if value is None:
            # NULL values are always valid
            return True

        type_lower = expected_type.lower()

        # Basic type validation
        type_checks = {
            "text": lambda v: isinstance(v, str),
            "varchar": lambda v: isinstance(v, str),
            "int": lambda v: isinstance(v, int),
            "bigint": lambda v: isinstance(v, int),
            "double": lambda v: isinstance(v, (int, float)),
            "float": lambda v: isinstance(v, (int, float)),
            "decimal": lambda v: isinstance(v, (int, float)),
            "boolean": lambda v: isinstance(v, bool),
            "uuid": lambda v: True,  # UUID validation requires uuid module
            "timestamp": lambda v: True,  # Timestamp validation complex
        }

        # Check if we have a validator for this type
        for type_pattern, validator in type_checks.items():
            if type_pattern in type_lower:
                if not validator(value):
                    logger.warning(
                        "Column type mismatch",
                        column=column_name,
                        expected_type=expected_type,
                        actual_value_type=type(value).__name__,
                    )
                    return False
                return True

        # Unknown type - allow it (might be complex type)
        return True

    def validate_event_types(self, event: ChangeEvent) -> List[str]:
        """
        Validate all column types in event

        Args:
            event: ChangeEvent to validate

        Returns:
            List of column names with type mismatches
        """
        schema = self.get_schema(event.keyspace, event.table_name)

        if schema is None:
            return []

        mismatches = []

        for col_name, col_value in event.columns.items():
            if col_name in schema.columns:
                expected_type = schema.columns[col_name]
                if not self.validate_column_type(col_name, col_value, expected_type):
                    mismatches.append(col_name)

        return mismatches


# Global validator instance
_validator = SchemaValidator()


def get_validator() -> SchemaValidator:
    """Get global schema validator instance"""
    return _validator


def validate_event(event: ChangeEvent) -> None:
    """
    Validate event using global validator

    Args:
        event: ChangeEvent to validate

    Raises:
        SchemaValidationError: If validation fails
    """
    _validator.validate_event(event)


def register_schema(schema: TableSchema) -> None:
    """
    Register schema with global validator

    Args:
        schema: TableSchema to register
    """
    _validator.register_schema(schema)
