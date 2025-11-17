"""
Dead Letter Event Model
Represents an event that failed after max retries
"""

from dataclasses import dataclass
from typing import Dict, Any, Optional
from uuid import UUID


@dataclass
class DeadLetterEvent:
    """
    Event that failed and was routed to DLQ

    Contains original event data plus error information for debugging
    and potential replay.

    Attributes:
        event_id: Original event ID
        event_type: Event type (INSERT, UPDATE, DELETE)
        table_name: Source table
        keyspace: Source keyspace
        partition_key: Partition key
        clustering_key: Clustering key
        columns: Column data
        timestamp_micros: Original event timestamp
        captured_at: When event was captured from CDC
        ttl_seconds: TTL if set
        destination: Which destination failed
        error_type: Type of error
        error_message: Error details
        failed_at: When event failed and was sent to DLQ
    """

    event_id: UUID
    event_type: str
    table_name: str
    keyspace: str
    partition_key: Dict[str, Any]
    clustering_key: Dict[str, Any]
    columns: Dict[str, Any]
    timestamp_micros: int
    captured_at: str
    ttl_seconds: Optional[int]
    destination: str
    error_type: str
    error_message: str
    failed_at: str

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary for JSON serialization

        Returns:
            Dict representation
        """
        return {
            "event_id": str(self.event_id),
            "event_type": self.event_type,
            "table_name": self.table_name,
            "keyspace": self.keyspace,
            "partition_key": self.partition_key,
            "clustering_key": self.clustering_key,
            "columns": self.columns,
            "timestamp_micros": self.timestamp_micros,
            "captured_at": self.captured_at,
            "ttl_seconds": self.ttl_seconds,
            "destination": self.destination,
            "error_type": self.error_type,
            "error_message": self.error_message,
            "failed_at": self.failed_at,
        }
