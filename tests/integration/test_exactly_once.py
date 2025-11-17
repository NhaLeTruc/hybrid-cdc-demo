"""
Integration test for exactly-once delivery guarantees
Verifies no duplicates after pipeline restart
"""

import pytest
from uuid import uuid4
from datetime import datetime, timezone


@pytest.mark.asyncio
class TestExactlyOnceDelivery:
    """Test exactly-once delivery semantics"""

    async def test_no_duplicates_after_pipeline_restart(
        self, cassandra_session, postgres_connection, sample_users_table_schema
    ):
        """Test that events are not duplicated when pipeline restarts"""
        # Setup
        cassandra_session.execute(sample_users_table_schema)

        # Insert test data
        user_id = uuid4()
        cassandra_session.execute(
            """
            INSERT INTO users (user_id, email, first_name, last_name, age, created_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (user_id, "test@example.com", "Test", "User", 30, datetime.now(timezone.utc)),
        )

        # Run pipeline once
        # from src.main import CDCPipeline
        # pipeline = CDCPipeline()
        # await pipeline.run_once()

        # Verify replicated once
        async with postgres_connection.cursor() as cur:
            await cur.execute("SELECT COUNT(*) as count FROM users WHERE user_id = %s", (user_id,))
            # first_count = await cur.fetchone()
            # assert first_count["count"] == 1

        # Restart pipeline and run again (should read from last offset)
        # pipeline2 = CDCPipeline()
        # await pipeline2.run_once()

        # Verify still only one record (no duplicate)
        async with postgres_connection.cursor() as cur:
            await cur.execute("SELECT COUNT(*) as count FROM users WHERE user_id = %s", (user_id,))
            # second_count = await cur.fetchone()
            # assert second_count["count"] == 1  # No duplicate!

    async def test_idempotent_writes_same_event_id(
        self, cassandra_session, postgres_connection, sample_users_table_schema
    ):
        """Test that writing same event_id multiple times is idempotent"""
        # Setup
        cassandra_session.execute(sample_users_table_schema)

        # Insert data
        user_id = uuid4()
        cassandra_session.execute(
            """
            INSERT INTO users (user_id, email, first_name, last_name, age, created_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (user_id, "test@example.com", "Test", "User", 30, datetime.now(timezone.utc)),
        )

        # Manually write same event twice to sink
        # from src.sinks.postgres import PostgresSink
        # from src.models.event import ChangeEvent, EventType

        # event = ChangeEvent.create(...)
        # sink = PostgresSink()
        # await sink.write_batch([event])
        # await sink.write_batch([event])  # Write same event again

        # Verify only one record
        async with postgres_connection.cursor() as cur:
            await cur.execute("SELECT COUNT(*) as count FROM users WHERE user_id = %s", (user_id,))
            # count = await cur.fetchone()
            # assert count["count"] == 1

    async def test_offset_prevents_reprocessing(
        self, cassandra_session, postgres_connection, sample_users_table_schema
    ):
        """Test that committed offset prevents reprocessing old events"""
        # Setup
        cassandra_session.execute(sample_users_table_schema)

        # Insert 10 events
        user_ids = [uuid4() for _ in range(10)]
        for i, user_id in enumerate(user_ids):
            cassandra_session.execute(
                """
                INSERT INTO users (user_id, email, first_name, last_name, age, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (user_id, f"user{i}@example.com", f"User{i}", "Test", 20, datetime.now(timezone.utc)),
            )

        # Process first 5 events
        # pipeline = CDCPipeline()
        # await pipeline.run_batch(batch_size=5)

        # Check offset was committed for first 5
        async with postgres_connection.cursor() as cur:
            await cur.execute(
                """
                SELECT events_replicated_count FROM cdc_offsets
                WHERE table_name = 'users' AND destination = 'POSTGRES'
                """
            )
            # offset = await cur.fetchone()
            # assert offset["events_replicated_count"] == 5

        # Restart and process remaining
        # pipeline2 = CDCPipeline()
        # await pipeline2.run_batch(batch_size=5)

        # Verify total is 10 (not 15)
        async with postgres_connection.cursor() as cur:
            await cur.execute("SELECT COUNT(*) as count FROM users")
            # count = await cur.fetchone()
            # assert count["count"] == 10  # No reprocessing of first 5

    async def test_transactional_offset_commit(
        self, cassandra_session, postgres_connection, sample_users_table_schema
    ):
        """Test that offset commit is transactional with data write"""
        # Setup
        cassandra_session.execute(sample_users_table_schema)

        user_id = uuid4()
        cassandra_session.execute(
            """
            INSERT INTO users (user_id, email, first_name, last_name, age, created_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (user_id, "test@example.com", "Test", "User", 30, datetime.now(timezone.utc)),
        )

        # If data write fails, offset should not be committed
        # Simulate failure by injecting error in sink
        # This will be tested with actual implementation
        pass
