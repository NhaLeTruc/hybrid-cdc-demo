"""
ReplicationOffset Data Model - Tracks CDC pipeline progress
Based on specs/001-secure-cdc-pipeline/data-model.md
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4


class Destination(str, Enum):
    """Destination warehouse type"""

    POSTGRES = "POSTGRES"
    CLICKHOUSE = "CLICKHOUSE"
    TIMESCALEDB = "TIMESCALEDB"


@dataclass
class ReplicationOffset:
    """
    Tracks pipeline progress per Cassandra partition and per destination warehouse

    Attributes:
        offset_id: Unique identifier for this offset record
        table_name: Cassandra table being replicated
        keyspace: Cassandra keyspace
        partition_id: Cassandra partition token range identifier
        destination: Which warehouse this offset applies to
        commitlog_file: Cassandra commitlog file path (e.g., "CommitLog-7-123456.log")
        commitlog_position: Byte offset within commitlog file
        last_event_timestamp_micros: Timestamp of last successfully replicated event
        last_committed_at: When this offset was committed (for lag calculation)
        events_replicated_count: Total events replicated for this partition (counter)
    """

    offset_id: UUID
    table_name: str
    keyspace: str
    partition_id: int
    destination: Destination
    commitlog_file: str
    commitlog_position: int
    last_event_timestamp_micros: int
    last_committed_at: datetime
    events_replicated_count: int

    def __post_init__(self) -> None:
        """Validate ReplicationOffset after initialization"""
        # Validate partition_id (int64 range)
        if not (-9223372036854775808 <= self.partition_id <= 9223372036854775807):
            raise ValueError("partition_id must be within int64 range")

        # Validate commitlog_position
        if self.commitlog_position < 0:
            raise ValueError("commitlog_position must be non-negative")

        # Validate timestamp
        if self.last_event_timestamp_micros < 0:
            raise ValueError("last_event_timestamp_micros must be non-negative")

        # Validate committed_at
        if self.last_committed_at > datetime.now():
            raise ValueError("last_committed_at cannot be in the future")

        # Validate events count
        if self.events_replicated_count < 0:
            raise ValueError("events_replicated_count must be non-negative")

    @classmethod
    def create(
        cls,
        table_name: str,
        keyspace: str,
        partition_id: int,
        destination: Destination,
        commitlog_file: str,
        commitlog_position: int,
        last_event_timestamp_micros: int,
        events_replicated_count: int = 0,
    ) -> "ReplicationOffset":
        """
        Factory method to create a ReplicationOffset with auto-generated ID and timestamp

        Args:
            table_name: Cassandra table name
            keyspace: Cassandra keyspace
            partition_id: Partition token range ID
            destination: Target warehouse
            commitlog_file: Commitlog file path
            commitlog_position: Byte offset in file
            last_event_timestamp_micros: Last event timestamp
            events_replicated_count: Event counter

        Returns:
            ReplicationOffset instance
        """
        return cls(
            offset_id=uuid4(),
            table_name=table_name,
            keyspace=keyspace,
            partition_id=partition_id,
            destination=destination,
            commitlog_file=commitlog_file,
            commitlog_position=commitlog_position,
            last_event_timestamp_micros=last_event_timestamp_micros,
            last_committed_at=datetime.now(),
            events_replicated_count=events_replicated_count,
        )

    def update(
        self,
        commitlog_file: str,
        commitlog_position: int,
        last_event_timestamp_micros: int,
        events_count: int = 1,
    ) -> "ReplicationOffset":
        """
        Create updated offset with new position and timestamp

        Args:
            commitlog_file: New commitlog file
            commitlog_position: New position in file
            last_event_timestamp_micros: New event timestamp
            events_count: Number of events in this batch (default 1)

        Returns:
            New ReplicationOffset with updated values
        """
        # Validate monotonicity
        if last_event_timestamp_micros < self.last_event_timestamp_micros:
            raise ValueError("Timestamps must be monotonically increasing")

        return ReplicationOffset(
            offset_id=self.offset_id,  # Keep same ID
            table_name=self.table_name,
            keyspace=self.keyspace,
            partition_id=self.partition_id,
            destination=self.destination,
            commitlog_file=commitlog_file,
            commitlog_position=commitlog_position,
            last_event_timestamp_micros=last_event_timestamp_micros,
            last_committed_at=datetime.now(),
            events_replicated_count=self.events_replicated_count + events_count,
        )

    @property
    def offset_key(self) -> str:
        """Unique key for this offset (table, partition, destination)"""
        return f"{self.keyspace}.{self.table_name}:partition_{self.partition_id}:{self.destination.value}"

    def to_dict(self) -> dict:
        """Convert to dictionary for storage"""
        return {
            "offset_id": str(self.offset_id),
            "table_name": self.table_name,
            "keyspace": self.keyspace,
            "partition_id": self.partition_id,
            "destination": self.destination.value,
            "commitlog_file": self.commitlog_file,
            "commitlog_position": self.commitlog_position,
            "last_event_timestamp_micros": self.last_event_timestamp_micros,
            "last_committed_at": self.last_committed_at.isoformat(),
            "events_replicated_count": self.events_replicated_count,
        }
