"""
SchemaVersion Data Model - Cassandra table schema tracking
Based on specs/001-secure-cdc-pipeline/data-model.md
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional
from uuid import UUID, uuid4


class ChangeType(str, Enum):
    """Type of schema change"""

    ADD_COLUMN = "ADD_COLUMN"
    DROP_COLUMN = "DROP_COLUMN"
    ALTER_TYPE = "ALTER_TYPE"


# Alias for compatibility with tests
SchemaChangeType = ChangeType


@dataclass
class ColumnDef:
    """
    Cassandra column definition

    Attributes:
        name: Column name
        cql_type: Cassandra CQL type (e.g., "TEXT", "INT", "UUID")
        is_partition_key: Whether this is a partition key column
        is_clustering_key: Whether this is a clustering key column
        is_static: Whether this is a static column
    """

    name: str
    cql_type: str
    is_partition_key: bool = False
    is_clustering_key: bool = False
    is_static: bool = False


@dataclass
class SchemaChange:
    """
    Represents a schema change between versions

    Attributes:
        change_type: Type of change (ADD/DROP/ALTER)
        column_name: Name of affected column
        old_type: Previous CQL type (None for ADD)
        new_type: New CQL type (None for DROP)
    """

    change_type: ChangeType
    column_name: str
    old_type: Optional[str] = None
    new_type: Optional[str] = None

    def is_compatible(self) -> bool:
        """
        Determine if this schema change is compatible (safe to apply automatically)

        Compatible changes:
        - ADD COLUMN (always safe - NULL values for existing rows)
        - DROP COLUMN (always safe - data is preserved, column ignored)
        - ALTER TYPE with widening conversions (int->bigint, decimal->double, etc.)

        Incompatible changes:
        - ALTER TYPE with narrowing conversions (bigint->int, text->int, etc.)
        - ALTER TYPE for partition/clustering keys (requires rebuild)
        """
        if self.change_type in (ChangeType.ADD_COLUMN, ChangeType.DROP_COLUMN):
            return True

        if self.change_type == ChangeType.ALTER_TYPE:
            # Check if type conversion is compatible
            return self._is_compatible_type_change(self.old_type, self.new_type)

        return False

    def _is_compatible_type_change(self, old_type: Optional[str], new_type: Optional[str]) -> bool:
        """Check if a type change is compatible (safe widening)"""
        if old_type is None or new_type is None:
            return False

        # Normalize types to lowercase
        old = old_type.lower()
        new = new_type.lower()

        # Compatible widening conversions
        compatible_conversions = {
            ("int", "bigint"),
            ("float", "double"),
            ("decimal", "double"),
            ("text", "varchar"),
            ("varchar", "text"),
        }

        return (old, new) in compatible_conversions

    def to_dict(self) -> Dict[str, any]:
        """Convert to dictionary for serialization"""
        return {
            "change_type": (
                self.change_type.value if isinstance(self.change_type, Enum) else self.change_type
            ),
            "column_name": self.column_name,
            "old_type": self.old_type,
            "new_type": self.new_type,
        }


@dataclass
class SchemaVersion:
    """
    Snapshot of Cassandra table schema at a point in time

    Attributes:
        schema_id: Unique identifier for this schema version
        table_name: Cassandra table name
        keyspace: Cassandra keyspace
        version_number: Monotonically increasing version (1, 2, 3...)
        columns: Column definitions {name: ColumnDef}
        partition_keys: Ordered list of partition key columns
        clustering_keys: Ordered list of clustering key columns
        detected_at: When this schema version was detected
        previous_version: Previous schema version number (None for initial)
        schema_changes: Diff from previous version (empty for initial)
    """

    schema_id: UUID
    table_name: str
    keyspace: str
    version_number: int
    columns: Dict[str, ColumnDef]
    partition_keys: List[str]
    clustering_keys: List[str]
    detected_at: datetime
    previous_version: Optional[int] = None
    schema_changes: List[SchemaChange] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Validate SchemaVersion after initialization"""
        # Validate version number
        if self.version_number < 1:
            raise ValueError("version_number must be >= 1")

        # Validate partition keys
        if not self.partition_keys:
            raise ValueError("partition_keys must be non-empty")

        # Validate all keys exist in columns
        for pk in self.partition_keys:
            if pk not in self.columns:
                raise ValueError(f"Partition key {pk} not found in columns")

        for ck in self.clustering_keys:
            if ck not in self.columns:
                raise ValueError(f"Clustering key {ck} not found in columns")

        # Validate schema_changes only for non-initial versions
        if self.version_number > 1 and self.previous_version is None:
            raise ValueError("previous_version required for non-initial versions")

    @classmethod
    def create_initial(
        cls,
        table_name: str,
        keyspace: str,
        columns: Dict[str, ColumnDef],
        partition_keys: List[str],
        clustering_keys: List[str],
    ) -> "SchemaVersion":
        """
        Create initial schema version (version 1)

        Args:
            table_name: Cassandra table name
            keyspace: Cassandra keyspace
            columns: Column definitions
            partition_keys: Partition key column names
            clustering_keys: Clustering key column names

        Returns:
            SchemaVersion instance with version_number=1
        """
        return cls(
            schema_id=uuid4(),
            table_name=table_name,
            keyspace=keyspace,
            version_number=1,
            columns=columns,
            partition_keys=partition_keys,
            clustering_keys=clustering_keys,
            detected_at=datetime.now(),
            previous_version=None,
            schema_changes=[],
        )

    def evolve(
        self,
        new_columns: Dict[str, ColumnDef],
        partition_keys: List[str],
        clustering_keys: List[str],
    ) -> "SchemaVersion":
        """
        Create new schema version with changes detected

        Args:
            new_columns: Updated column definitions
            partition_keys: Updated partition keys
            clustering_keys: Updated clustering keys

        Returns:
            New SchemaVersion with incremented version_number and detected changes
        """
        changes = self._detect_changes(new_columns)

        return SchemaVersion(
            schema_id=uuid4(),
            table_name=self.table_name,
            keyspace=self.keyspace,
            version_number=self.version_number + 1,
            columns=new_columns,
            partition_keys=partition_keys,
            clustering_keys=clustering_keys,
            detected_at=datetime.now(),
            previous_version=self.version_number,
            schema_changes=changes,
        )

    def _detect_changes(self, new_columns: Dict[str, ColumnDef]) -> List[SchemaChange]:
        """
        Detect schema changes between current and new columns

        Args:
            new_columns: New column definitions

        Returns:
            List of SchemaChange objects
        """
        changes: List[SchemaChange] = []

        # Detect added columns
        for col_name, col_def in new_columns.items():
            if col_name not in self.columns:
                changes.append(
                    SchemaChange(
                        change_type=ChangeType.ADD_COLUMN,
                        column_name=col_name,
                        old_type=None,
                        new_type=col_def.cql_type,
                    )
                )

        # Detect dropped or altered columns
        for col_name, col_def in self.columns.items():
            if col_name not in new_columns:
                changes.append(
                    SchemaChange(
                        change_type=ChangeType.DROP_COLUMN,
                        column_name=col_name,
                        old_type=col_def.cql_type,
                        new_type=None,
                    )
                )
            elif col_def.cql_type != new_columns[col_name].cql_type:
                changes.append(
                    SchemaChange(
                        change_type=ChangeType.ALTER_TYPE,
                        column_name=col_name,
                        old_type=col_def.cql_type,
                        new_type=new_columns[col_name].cql_type,
                    )
                )

        return changes

    def to_dict(self) -> dict:
        """Convert to dictionary for storage/serialization"""
        return {
            "schema_id": str(self.schema_id),
            "table_name": self.table_name,
            "keyspace": self.keyspace,
            "version_number": self.version_number,
            "columns": {name: vars(col) for name, col in self.columns.items()},
            "partition_keys": self.partition_keys,
            "clustering_keys": self.clustering_keys,
            "detected_at": self.detected_at.isoformat(),
            "previous_version": self.previous_version,
            "schema_changes": [vars(change) for change in self.schema_changes],
        }


@dataclass
class TableSchema:
    """
    Simplified table schema representation for testing and comparison

    Attributes:
        keyspace: Cassandra keyspace name
        table_name: Table name
        columns: Column name to type mapping
        partition_keys: List of partition key column names
        clustering_keys: List of clustering key column names
        version: Schema version number (optional)
    """

    keyspace: str
    table_name: str
    columns: Dict[str, str]
    partition_keys: List[str]
    clustering_keys: List[str]
    version: int = 1

    def compare(self, other: "TableSchema") -> List[SchemaChange]:
        """
        Compare this schema with another and detect changes

        Args:
            other: The new schema to compare against

        Returns:
            List of SchemaChange objects representing the differences
        """
        changes: List[SchemaChange] = []

        # Detect partition key changes (incompatible)
        if self.partition_keys != other.partition_keys:
            # Partition key change is incompatible - treat as ALTER TYPE with incompatibility
            for pk in self.partition_keys:
                if pk not in other.partition_keys:
                    changes.append(
                        SchemaChange(
                            change_type=ChangeType.ALTER_TYPE,
                            column_name=pk,
                            old_type="partition_key",
                            new_type="not_partition_key",
                        )
                    )

        # Detect clustering key changes
        if self.clustering_keys != other.clustering_keys:
            for ck in self.clustering_keys:
                if ck not in other.clustering_keys:
                    changes.append(
                        SchemaChange(
                            change_type=ChangeType.ALTER_TYPE,
                            column_name=ck,
                            old_type="clustering_key",
                            new_type="not_clustering_key",
                        )
                    )

        # Detect added columns
        for col_name, col_type in other.columns.items():
            if col_name not in self.columns:
                changes.append(
                    SchemaChange(
                        change_type=ChangeType.ADD_COLUMN,
                        column_name=col_name,
                        old_type=None,
                        new_type=col_type,
                    )
                )

        # Detect dropped or altered columns
        for col_name, col_type in self.columns.items():
            if col_name not in other.columns:
                changes.append(
                    SchemaChange(
                        change_type=ChangeType.DROP_COLUMN,
                        column_name=col_name,
                        old_type=col_type,
                        new_type=None,
                    )
                )
            elif col_type != other.columns[col_name]:
                changes.append(
                    SchemaChange(
                        change_type=ChangeType.ALTER_TYPE,
                        column_name=col_name,
                        old_type=col_type,
                        new_type=other.columns[col_name],
                    )
                )

        return changes

    def with_version(self, new_version: int) -> "TableSchema":
        """
        Create a copy of this schema with a new version number

        Args:
            new_version: The new version number

        Returns:
            New TableSchema instance with updated version
        """
        return TableSchema(
            keyspace=self.keyspace,
            table_name=self.table_name,
            columns=self.columns.copy(),
            partition_keys=self.partition_keys.copy(),
            clustering_keys=self.clustering_keys.copy(),
            version=new_version,
        )

    def get_hash(self) -> str:
        """
        Calculate a hash of the schema for comparison

        Returns:
            Hash string representing the schema structure
        """
        import hashlib
        import json

        # Create a deterministic representation of the schema
        schema_dict = {
            "keyspace": self.keyspace,
            "table_name": self.table_name,
            "columns": sorted(self.columns.items()),
            "partition_keys": self.partition_keys,
            "clustering_keys": self.clustering_keys,
        }

        # Serialize to JSON string (sorted for determinism)
        schema_json = json.dumps(schema_dict, sort_keys=True)

        # Calculate SHA256 hash
        return hashlib.sha256(schema_json.encode()).hexdigest()
