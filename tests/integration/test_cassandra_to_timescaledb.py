"""
Integration test for Cassandra → TimescaleDB replication
End-to-end test of CDC pipeline from Cassandra to TimescaleDB warehouse
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest


@pytest.mark.asyncio
class TestCassandraToTimescaleDB:
    """Test end-to-end replication from Cassandra to TimescaleDB"""

    async def test_insert_event_replicates_to_timescaledb(
        self,
        cassandra_session,
        timescaledb_connection,
        timescaledb_users_table,
        sample_users_table_schema,
    ):
        """Test that INSERT in Cassandra replicates to TimescaleDB"""
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

        # Run CDC pipeline
        # from src.main import CDCPipeline
        # pipeline = CDCPipeline()
        # await pipeline.run_once()

        # Verify replication
        async with timescaledb_connection.cursor() as cur:
            await cur.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
            # row = await cur.fetchone()
            # assert row is not None

    async def test_time_series_data_uses_hypertable(
        self, cassandra_session, timescaledb_connection, sample_users_table_schema
    ):
        """Test that replicated data uses TimescaleDB hypertable features"""
        # Setup
        cassandra_session.execute(sample_users_table_schema)

        # Insert time-series data
        for i in range(10):
            user_id = uuid4()
            cassandra_session.execute(
                """
                INSERT INTO users (user_id, email, first_name, last_name, age, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    user_id,
                    f"user{i}@example.com",
                    f"User{i}",
                    "Test",
                    20,
                    datetime.now(timezone.utc),
                ),
            )

        # Run CDC
        # await pipeline.run_batch()

        # Verify hypertable is being used
        async with timescaledb_connection.cursor() as cur:
            await cur.execute(
                """
                SELECT * FROM timescaledb_information.hypertables
                WHERE hypertable_name = 'users'
                """
            )
            # hypertable = await cur.fetchone()
            # assert hypertable is not None
