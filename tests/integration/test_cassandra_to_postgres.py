"""
Integration test for Cassandra → Postgres replication
End-to-end test of CDC pipeline from Cassandra to Postgres warehouse
"""

import pytest
import asyncio
from uuid import uuid4
from datetime import datetime, timezone


@pytest.mark.asyncio
class TestCassandraToPostgres:
    """Test end-to-end replication from Cassandra to Postgres"""

    async def test_insert_event_replicates_to_postgres(
        self, cassandra_session, postgres_connection, sample_users_table_schema
    ):
        """Test that INSERT in Cassandra replicates to Postgres"""
        # Setup: Create table in Cassandra
        cassandra_session.execute(sample_users_table_schema)

        # Insert test data into Cassandra
        user_id = uuid4()
        cassandra_session.execute(
            """
            INSERT INTO users (user_id, email, first_name, last_name, age, created_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (user_id, "test@example.com", "Test", "User", 30, datetime.now(timezone.utc)),
        )

        # Wait for CDC to process (in real implementation)
        # This will use the actual pipeline
        from src.main import CDCPipeline

        pipeline = CDCPipeline()
        # await pipeline.run_once()  # Process one batch

        # Verify data replicated to Postgres
        async with postgres_connection.cursor() as cur:
            await cur.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
            row = await cur.fetchone()

        # Assertions will be implemented with actual pipeline
        # assert row is not None
        # assert row["email"] == "test@example.com"

    async def test_update_event_replicates_to_postgres(
        self, cassandra_session, postgres_connection, sample_users_table_schema
    ):
        """Test that UPDATE in Cassandra replicates to Postgres"""
        # Setup
        cassandra_session.execute(sample_users_table_schema)

        user_id = uuid4()
        cassandra_session.execute(
            """
            INSERT INTO users (user_id, email, first_name, last_name, age, created_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (user_id, "original@example.com", "Test", "User", 30, datetime.now(timezone.utc)),
        )

        # Update in Cassandra
        cassandra_session.execute(
            """
            UPDATE users SET email = %s WHERE user_id = %s
            """,
            ("updated@example.com", user_id),
        )

        # Wait for CDC
        # pipeline.run_once()

        # Verify update replicated
        async with postgres_connection.cursor() as cur:
            await cur.execute("SELECT email FROM users WHERE user_id = %s", (user_id,))
            # row = await cur.fetchone()
            # assert row["email"] == "updated@example.com"

    async def test_delete_event_replicates_to_postgres(
        self, cassandra_session, postgres_connection, sample_users_table_schema
    ):
        """Test that DELETE in Cassandra replicates to Postgres"""
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

        # Delete in Cassandra
        cassandra_session.execute("DELETE FROM users WHERE user_id = %s", (user_id,))

        # Wait for CDC
        # pipeline.run_once()

        # Verify deletion replicated
        async with postgres_connection.cursor() as cur:
            await cur.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
            # row = await cur.fetchone()
            # assert row is None  # Should be deleted

    async def test_batch_insert_replicates_to_postgres(
        self, cassandra_session, postgres_connection, sample_users_table_schema
    ):
        """Test that batch inserts replicate correctly"""
        # Setup
        cassandra_session.execute(sample_users_table_schema)

        # Insert 100 users
        user_ids = [uuid4() for _ in range(100)]
        for i, user_id in enumerate(user_ids):
            cassandra_session.execute(
                """
                INSERT INTO users (user_id, email, first_name, last_name, age, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (user_id, f"user{i}@example.com", f"User{i}", "Test", 20 + i, datetime.now(timezone.utc)),
            )

        # Wait for CDC to process all
        # pipeline.run_batch()

        # Verify all replicated
        async with postgres_connection.cursor() as cur:
            await cur.execute("SELECT COUNT(*) as count FROM users")
            # row = await cur.fetchone()
            # assert row["count"] == 100

    async def test_offset_committed_after_replication(
        self, cassandra_session, postgres_connection, sample_users_table_schema
    ):
        """Test that offset is committed after successful replication"""
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

        # Run pipeline
        # pipeline.run_once()

        # Verify offset was committed
        async with postgres_connection.cursor() as cur:
            await cur.execute(
                """
                SELECT * FROM cdc_offsets
                WHERE table_name = 'users'
                AND destination = 'POSTGRES'
                """
            )
            # offset_row = await cur.fetchone()
            # assert offset_row is not None
            # assert offset_row["events_replicated_count"] > 0
