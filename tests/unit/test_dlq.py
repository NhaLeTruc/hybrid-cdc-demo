"""
Unit tests for Dead Letter Queue (DLQ)
Tests DLQ write logic for failed events
"""

import json
from datetime import datetime, timezone
from uuid import uuid4

from src.models.event import ChangeEvent, EventType


class TestDLQ:
    """Test Dead Letter Queue functionality"""

    def test_write_event_to_dlq(self, tmp_path):
        """Test writing failed event to DLQ"""
        from src.dlq.writer import DLQWriter

        dlq_dir = tmp_path / "dlq"
        writer = DLQWriter(dlq_directory=str(dlq_dir))

        # Create test event
        event = ChangeEvent.create(
            event_type=EventType.INSERT,
            table_name="users",
            keyspace="ecommerce",
            partition_key={"user_id": str(uuid4())},
            clustering_key={},
            columns={"email": "test@example.com"},
            timestamp_micros=int(datetime.now(timezone.utc).timestamp() * 1_000_000),
        )

        # Write to DLQ
        writer.write_event(
            event=event,
            destination="POSTGRES",
            error_type="connection_timeout",
            error_message="Connection to Postgres timed out",
        )

        # Verify file was created
        dlq_files = list(dlq_dir.glob("*.jsonl"))
        assert len(dlq_files) > 0

    def test_dlq_file_format(self, tmp_path):
        """Test that DLQ file is in JSONL format"""
        from src.dlq.writer import DLQWriter

        dlq_dir = tmp_path / "dlq"
        writer = DLQWriter(dlq_directory=str(dlq_dir))

        event = ChangeEvent.create(
            event_type=EventType.INSERT,
            table_name="users",
            keyspace="ecommerce",
            partition_key={"user_id": str(uuid4())},
            clustering_key={},
            columns={"email": "test@example.com"},
            timestamp_micros=int(datetime.now(timezone.utc).timestamp() * 1_000_000),
        )

        writer.write_event(
            event=event,
            destination="POSTGRES",
            error_type="write_error",
            error_message="Write failed",
        )

        # Read DLQ file and verify format
        dlq_file = list(dlq_dir.glob("*.jsonl"))[0]
        with open(dlq_file) as f:
            line = f.readline()
            data = json.loads(line)

        # Should contain event and error info
        assert "event_id" in data
        assert "destination" in data
        assert "error_type" in data
        assert "error_message" in data
        assert "failed_at" in data

    def test_dlq_rotation_by_date(self, tmp_path):
        """Test that DLQ files are rotated by date"""
        from src.dlq.writer import DLQWriter

        dlq_dir = tmp_path / "dlq"
        writer = DLQWriter(dlq_directory=str(dlq_dir))

        event = ChangeEvent.create(
            event_type=EventType.INSERT,
            table_name="users",
            keyspace="ecommerce",
            partition_key={"user_id": str(uuid4())},
            clustering_key={},
            columns={"email": "test@example.com"},
            timestamp_micros=int(datetime.now(timezone.utc).timestamp() * 1_000_000),
        )

        writer.write_event(
            event=event,
            destination="POSTGRES",
            error_type="error",
            error_message="Test",
        )

        # File name should contain date
        dlq_files = list(dlq_dir.glob("*.jsonl"))
        assert len(dlq_files) == 1

        filename = dlq_files[0].name
        # Should be like: dlq_POSTGRES_2025-11-17.jsonl
        assert "dlq_" in filename
        assert "POSTGRES" in filename
        assert ".jsonl" in filename

    def test_dlq_append_mode(self, tmp_path):
        """Test that DLQ appends to existing file"""
        from src.dlq.writer import DLQWriter

        dlq_dir = tmp_path / "dlq"
        writer = DLQWriter(dlq_directory=str(dlq_dir))

        # Write two events
        for i in range(2):
            event = ChangeEvent.create(
                event_type=EventType.INSERT,
                table_name="users",
                keyspace="ecommerce",
                partition_key={"user_id": str(uuid4())},
                clustering_key={},
                columns={"email": f"test{i}@example.com"},
                timestamp_micros=int(datetime.now(timezone.utc).timestamp() * 1_000_000),
            )

            writer.write_event(
                event=event,
                destination="POSTGRES",
                error_type="error",
                error_message="Test",
            )

        # Should still be one file
        dlq_files = list(dlq_dir.glob("*.jsonl"))
        assert len(dlq_files) == 1

        # But with two lines
        with open(dlq_files[0]) as f:
            lines = f.readlines()
        assert len(lines) == 2

    def test_dlq_creates_directory(self, tmp_path):
        """Test that DLQ creates directory if missing"""
        from src.dlq.writer import DLQWriter

        dlq_dir = tmp_path / "missing" / "dlq"
        writer = DLQWriter(dlq_directory=str(dlq_dir))

        event = ChangeEvent.create(
            event_type=EventType.INSERT,
            table_name="users",
            keyspace="ecommerce",
            partition_key={"user_id": str(uuid4())},
            clustering_key={},
            columns={"email": "test@example.com"},
            timestamp_micros=int(datetime.now(timezone.utc).timestamp() * 1_000_000),
        )

        writer.write_event(
            event=event,
            destination="POSTGRES",
            error_type="error",
            error_message="Test",
        )

        # Directory should be created
        assert dlq_dir.exists()

    def test_dlq_includes_full_event_details(self, tmp_path):
        """Test that DLQ includes all event details for debugging"""
        from src.dlq.writer import DLQWriter

        dlq_dir = tmp_path / "dlq"
        writer = DLQWriter(dlq_directory=str(dlq_dir))

        event = ChangeEvent.create(
            event_type=EventType.UPDATE,
            table_name="orders",
            keyspace="ecommerce",
            partition_key={"order_id": str(uuid4())},
            clustering_key={"created_at": "2025-11-17"},
            columns={"status": "shipped", "total": 99.99},
            timestamp_micros=int(datetime.now(timezone.utc).timestamp() * 1_000_000),
        )

        writer.write_event(
            event=event,
            destination="CLICKHOUSE",
            error_type="parse_error",
            error_message="Failed to parse complex type",
        )

        # Read and verify all details are present
        dlq_file = list(dlq_dir.glob("*.jsonl"))[0]
        with open(dlq_file) as f:
            data = json.loads(f.readline())

        assert data["event_type"] == "UPDATE"
        assert data["table_name"] == "orders"
        assert "partition_key" in data
        assert "clustering_key" in data
        assert "columns" in data
        assert data["error_type"] == "parse_error"
