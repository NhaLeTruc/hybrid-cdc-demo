"""
Contract tests for ReplicationOffset schema validation
Validates that ReplicationOffset dataclass matches offset-schema.json contract
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from jsonschema import ValidationError, validate

from src.models.offset import Destination, ReplicationOffset


@pytest.fixture
def offset_schema():
    """Load offset-schema.json contract"""
    schema_path = (
        Path(__file__).parent.parent.parent
        / "specs"
        / "001-secure-cdc-pipeline"
        / "contracts"
        / "offset-schema.json"
    )
    with open(schema_path) as f:
        return json.load(f)


class TestOffsetSchema:
    """Test that ReplicationOffset conforms to offset-schema.json"""

    def test_postgres_offset_matches_schema(self, offset_schema):
        """Test that Postgres offset conforms to schema"""
        offset = ReplicationOffset(
            offset_id=uuid4(),
            table_name="users",
            keyspace="ecommerce",
            partition_id=42,
            destination=Destination.POSTGRES,
            commitlog_file="CommitLog-7-1700000000.log",
            commitlog_position=1048576,
            last_event_timestamp_micros=1700000000000000,
            last_committed_at=datetime.now(timezone.utc),
            events_replicated_count=1000,
        )

        offset_dict = {
            "offset_id": str(offset.offset_id),
            "table_name": offset.table_name,
            "keyspace": offset.keyspace,
            "partition_id": offset.partition_id,
            "destination": offset.destination.value,
            "commitlog_file": offset.commitlog_file,
            "commitlog_position": offset.commitlog_position,
            "last_event_timestamp_micros": offset.last_event_timestamp_micros,
            "last_committed_at": offset.last_committed_at.isoformat(),
            "events_replicated_count": offset.events_replicated_count,
        }

        # Should not raise ValidationError
        validate(instance=offset_dict, schema=offset_schema)

    def test_clickhouse_offset_matches_schema(self, offset_schema):
        """Test that ClickHouse offset conforms to schema"""
        offset = ReplicationOffset(
            offset_id=uuid4(),
            table_name="orders",
            keyspace="ecommerce",
            partition_id=100,
            destination=Destination.CLICKHOUSE,
            commitlog_file="CommitLog-7-1700000000.log",
            commitlog_position=2097152,
            last_event_timestamp_micros=1700000001000000,
            last_committed_at=datetime.now(timezone.utc),
            events_replicated_count=5000,
        )

        offset_dict = {
            "offset_id": str(offset.offset_id),
            "table_name": offset.table_name,
            "keyspace": offset.keyspace,
            "partition_id": offset.partition_id,
            "destination": offset.destination.value,
            "commitlog_file": offset.commitlog_file,
            "commitlog_position": offset.commitlog_position,
            "last_event_timestamp_micros": offset.last_event_timestamp_micros,
            "last_committed_at": offset.last_committed_at.isoformat(),
            "events_replicated_count": offset.events_replicated_count,
        }

        validate(instance=offset_dict, schema=offset_schema)

    def test_timescaledb_offset_matches_schema(self, offset_schema):
        """Test that TimescaleDB offset conforms to schema"""
        offset = ReplicationOffset(
            offset_id=uuid4(),
            table_name="metrics",
            keyspace="monitoring",
            partition_id=-1000,  # Negative partition IDs are valid
            destination=Destination.TIMESCALEDB,
            commitlog_file="CommitLog-7-1700000000.log",
            commitlog_position=4194304,
            last_event_timestamp_micros=1700000002000000,
            last_committed_at=datetime.now(timezone.utc),
            events_replicated_count=10000,
        )

        offset_dict = {
            "offset_id": str(offset.offset_id),
            "table_name": offset.table_name,
            "keyspace": offset.keyspace,
            "partition_id": offset.partition_id,
            "destination": offset.destination.value,
            "commitlog_file": offset.commitlog_file,
            "commitlog_position": offset.commitlog_position,
            "last_event_timestamp_micros": offset.last_event_timestamp_micros,
            "last_committed_at": offset.last_committed_at.isoformat(),
            "events_replicated_count": offset.events_replicated_count,
        }

        validate(instance=offset_dict, schema=offset_schema)

    def test_invalid_destination_fails_validation(self, offset_schema):
        """Test that invalid destination fails schema validation"""
        invalid_offset_dict = {
            "offset_id": str(uuid4()),
            "table_name": "users",
            "keyspace": "ecommerce",
            "partition_id": 42,
            "destination": "INVALID_DEST",  # Not POSTGRES, CLICKHOUSE, or TIMESCALEDB
            "commitlog_file": "CommitLog-7-1700000000.log",
            "commitlog_position": 1048576,
            "last_event_timestamp_micros": 1700000000000000,
            "last_committed_at": datetime.now(timezone.utc).isoformat(),
            "events_replicated_count": 1000,
        }

        with pytest.raises(ValidationError):
            validate(instance=invalid_offset_dict, schema=offset_schema)

    def test_invalid_commitlog_file_pattern_fails_validation(self, offset_schema):
        """Test that invalid commitlog file pattern fails validation"""
        invalid_offset_dict = {
            "offset_id": str(uuid4()),
            "table_name": "users",
            "keyspace": "ecommerce",
            "partition_id": 42,
            "destination": "POSTGRES",
            "commitlog_file": "invalid_file.log",  # Must match CommitLog-*-*.log pattern
            "commitlog_position": 1048576,
            "last_event_timestamp_micros": 1700000000000000,
            "last_committed_at": datetime.now(timezone.utc).isoformat(),
            "events_replicated_count": 1000,
        }

        with pytest.raises(ValidationError):
            validate(instance=invalid_offset_dict, schema=offset_schema)

    def test_missing_required_field_fails_validation(self, offset_schema):
        """Test that missing required field fails validation"""
        incomplete_offset_dict = {
            "offset_id": str(uuid4()),
            "table_name": "users",
            # Missing keyspace, partition_id, destination, commitlog_file, etc.
        }

        with pytest.raises(ValidationError):
            validate(instance=incomplete_offset_dict, schema=offset_schema)

    def test_negative_commitlog_position_fails_validation(self, offset_schema):
        """Test that negative commitlog position fails validation"""
        invalid_offset_dict = {
            "offset_id": str(uuid4()),
            "table_name": "users",
            "keyspace": "ecommerce",
            "partition_id": 42,
            "destination": "POSTGRES",
            "commitlog_file": "CommitLog-7-1700000000.log",
            "commitlog_position": -100,  # Must be >= 0
            "last_event_timestamp_micros": 1700000000000000,
            "last_committed_at": datetime.now(timezone.utc).isoformat(),
            "events_replicated_count": 1000,
        }

        with pytest.raises(ValidationError):
            validate(instance=invalid_offset_dict, schema=offset_schema)

    def test_negative_events_count_fails_validation(self, offset_schema):
        """Test that negative events count fails validation"""
        invalid_offset_dict = {
            "offset_id": str(uuid4()),
            "table_name": "users",
            "keyspace": "ecommerce",
            "partition_id": 42,
            "destination": "POSTGRES",
            "commitlog_file": "CommitLog-7-1700000000.log",
            "commitlog_position": 1048576,
            "last_event_timestamp_micros": 1700000000000000,
            "last_committed_at": datetime.now(timezone.utc).isoformat(),
            "events_replicated_count": -10,  # Must be >= 0
        }

        with pytest.raises(ValidationError):
            validate(instance=invalid_offset_dict, schema=offset_schema)

    def test_zero_values_are_valid(self, offset_schema):
        """Test that zero values for counts and positions are valid"""
        offset_dict = {
            "offset_id": str(uuid4()),
            "table_name": "users",
            "keyspace": "ecommerce",
            "partition_id": 0,
            "destination": "POSTGRES",
            "commitlog_file": "CommitLog-7-1700000000.log",
            "commitlog_position": 0,  # Start of file
            "last_event_timestamp_micros": 0,  # Epoch
            "last_committed_at": datetime.now(timezone.utc).isoformat(),
            "events_replicated_count": 0,  # No events yet
        }

        # Should not raise ValidationError
        validate(instance=offset_dict, schema=offset_schema)

    def test_large_partition_id_is_valid(self, offset_schema):
        """Test that very large partition IDs (int64) are valid"""
        offset_dict = {
            "offset_id": str(uuid4()),
            "table_name": "users",
            "keyspace": "ecommerce",
            "partition_id": 9223372036854775807,  # Max int64
            "destination": "POSTGRES",
            "commitlog_file": "CommitLog-7-1700000000.log",
            "commitlog_position": 1048576,
            "last_event_timestamp_micros": 1700000000000000,
            "last_committed_at": datetime.now(timezone.utc).isoformat(),
            "events_replicated_count": 1000,
        }

        validate(instance=offset_dict, schema=offset_schema)

    def test_negative_partition_id_is_valid(self, offset_schema):
        """Test that negative partition IDs are valid"""
        offset_dict = {
            "offset_id": str(uuid4()),
            "table_name": "users",
            "keyspace": "ecommerce",
            "partition_id": -9223372036854775808,  # Min int64
            "destination": "POSTGRES",
            "commitlog_file": "CommitLog-7-1700000000.log",
            "commitlog_position": 1048576,
            "last_event_timestamp_micros": 1700000000000000,
            "last_committed_at": datetime.now(timezone.utc).isoformat(),
            "events_replicated_count": 1000,
        }

        validate(instance=offset_dict, schema=offset_schema)
