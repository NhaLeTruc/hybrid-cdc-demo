"""
Contract tests for ChangeEvent schema validation
Validates that ChangeEvent dataclass matches event-schema.json contract
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from jsonschema import ValidationError, validate

from src.models.event import ChangeEvent, EventType


@pytest.fixture
def event_schema():
    """Load event-schema.json contract"""
    schema_path = (
        Path(__file__).parent.parent.parent
        / "specs"
        / "001-secure-cdc-pipeline"
        / "contracts"
        / "event-schema.json"
    )
    with open(schema_path) as f:
        return json.load(f)


class TestEventSchema:
    """Test that ChangeEvent conforms to event-schema.json"""

    def test_insert_event_matches_schema(self, event_schema):
        """Test that INSERT event conforms to schema"""
        event = ChangeEvent.create(
            event_type=EventType.INSERT,
            table_name="users",
            keyspace="ecommerce",
            partition_key={"user_id": str(uuid4())},
            clustering_key={},
            columns={"email": "test@example.com", "age": 30},
            timestamp_micros=int(datetime.now(timezone.utc).timestamp() * 1_000_000),
        )

        # Convert to dict for schema validation
        event_dict = {
            "event_id": str(event.event_id),
            "event_type": event.event_type.value,
            "table_name": event.table_name,
            "keyspace": event.keyspace,
            "partition_key": event.partition_key,
            "clustering_key": event.clustering_key,
            "columns": event.columns,
            "timestamp_micros": event.timestamp_micros,
            "ttl_seconds": event.ttl_seconds,
            "captured_at": event.captured_at.isoformat(),
        }

        # Should not raise ValidationError
        validate(instance=event_dict, schema=event_schema)

    def test_update_event_matches_schema(self, event_schema):
        """Test that UPDATE event conforms to schema"""
        event = ChangeEvent.create(
            event_type=EventType.UPDATE,
            table_name="users",
            keyspace="ecommerce",
            partition_key={"user_id": str(uuid4())},
            clustering_key={},
            columns={"email": "updated@example.com"},
            timestamp_micros=int(datetime.now(timezone.utc).timestamp() * 1_000_000),
        )

        event_dict = {
            "event_id": str(event.event_id),
            "event_type": event.event_type.value,
            "table_name": event.table_name,
            "keyspace": event.keyspace,
            "partition_key": event.partition_key,
            "clustering_key": event.clustering_key,
            "columns": event.columns,
            "timestamp_micros": event.timestamp_micros,
            "ttl_seconds": event.ttl_seconds,
            "captured_at": event.captured_at.isoformat(),
        }

        validate(instance=event_dict, schema=event_schema)

    def test_delete_event_matches_schema(self, event_schema):
        """Test that DELETE event conforms to schema"""
        event = ChangeEvent.create(
            event_type=EventType.DELETE,
            table_name="users",
            keyspace="ecommerce",
            partition_key={"user_id": str(uuid4())},
            clustering_key={},
            columns={},  # DELETE has empty columns
            timestamp_micros=int(datetime.now(timezone.utc).timestamp() * 1_000_000),
        )

        event_dict = {
            "event_id": str(event.event_id),
            "event_type": event.event_type.value,
            "table_name": event.table_name,
            "keyspace": event.keyspace,
            "partition_key": event.partition_key,
            "clustering_key": event.clustering_key,
            "columns": event.columns,
            "timestamp_micros": event.timestamp_micros,
            "ttl_seconds": event.ttl_seconds,
            "captured_at": event.captured_at.isoformat(),
        }

        validate(instance=event_dict, schema=event_schema)

    def test_event_with_ttl_matches_schema(self, event_schema):
        """Test that event with TTL conforms to schema"""
        event = ChangeEvent.create(
            event_type=EventType.INSERT,
            table_name="sessions",
            keyspace="ecommerce",
            partition_key={"session_id": str(uuid4())},
            clustering_key={},
            columns={"token": "abc123"},
            timestamp_micros=int(datetime.now(timezone.utc).timestamp() * 1_000_000),
            ttl_seconds=3600,  # 1 hour TTL
        )

        event_dict = {
            "event_id": str(event.event_id),
            "event_type": event.event_type.value,
            "table_name": event.table_name,
            "keyspace": event.keyspace,
            "partition_key": event.partition_key,
            "clustering_key": event.clustering_key,
            "columns": event.columns,
            "timestamp_micros": event.timestamp_micros,
            "ttl_seconds": event.ttl_seconds,
            "captured_at": event.captured_at.isoformat(),
        }

        validate(instance=event_dict, schema=event_schema)

    def test_invalid_event_type_fails_validation(self, event_schema):
        """Test that invalid event type fails schema validation"""
        invalid_event_dict = {
            "event_id": str(uuid4()),
            "event_type": "INVALID_TYPE",  # Not INSERT, UPDATE, or DELETE
            "table_name": "users",
            "keyspace": "ecommerce",
            "partition_key": {"user_id": str(uuid4())},
            "clustering_key": {},
            "columns": {"email": "test@example.com"},
            "timestamp_micros": int(datetime.now(timezone.utc).timestamp() * 1_000_000),
            "ttl_seconds": None,
            "captured_at": datetime.now(timezone.utc).isoformat(),
        }

        with pytest.raises(ValidationError):
            validate(instance=invalid_event_dict, schema=event_schema)

    def test_missing_required_field_fails_validation(self, event_schema):
        """Test that missing required field fails validation"""
        incomplete_event_dict = {
            "event_id": str(uuid4()),
            "event_type": "INSERT",
            # Missing table_name, keyspace, partition_key, timestamp_micros, captured_at
        }

        with pytest.raises(ValidationError):
            validate(instance=incomplete_event_dict, schema=event_schema)

    def test_delete_with_columns_fails_validation(self, event_schema):
        """Test that DELETE event with columns fails validation"""
        invalid_delete_dict = {
            "event_id": str(uuid4()),
            "event_type": "DELETE",
            "table_name": "users",
            "keyspace": "ecommerce",
            "partition_key": {"user_id": str(uuid4())},
            "clustering_key": {},
            "columns": {"email": "should_be_empty@example.com"},  # DELETE must have empty columns
            "timestamp_micros": int(datetime.now(timezone.utc).timestamp() * 1_000_000),
            "ttl_seconds": None,
            "captured_at": datetime.now(timezone.utc).isoformat(),
        }

        with pytest.raises(ValidationError):
            validate(instance=invalid_delete_dict, schema=event_schema)

    def test_insert_without_columns_fails_validation(self, event_schema):
        """Test that INSERT event without columns fails validation"""
        invalid_insert_dict = {
            "event_id": str(uuid4()),
            "event_type": "INSERT",
            "table_name": "users",
            "keyspace": "ecommerce",
            "partition_key": {"user_id": str(uuid4())},
            "clustering_key": {},
            "columns": {},  # INSERT must have at least one column
            "timestamp_micros": int(datetime.now(timezone.utc).timestamp() * 1_000_000),
            "ttl_seconds": None,
            "captured_at": datetime.now(timezone.utc).isoformat(),
        }

        with pytest.raises(ValidationError):
            validate(instance=invalid_insert_dict, schema=event_schema)

    def test_invalid_table_name_pattern_fails_validation(self, event_schema):
        """Test that invalid table name pattern fails validation"""
        invalid_event_dict = {
            "event_id": str(uuid4()),
            "event_type": "INSERT",
            "table_name": "InvalidTableName",  # Must be lowercase with underscores
            "keyspace": "ecommerce",
            "partition_key": {"user_id": str(uuid4())},
            "clustering_key": {},
            "columns": {"email": "test@example.com"},
            "timestamp_micros": int(datetime.now(timezone.utc).timestamp() * 1_000_000),
            "ttl_seconds": None,
            "captured_at": datetime.now(timezone.utc).isoformat(),
        }

        with pytest.raises(ValidationError):
            validate(instance=invalid_event_dict, schema=event_schema)

    def test_empty_partition_key_fails_validation(self, event_schema):
        """Test that empty partition key fails validation"""
        invalid_event_dict = {
            "event_id": str(uuid4()),
            "event_type": "INSERT",
            "table_name": "users",
            "keyspace": "ecommerce",
            "partition_key": {},  # Must have at least one key
            "clustering_key": {},
            "columns": {"email": "test@example.com"},
            "timestamp_micros": int(datetime.now(timezone.utc).timestamp() * 1_000_000),
            "ttl_seconds": None,
            "captured_at": datetime.now(timezone.utc).isoformat(),
        }

        with pytest.raises(ValidationError):
            validate(instance=invalid_event_dict, schema=event_schema)
