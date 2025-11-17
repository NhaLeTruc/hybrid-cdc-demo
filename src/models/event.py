"""
ChangeEvent Data Model - CDC event representation
Based on specs/001-secure-cdc-pipeline/data-model.md
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional
from uuid import UUID, uuid4


class EventType(str, Enum):
    """Type of CDC change operation"""

    INSERT = "INSERT"
    UPDATE = "UPDATE"
    DELETE = "DELETE"


@dataclass
class ChangeEvent:
    """
    Represents a single data modification (INSERT, UPDATE, DELETE) captured from Cassandra

    Attributes:
        event_id: Unique identifier for deduplication and correlation
        event_type: Type of change operation (INSERT, UPDATE, DELETE)
        table_name: Cassandra table name (e.g., "users", "orders")
        keyspace: Cassandra keyspace (database)
        partition_key: Partition key columns and values {column: value}
        clustering_key: Clustering key columns and values (empty for single-row partition)
        columns: Changed column values {column: value} (empty for DELETE)
        timestamp_micros: Cassandra writetime (microseconds since epoch)
        ttl_seconds: Time-to-live for inserted row (None if no TTL)
        captured_at: When pipeline read this event from commitlog
    """

    event_id: UUID
    event_type: EventType
    table_name: str
    keyspace: str
    partition_key: Dict[str, Any]
    clustering_key: Dict[str, Any]
    columns: Dict[str, Any]
    timestamp_micros: int
    captured_at: datetime
    ttl_seconds: Optional[int] = None

    def __post_init__(self) -> None:
        """Validate ChangeEvent after initialization"""
        # Validate timestamp
        if self.timestamp_micros <= 0:
            raise ValueError("timestamp_micros must be positive")

        # Validate partition key
        if not self.partition_key:
            raise ValueError("partition_key must be non-empty")

        # Validate columns based on event type
        if self.event_type != EventType.DELETE and not self.columns:
            raise ValueError(f"columns required for {self.event_type} events")

        # Validate captured_at
        if self.captured_at > datetime.now():
            raise ValueError("captured_at cannot be in the future")

    @classmethod
    def create(
        cls,
        event_type: EventType,
        table_name: str,
        keyspace: str,
        partition_key: Dict[str, Any],
        columns: Dict[str, Any],
        timestamp_micros: int,
        clustering_key: Optional[Dict[str, Any]] = None,
        ttl_seconds: Optional[int] = None,
    ) -> "ChangeEvent":
        """
        Factory method to create a ChangeEvent with auto-generated ID and timestamp

        Args:
            event_type: Type of change (INSERT, UPDATE, DELETE)
            table_name: Cassandra table name
            keyspace: Cassandra keyspace
            partition_key: Partition key values
            columns: Column values
            timestamp_micros: Cassandra writetime
            clustering_key: Clustering key values (optional)
            ttl_seconds: TTL for row (optional)

        Returns:
            ChangeEvent instance
        """
        return cls(
            event_id=uuid4(),
            event_type=event_type,
            table_name=table_name,
            keyspace=keyspace,
            partition_key=partition_key,
            clustering_key=clustering_key or {},
            columns=columns,
            timestamp_micros=timestamp_micros,
            ttl_seconds=ttl_seconds,
            captured_at=datetime.now(),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert ChangeEvent to dictionary (for serialization)"""
        return {
            "event_id": str(self.event_id),
            "event_type": self.event_type.value,
            "table_name": self.table_name,
            "keyspace": self.keyspace,
            "partition_key": self.partition_key,
            "clustering_key": self.clustering_key,
            "columns": self.columns,
            "timestamp_micros": self.timestamp_micros,
            "ttl_seconds": self.ttl_seconds,
            "captured_at": self.captured_at.isoformat(),
        }

    @property
    def event_key(self) -> str:
        """Unique key for deduplication (table + partition + clustering + timestamp)"""
        pk_str = "_".join(str(v) for v in self.partition_key.values())
        ck_str = "_".join(str(v) for v in self.clustering_key.values())
        return f"{self.keyspace}.{self.table_name}:{pk_str}:{ck_str}:{self.timestamp_micros}"
