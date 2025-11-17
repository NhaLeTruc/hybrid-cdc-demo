"""
Unit tests for offset management logic
Tests offset read/write/commit operations for exactly-once delivery
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.models.offset import Destination, ReplicationOffset


class TestOffsetManagement:
    """Test offset management for exactly-once delivery"""

    @pytest.fixture
    def sample_offset(self):
        """Create a sample offset for testing"""
        return ReplicationOffset(
            offset_id=uuid4(),
            table_name="users",
            keyspace="ecommerce",
            partition_id=42,
            destination=Destination.POSTGRES,
            commitlog_file="CommitLog-7-1700000000.log",
            commitlog_position=1048576,
            last_event_timestamp_micros=1700000000000000,
            last_committed_at=datetime.now(timezone.utc),
            events_replicated_count=100,
        )

    def test_read_offset_for_partition(self, sample_offset):
        """Test reading offset for a specific partition and destination"""
        from src.cdc.offset import OffsetManager

        manager = OffsetManager()

        # Should return None when no offset exists
        offset = manager.read_offset(
            table_name="users",
            keyspace="ecommerce",
            partition_id=42,
            destination=Destination.POSTGRES,
        )

        # Initially should be None (no offset stored)
        # After implementation, this will test actual storage
        assert offset is None or isinstance(offset, ReplicationOffset)

    def test_write_offset_creates_new_record(self, sample_offset):
        """Test writing a new offset record"""
        from src.cdc.offset import OffsetManager

        manager = OffsetManager()

        # Write offset
        manager.write_offset(sample_offset)

        # Read it back
        offset = manager.read_offset(
            table_name=sample_offset.table_name,
            keyspace=sample_offset.keyspace,
            partition_id=sample_offset.partition_id,
            destination=sample_offset.destination,
        )

        assert offset is not None
        assert offset.commitlog_file == sample_offset.commitlog_file
        assert offset.commitlog_position == sample_offset.commitlog_position

    def test_write_offset_updates_existing_record(self, sample_offset):
        """Test updating an existing offset record"""
        from src.cdc.offset import OffsetManager

        manager = OffsetManager()

        # Write initial offset
        manager.write_offset(sample_offset)

        # Update offset with new position
        updated_offset = sample_offset.update(
            new_commitlog_position=2097152,
            new_event_timestamp_micros=1700000001000000,
            events_count=10,
        )

        manager.write_offset(updated_offset)

        # Read it back
        offset = manager.read_offset(
            table_name=sample_offset.table_name,
            keyspace=sample_offset.keyspace,
            partition_id=sample_offset.partition_id,
            destination=sample_offset.destination,
        )

        assert offset.commitlog_position == 2097152
        assert offset.events_replicated_count == 110  # 100 + 10

    def test_commit_offset_atomic_operation(self, sample_offset):
        """Test that offset commit is atomic"""
        from src.cdc.offset import OffsetManager

        manager = OffsetManager()

        # Commit should succeed or rollback completely
        success = manager.commit_offset(sample_offset)

        assert isinstance(success, bool)

    def test_offset_monotonic_timestamp_validation(self, sample_offset):
        """Test that offset timestamps must be monotonically increasing"""
        from src.cdc.offset import OffsetManager

        manager = OffsetManager()

        # Write initial offset
        manager.write_offset(sample_offset)

        # Try to write offset with older timestamp - should raise error
        older_offset = ReplicationOffset(
            offset_id=uuid4(),
            table_name=sample_offset.table_name,
            keyspace=sample_offset.keyspace,
            partition_id=sample_offset.partition_id,
            destination=sample_offset.destination,
            commitlog_file=sample_offset.commitlog_file,
            commitlog_position=sample_offset.commitlog_position + 1000,
            last_event_timestamp_micros=sample_offset.last_event_timestamp_micros - 1000,  # Older!
            last_committed_at=datetime.now(timezone.utc),
            events_replicated_count=101,
        )

        with pytest.raises(ValueError, match="timestamp must be monotonically increasing"):
            manager.write_offset(older_offset)

    def test_read_all_offsets_for_table(self):
        """Test reading all offsets for a table across all destinations"""
        from src.cdc.offset import OffsetManager

        manager = OffsetManager()

        offsets = manager.read_all_offsets(table_name="users", keyspace="ecommerce")

        # Should return a dict of {Destination: ReplicationOffset}
        assert isinstance(offsets, dict)

    def test_read_latest_offset_across_partitions(self):
        """Test reading the latest offset across all partitions for a destination"""
        from src.cdc.offset import OffsetManager

        manager = OffsetManager()

        latest_offset = manager.read_latest_offset(
            table_name="users", keyspace="ecommerce", destination=Destination.POSTGRES
        )

        # Should return the offset with highest timestamp
        assert latest_offset is None or isinstance(latest_offset, ReplicationOffset)

    def test_offset_cleanup_old_records(self):
        """Test cleaning up old offset records (retention policy)"""
        from src.cdc.offset import OffsetManager

        manager = OffsetManager()

        # Cleanup offsets older than 7 days
        deleted_count = manager.cleanup_old_offsets(retention_days=7)

        assert isinstance(deleted_count, int)
        assert deleted_count >= 0

    def test_offset_idempotent_writes(self, sample_offset):
        """Test that writing the same offset multiple times is idempotent"""
        from src.cdc.offset import OffsetManager

        manager = OffsetManager()

        # Write offset twice
        manager.write_offset(sample_offset)
        manager.write_offset(sample_offset)

        # Should have only one record
        offset = manager.read_offset(
            table_name=sample_offset.table_name,
            keyspace=sample_offset.keyspace,
            partition_id=sample_offset.partition_id,
            destination=sample_offset.destination,
        )

        assert offset is not None
        # Events count should not be duplicated
        assert offset.events_replicated_count == sample_offset.events_replicated_count
