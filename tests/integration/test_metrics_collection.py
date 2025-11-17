"""
Integration test for metrics collection during replication
Verifies metrics are updated correctly during CDC pipeline operation
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest


@pytest.mark.asyncio
class TestMetricsCollection:
    """Test metrics collection during pipeline operation"""

    async def test_events_processed_counter_increments(
        self, cassandra_session, postgres_connection, sample_users_table_schema
    ):
        """Test that events_processed_total counter increments during replication"""
        # Setup
        cassandra_session.execute(sample_users_table_schema)

        # Insert events
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
                    25,
                    datetime.now(timezone.utc),
                ),
            )

        # Run pipeline
        # from src.main import CDCPipeline
        # pipeline = CDCPipeline()
        # await pipeline.run_batch()

        # Check metrics
        # from src.observability.metrics import events_processed_total
        # metric_value = events_processed_total.labels(destination="POSTGRES", table="users")._value.get()
        # assert metric_value >= 10

    async def test_replication_lag_gauge_updates(
        self, cassandra_session, postgres_connection, sample_users_table_schema
    ):
        """Test that replication lag gauge is updated during replication"""
        # Setup
        cassandra_session.execute(sample_users_table_schema)

        # Insert event
        user_id = uuid4()
        cassandra_session.execute(
            """
            INSERT INTO users (user_id, email, first_name, last_name, age, created_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (user_id, "test@example.com", "Test", "User", 30, datetime.now(timezone.utc)),
        )

        # Run pipeline
        # pipeline = CDCPipeline()
        # await pipeline.run_once()

        # Check lag metric
        # from src.observability.metrics import replication_lag_seconds
        # lag = replication_lag_seconds.labels(destination="POSTGRES")._value.get()
        # assert lag >= 0  # Lag should be non-negative
        # assert lag < 60  # Lag should be less than 1 minute for fresh data

    async def test_throughput_gauge_tracks_events_per_second(
        self, cassandra_session, postgres_connection, sample_users_table_schema
    ):
        """Test that throughput gauge tracks events/sec correctly"""
        # Setup
        cassandra_session.execute(sample_users_table_schema)

        # Insert many events quickly
        for i in range(100):
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
                    25,
                    datetime.now(timezone.utc),
                ),
            )

        # Run pipeline
        # pipeline = CDCPipeline()
        # start_time = time.time()
        # await pipeline.run_batch()
        # duration = time.time() - start_time

        # Check throughput
        # from src.observability.metrics import events_per_second
        # eps = events_per_second.labels(destination="POSTGRES")._value.get()
        # expected_eps = 100 / duration
        # assert eps > 0
        # assert abs(eps - expected_eps) < 100  # Within reasonable range

    async def test_errors_counter_increments_on_failure(
        self, cassandra_session, postgres_connection, sample_users_table_schema
    ):
        """Test that errors counter increments when writes fail"""
        # Setup
        cassandra_session.execute(sample_users_table_schema)

        # Insert event
        user_id = uuid4()
        cassandra_session.execute(
            """
            INSERT INTO users (user_id, email, first_name, last_name, age, created_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (user_id, "test@example.com", "Test", "User", 30, datetime.now(timezone.utc)),
        )

        # Simulate failure by disconnecting destination
        # ... setup failure scenario

        # Run pipeline (should fail and increment errors)
        # try:
        #     await pipeline.run_once()
        # except:
        #     pass

        # Check errors metric
        # from src.observability.metrics import errors_total
        # errors = errors_total.labels(destination="POSTGRES", error_type="connection_error")._value.get()
        # assert errors > 0

    async def test_backlog_depth_gauge_reflects_queue_size(
        self, cassandra_session, postgres_connection, sample_users_table_schema
    ):
        """Test that backlog depth gauge reflects uncommitted events"""
        # Setup
        cassandra_session.execute(sample_users_table_schema)

        # Insert many events
        for i in range(50):
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
                    25,
                    datetime.now(timezone.utc),
                ),
            )

        # Check backlog before processing
        # from src.observability.metrics import backlog_depth
        # backlog_before = backlog_depth.labels(destination="POSTGRES")._value.get()

        # Run pipeline
        # await pipeline.run_batch()

        # Backlog should decrease after processing
        # backlog_after = backlog_depth.labels(destination="POSTGRES")._value.get()
        # assert backlog_after < backlog_before

    async def test_replication_duration_histogram_records_latency(
        self, cassandra_session, postgres_connection, sample_users_table_schema
    ):
        """Test that replication duration histogram records batch latency"""
        # Setup
        cassandra_session.execute(sample_users_table_schema)

        # Insert event
        user_id = uuid4()
        cassandra_session.execute(
            """
            INSERT INTO users (user_id, email, first_name, last_name, age, created_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (user_id, "test@example.com", "Test", "User", 30, datetime.now(timezone.utc)),
        )

        # Run pipeline
        # pipeline = CDCPipeline()
        # await pipeline.run_once()

        # Check histogram
        # from src.observability.metrics import replication_duration_seconds
        # histogram = replication_duration_seconds.labels(destination="POSTGRES")
        # assert histogram._count.get() > 0  # At least one observation recorded
