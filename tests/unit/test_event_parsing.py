"""
Unit tests for CDC event parsing logic
Tests the parser module that converts commitlog binary format into ChangeEvent objects
"""

from datetime import datetime, timezone

import pytest

from src.models.event import ChangeEvent, EventType


class TestEventParsing:
    """Test parsing of CDC events from commitlog format"""

    def test_parse_insert_event(self):
        """Test parsing INSERT event from binary commitlog entry"""
        # This test will fail until parser.py is implemented
        from src.cdc.parser import parse_commitlog_entry

        # Sample commitlog entry (binary format simplified for test)
        commitlog_entry = b"INSERT users ..."  # Placeholder

        event = parse_commitlog_entry(commitlog_entry)

        assert isinstance(event, ChangeEvent)
        assert event.event_type == EventType.INSERT
        assert event.table_name == "users"
        assert event.keyspace is not None
        assert len(event.partition_key) > 0
        assert len(event.columns) > 0

    def test_parse_update_event(self):
        """Test parsing UPDATE event from binary commitlog entry"""
        from src.cdc.parser import parse_commitlog_entry

        commitlog_entry = b"UPDATE users ..."  # Placeholder

        event = parse_commitlog_entry(commitlog_entry)

        assert event.event_type == EventType.UPDATE
        assert len(event.columns) > 0

    def test_parse_delete_event(self):
        """Test parsing DELETE event from binary commitlog entry"""
        from src.cdc.parser import parse_commitlog_entry

        commitlog_entry = b"DELETE users ..."  # Placeholder

        event = parse_commitlog_entry(commitlog_entry)

        assert event.event_type == EventType.DELETE
        # DELETE events should have empty columns
        assert len(event.columns) == 0

    def test_parse_event_with_ttl(self):
        """Test parsing event with TTL set"""
        from src.cdc.parser import parse_commitlog_entry

        commitlog_entry = b"INSERT sessions WITH TTL ..."  # Placeholder

        event = parse_commitlog_entry(commitlog_entry)

        assert event.ttl_seconds is not None
        assert event.ttl_seconds > 0

    def test_parse_event_without_clustering_key(self):
        """Test parsing event from table with only partition key"""
        from src.cdc.parser import parse_commitlog_entry

        commitlog_entry = b"INSERT simple_table ..."  # Placeholder

        event = parse_commitlog_entry(commitlog_entry)

        assert len(event.partition_key) > 0
        assert event.clustering_key == {}

    def test_parse_event_with_clustering_key(self):
        """Test parsing event from table with clustering key"""
        from src.cdc.parser import parse_commitlog_entry

        commitlog_entry = b"INSERT time_series ..."  # Placeholder

        event = parse_commitlog_entry(commitlog_entry)

        assert len(event.partition_key) > 0
        assert len(event.clustering_key) > 0

    def test_parse_event_validates_timestamp(self):
        """Test that parsed event has valid timestamp"""
        from src.cdc.parser import parse_commitlog_entry

        commitlog_entry = b"INSERT users ..."  # Placeholder

        event = parse_commitlog_entry(commitlog_entry)

        # Timestamp should be reasonable (not in future, not too old)
        now_micros = int(datetime.now(timezone.utc).timestamp() * 1_000_000)
        one_year_ago_micros = now_micros - (365 * 24 * 60 * 60 * 1_000_000)

        assert event.timestamp_micros >= one_year_ago_micros
        assert event.timestamp_micros <= now_micros + 60_000_000  # Allow 60s clock skew

    def test_parse_event_generates_unique_id(self):
        """Test that each parsed event gets unique event_id"""
        from src.cdc.parser import parse_commitlog_entry

        commitlog_entry1 = b"INSERT users ..."
        commitlog_entry2 = b"INSERT users ..."

        event1 = parse_commitlog_entry(commitlog_entry1)
        event2 = parse_commitlog_entry(commitlog_entry2)

        assert event1.event_id != event2.event_id

    def test_parse_invalid_commitlog_entry_raises_error(self):
        """Test that invalid commitlog entry raises ParseError"""
        from src.cdc.parser import ParseError, parse_commitlog_entry

        invalid_entry = b"GARBAGE DATA"

        with pytest.raises(ParseError):
            parse_commitlog_entry(invalid_entry)

    def test_parse_event_sets_captured_at(self):
        """Test that parsed event has captured_at timestamp"""
        from src.cdc.parser import parse_commitlog_entry

        commitlog_entry = b"INSERT users ..."
        before = datetime.now(timezone.utc)

        event = parse_commitlog_entry(commitlog_entry)

        after = datetime.now(timezone.utc)

        # captured_at should be between before and after
        assert before <= event.captured_at <= after
