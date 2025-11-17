"""
Offset Management for Exactly-Once Delivery
Manages replication offsets per partition and destination
"""

from datetime import datetime, timezone
from typing import Optional, Dict
from uuid import uuid4
import structlog

from src.models.offset import ReplicationOffset, Destination

logger = structlog.get_logger(__name__)


class OffsetManager:
    """
    Manages replication offsets for exactly-once delivery

    Offsets are stored in each destination's offset table to ensure
    atomic commits with data writes.
    """

    def __init__(self):
        """Initialize offset manager"""
        self._in_memory_offsets: Dict[tuple, ReplicationOffset] = {}
        logger.info("OffsetManager initialized")

    def read_offset(
        self,
        table_name: str,
        keyspace: str,
        partition_id: int,
        destination: Destination,
    ) -> Optional[ReplicationOffset]:
        """
        Read the last committed offset for a partition and destination

        Args:
            table_name: Table name
            keyspace: Keyspace name
            partition_id: Partition identifier
            destination: Target destination

        Returns:
            Last committed offset, or None if no offset exists
        """
        key = (table_name, keyspace, partition_id, destination)

        # Check in-memory cache first
        if key in self._in_memory_offsets:
            logger.debug("Offset found in memory", key=key)
            return self._in_memory_offsets[key]

        # In production, this would query the offset table in the destination database
        # For now, return None (no offset stored)
        logger.debug("No offset found", table=table_name, partition=partition_id, dest=destination.value)
        return None

    def write_offset(self, offset: ReplicationOffset) -> None:
        """
        Write offset to storage

        Args:
            offset: Offset to write

        Raises:
            ValueError: If offset timestamp is not monotonically increasing
        """
        key = (offset.table_name, offset.keyspace, offset.partition_id, offset.destination)

        # Check for monotonicity
        existing_offset = self._in_memory_offsets.get(key)
        if existing_offset:
            if offset.last_event_timestamp_micros < existing_offset.last_event_timestamp_micros:
                raise ValueError(
                    f"Offset timestamp must be monotonically increasing. "
                    f"Got {offset.last_event_timestamp_micros}, "
                    f"existing {existing_offset.last_event_timestamp_micros}"
                )

        # Store in memory
        self._in_memory_offsets[key] = offset

        logger.info(
            "Offset written",
            table=offset.table_name,
            partition=offset.partition_id,
            destination=offset.destination.value,
            position=offset.commitlog_position,
            events_count=offset.events_replicated_count,
        )

    def commit_offset(self, offset: ReplicationOffset) -> bool:
        """
        Atomically commit offset to destination database

        This should be called within the same transaction as data writes
        to ensure exactly-once delivery.

        Args:
            offset: Offset to commit

        Returns:
            True if commit succeeded, False otherwise
        """
        try:
            # Write to storage
            self.write_offset(offset)

            # In production, this would execute:
            # INSERT INTO cdc_offsets (...) VALUES (...)
            # ON CONFLICT (table_name, keyspace, partition_id, destination)
            # DO UPDATE SET ...
            # within the same transaction as the data writes

            logger.info("Offset committed", offset_id=str(offset.offset_id))
            return True

        except Exception as e:
            logger.error("Failed to commit offset", error=str(e))
            return False

    def read_all_offsets(
        self,
        table_name: str,
        keyspace: str,
    ) -> Dict[Destination, ReplicationOffset]:
        """
        Read all offsets for a table across all destinations

        Args:
            table_name: Table name
            keyspace: Keyspace name

        Returns:
            Dict mapping Destination to latest offset
        """
        offsets: Dict[Destination, ReplicationOffset] = {}

        for key, offset in self._in_memory_offsets.items():
            tbl, ks, partition, dest = key
            if tbl == table_name and ks == keyspace:
                # Keep the latest offset for each destination
                if dest not in offsets or offset.last_event_timestamp_micros > offsets[dest].last_event_timestamp_micros:
                    offsets[dest] = offset

        logger.debug("Read all offsets", table=table_name, count=len(offsets))
        return offsets

    def read_latest_offset(
        self,
        table_name: str,
        keyspace: str,
        destination: Destination,
    ) -> Optional[ReplicationOffset]:
        """
        Read the latest offset across all partitions for a destination

        Args:
            table_name: Table name
            keyspace: Keyspace name
            destination: Target destination

        Returns:
            Latest offset, or None if no offsets exist
        """
        latest_offset: Optional[ReplicationOffset] = None

        for key, offset in self._in_memory_offsets.items():
            tbl, ks, partition, dest = key
            if tbl == table_name and ks == keyspace and dest == destination:
                if latest_offset is None or offset.last_event_timestamp_micros > latest_offset.last_event_timestamp_micros:
                    latest_offset = offset

        if latest_offset:
            logger.debug(
                "Latest offset found",
                table=table_name,
                destination=destination.value,
                timestamp=latest_offset.last_event_timestamp_micros,
            )
        else:
            logger.debug("No offsets found", table=table_name, destination=destination.value)

        return latest_offset

    def cleanup_old_offsets(self, retention_days: int = 7) -> int:
        """
        Clean up old offset records

        Args:
            retention_days: Keep offsets newer than this many days

        Returns:
            Number of offsets deleted
        """
        cutoff_time = datetime.now(timezone.utc).timestamp() - (retention_days * 24 * 60 * 60)
        deleted_count = 0

        # Find offsets older than cutoff
        keys_to_delete = []
        for key, offset in self._in_memory_offsets.items():
            if offset.last_committed_at.timestamp() < cutoff_time:
                keys_to_delete.append(key)

        # Delete old offsets
        for key in keys_to_delete:
            del self._in_memory_offsets[key]
            deleted_count += 1

        logger.info("Cleaned up old offsets", deleted_count=deleted_count, retention_days=retention_days)
        return deleted_count

    def create_offset(
        self,
        table_name: str,
        keyspace: str,
        partition_id: int,
        destination: Destination,
        commitlog_file: str,
        commitlog_position: int,
        event_timestamp_micros: int,
        events_count: int = 1,
    ) -> ReplicationOffset:
        """
        Create a new offset record

        Args:
            table_name: Table name
            keyspace: Keyspace name
            partition_id: Partition identifier
            destination: Target destination
            commitlog_file: Commitlog file name
            commitlog_position: Position in commitlog file
            event_timestamp_micros: Timestamp of last event
            events_count: Number of events processed

        Returns:
            New ReplicationOffset
        """
        offset = ReplicationOffset(
            offset_id=uuid4(),
            table_name=table_name,
            keyspace=keyspace,
            partition_id=partition_id,
            destination=destination,
            commitlog_file=commitlog_file,
            commitlog_position=commitlog_position,
            last_event_timestamp_micros=event_timestamp_micros,
            last_committed_at=datetime.now(timezone.utc),
            events_replicated_count=events_count,
        )

        logger.debug("Created new offset", offset_id=str(offset.offset_id))
        return offset
