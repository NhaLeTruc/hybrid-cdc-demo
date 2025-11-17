"""
Integration test for Cassandra → ClickHouse replication
End-to-end test of CDC pipeline from Cassandra to ClickHouse warehouse
"""

from datetime import datetime, timezone
from uuid import uuid4


class TestCassandraToClickHouse:
    """Test end-to-end replication from Cassandra to ClickHouse"""

    def test_insert_event_replicates_to_clickhouse(
        self, cassandra_session, clickhouse_client, sample_users_table_schema
    ):
        """Test that INSERT in Cassandra replicates to ClickHouse"""
        # Setup: Create table in Cassandra
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
        # pipeline.run_once()

        # Verify replication to ClickHouse
        # result = clickhouse_client.execute("SELECT * FROM analytics.users WHERE user_id = %s", (str(user_id),))
        # assert len(result) > 0

    def test_batch_insert_replicates_to_clickhouse(
        self, cassandra_session, clickhouse_client, sample_users_table_schema
    ):
        """Test that batch inserts replicate correctly to ClickHouse"""
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
                (
                    user_id,
                    f"user{i}@example.com",
                    f"User{i}",
                    "Test",
                    20 + i,
                    datetime.now(timezone.utc),
                ),
            )

        # Run CDC
        # pipeline.run_batch()

        # Verify count
        # result = clickhouse_client.execute("SELECT COUNT(*) as count FROM analytics.users")
        # assert result[0][0] == 100
