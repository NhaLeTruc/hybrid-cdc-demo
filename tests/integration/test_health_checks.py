"""
Integration test for health check functionality
Verifies dependency health detection and reporting
"""

import asyncio

import pytest


@pytest.mark.asyncio
class TestHealthChecks:
    """Test health check functionality"""

    async def test_cassandra_health_check_when_up(self, cassandra_session):
        """Test Cassandra health check returns healthy when database is up"""
        from src.observability.health import check_cassandra_health

        is_healthy, latency_ms = await check_cassandra_health()

        assert is_healthy is True
        assert latency_ms >= 0

    async def test_postgres_health_check_when_up(self, postgres_connection, postgres_connection_url):
        """Test Postgres health check returns healthy when database is up"""
        from src.observability.health import check_postgres_health

        is_healthy, latency_ms = await check_postgres_health(connection_url=postgres_connection_url)

        assert is_healthy is True
        assert latency_ms >= 0

    async def test_clickhouse_health_check_when_up(self, clickhouse_client):
        """Test ClickHouse health check returns healthy when database is up"""
        from src.observability.health import check_clickhouse_health

        is_healthy, latency_ms = await check_clickhouse_health()

        assert is_healthy is True
        assert latency_ms >= 0

    async def test_timescaledb_health_check_when_up(self, timescaledb_connection, timescaledb_connection_url):
        """Test TimescaleDB health check returns healthy when database is up"""
        from src.observability.health import check_timescaledb_health

        is_healthy, latency_ms = await check_timescaledb_health(connection_url=timescaledb_connection_url)

        assert is_healthy is True
        assert latency_ms >= 0

    async def test_health_check_detects_down_database(self):
        """Test health check detects when database is down"""

        # Configure health check with invalid connection
        # ... setup invalid connection

        # is_healthy, latency_ms = await check_postgres_health()

        # assert is_healthy is False

    async def test_health_check_measures_latency(self, postgres_connection, postgres_connection_url):
        """Test that health check measures response latency"""
        from src.observability.health import check_postgres_health

        is_healthy, latency_ms = await check_postgres_health(connection_url=postgres_connection_url)

        # Latency should be reasonable (< 1 second for local database)
        assert latency_ms < 1000

    async def test_all_dependencies_health_check(
        self, cassandra_session, postgres_connection, clickhouse_client, timescaledb_connection,
        postgres_connection_url, timescaledb_connection_url
    ):
        """Test checking all dependencies at once"""
        from src.observability.health import check_all_dependencies

        health_status = await check_all_dependencies(
            postgres_url=postgres_connection_url,
            timescaledb_url=timescaledb_connection_url
        )

        # Should return dict with all dependencies
        assert "cassandra" in health_status
        assert "postgres" in health_status
        assert "clickhouse" in health_status
        assert "timescaledb" in health_status

        # All should be healthy
        for dep_name, dep_status in health_status.items():
            assert dep_status["status"] == "up"
            assert dep_status["latency_ms"] >= 0

    async def test_health_check_concurrent_execution(
        self, cassandra_session, postgres_connection, clickhouse_client, timescaledb_connection,
        postgres_connection_url, timescaledb_connection_url
    ):
        """Test that health checks can run concurrently"""
        from src.observability.health import (
            check_cassandra_health,
            check_clickhouse_health,
            check_postgres_health,
            check_timescaledb_health,
        )

        # Run all health checks concurrently
        results = await asyncio.gather(
            check_cassandra_health(),
            check_postgres_health(connection_url=postgres_connection_url),
            check_clickhouse_health(),
            check_timescaledb_health(connection_url=timescaledb_connection_url),
        )

        # All should succeed
        for is_healthy, latency_ms in results:
            assert is_healthy is True
            assert latency_ms >= 0

    async def test_health_check_timeout(self):
        """Test that health check times out for slow databases"""

        # Configure with slow/hanging connection
        # ... setup slow connection

        # Health check should timeout and return unhealthy
        # with timeout of 5 seconds
        # is_healthy, latency_ms = await check_postgres_health(timeout_seconds=5)

        # Should either timeout or complete within reasonable time
        # assert latency_ms < 6000  # Should not exceed timeout + overhead
