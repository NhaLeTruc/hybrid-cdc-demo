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
