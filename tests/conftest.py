"""
Pytest Fixtures and Test Configuration
Provides testcontainers for Cassandra, Postgres, ClickHouse, TimescaleDB
"""

import asyncio
from typing import AsyncGenerator, Generator

import pytest
from cassandra.cluster import Cluster, Session
from clickhouse_driver import Client as ClickHouseClient
from psycopg import AsyncConnection
from testcontainers.cassandra import CassandraContainer
from testcontainers.clickhouse import ClickHouseContainer
from testcontainers.postgres import PostgresContainer

# ============================================================================
# Event Loop Configuration
# ============================================================================


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """
    Create an event loop for the entire test session

    This ensures all async tests share the same event loop
    """
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# ============================================================================
# Cassandra Testcontainer
# ============================================================================


@pytest.fixture(scope="session")
def cassandra_container() -> Generator[CassandraContainer, None, None]:
    """
    Start a Cassandra testcontainer for the test session

    Yields:
        Running CassandraContainer instance
    """
    container = CassandraContainer("cassandra:4.1")
    container.start()
    yield container
    container.stop()


@pytest.fixture(scope="session")
def cassandra_session(
    cassandra_container: CassandraContainer,
) -> Generator[Session, None, None]:
    """
    Create a Cassandra session connected to the testcontainer

    Args:
        cassandra_container: Running Cassandra container

    Yields:
        Cassandra Session instance
    """
    cluster = Cluster(
        [cassandra_container.get_container_host_ip()],
        port=cassandra_container.get_exposed_port(9042),
    )
    session = cluster.connect()

    # Create test keyspace
    session.execute(
        """
        CREATE KEYSPACE IF NOT EXISTS test_keyspace
        WITH replication = {'class': 'SimpleStrategy', 'replication_factor': 1}
        """
    )
    session.set_keyspace("test_keyspace")

    yield session

    # Cleanup
    session.shutdown()
    cluster.shutdown()


# ============================================================================
# Postgres Testcontainer
# ============================================================================


@pytest.fixture(scope="session")
def postgres_container() -> Generator[PostgresContainer, None, None]:
    """
    Start a Postgres testcontainer for the test session

    Yields:
        Running PostgresContainer instance
    """
    container = PostgresContainer("postgres:15", driver=None)
    container.start()
    yield container
    container.stop()


@pytest.fixture
async def postgres_connection(
    postgres_container: PostgresContainer,
) -> AsyncGenerator[AsyncConnection, None]:
    """
    Create an async Postgres connection to the testcontainer

    Args:
        postgres_container: Running Postgres container

    Yields:
        Async Postgres connection
    """
    connection_url = postgres_container.get_connection_url().replace("psycopg2", "")
    async with await AsyncConnection.connect(connection_url) as conn:
        yield conn


# ============================================================================
# ClickHouse Testcontainer
# ============================================================================


@pytest.fixture(scope="session")
def clickhouse_container() -> Generator[ClickHouseContainer, None, None]:
    """
    Start a ClickHouse testcontainer for the test session

    Yields:
        Running ClickHouseContainer instance
    """
    container = ClickHouseContainer("clickhouse/clickhouse-server:23")
    container.start()
    yield container
    container.stop()


@pytest.fixture
def clickhouse_client(
    clickhouse_container: ClickHouseContainer,
) -> Generator[ClickHouseClient, None, None]:
    """
    Create a ClickHouse client connected to the testcontainer

    ClickHouse 23+ requires authentication. Testcontainers creates
    a default user with username="test" and password="test".

    Args:
        clickhouse_container: Running ClickHouse container

    Yields:
        ClickHouse Client instance
    """
    client = ClickHouseClient(
        host=clickhouse_container.get_container_host_ip(),
        port=clickhouse_container.get_exposed_port(9000),
        database="default",
        user=clickhouse_container.username,
        password=clickhouse_container.password,
    )
    yield client
    client.disconnect()


# ============================================================================
# TimescaleDB Testcontainer
# ============================================================================


@pytest.fixture(scope="session")
def timescaledb_container() -> Generator[PostgresContainer, None, None]:
    """
    Start a TimescaleDB testcontainer for the test session

    Yields:
        Running PostgresContainer with TimescaleDB extension
    """
    container = PostgresContainer("timescale/timescaledb:2.23.1-pg15", driver=None)
    container.start()
    yield container
    container.stop()


@pytest.fixture
async def timescaledb_connection(
    timescaledb_container: PostgresContainer,
) -> AsyncGenerator[AsyncConnection, None]:
    """
    Create an async TimescaleDB connection to the testcontainer

    Args:
        timescaledb_container: Running TimescaleDB container

    Yields:
        Async TimescaleDB connection
    """
    connection_url = timescaledb_container.get_connection_url().replace("psycopg2", "")
    async with await AsyncConnection.connect(connection_url) as conn:
        # Enable TimescaleDB extension
        async with conn.cursor() as cur:
            await cur.execute("CREATE EXTENSION IF NOT EXISTS timescaledb;")
        await conn.commit()
        yield conn


# ============================================================================
# Test Data Fixtures
# ============================================================================


@pytest.fixture
def sample_users_table_schema() -> str:
    """
    Sample Cassandra schema for users table

    Returns:
        CQL CREATE TABLE statement
    """
    return """
        CREATE TABLE IF NOT EXISTS users (
            user_id UUID PRIMARY KEY,
            email TEXT,
            phone TEXT,
            first_name TEXT,
            last_name TEXT,
            age INT,
            city TEXT,
            created_at TIMESTAMP
        )
    """


@pytest.fixture
def sample_orders_table_schema() -> str:
    """
    Sample Cassandra schema for orders table

    Returns:
        CQL CREATE TABLE statement
    """
    return """
        CREATE TABLE IF NOT EXISTS orders (
            order_id UUID PRIMARY KEY,
            user_id UUID,
            product_id UUID,
            quantity INT,
            total_price DECIMAL,
            order_date TIMESTAMP
        )
    """


# ============================================================================
# Cleanup Utilities
# ============================================================================


@pytest.fixture(autouse=True)
async def cleanup_test_data(
    postgres_connection: AsyncConnection,
    clickhouse_client: ClickHouseClient,
    timescaledb_connection: AsyncConnection,
) -> AsyncGenerator[None, None]:
    """
    Automatically cleanup test data after each test

    This fixture runs after every test to ensure clean state
    """
    yield

    # Cleanup Postgres
    async with postgres_connection.cursor() as cur:
        await cur.execute("DROP SCHEMA IF EXISTS public CASCADE;")
        await cur.execute("CREATE SCHEMA public;")
    await postgres_connection.commit()

    # Cleanup ClickHouse
    clickhouse_client.execute("DROP DATABASE IF EXISTS test_db;")
    clickhouse_client.execute("CREATE DATABASE IF NOT EXISTS test_db;")

    # Cleanup TimescaleDB
    async with timescaledb_connection.cursor() as cur:
        await cur.execute("DROP SCHEMA IF EXISTS public CASCADE;")
        await cur.execute("CREATE SCHEMA public;")
        # TimescaleDB extension is already installed at database level, no need to recreate
    await timescaledb_connection.commit()
