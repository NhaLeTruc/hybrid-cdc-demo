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

    # Create ecommerce keyspace for integration tests
    session.execute(
        """
        CREATE KEYSPACE IF NOT EXISTS ecommerce
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
    Create an async Postgres connection to the testcontainer with transaction rollback support

    Args:
        postgres_container: Running Postgres container

    Yields:
        Async Postgres connection
    """
    import psycopg.pq

    connection_url = postgres_container.get_connection_url().replace("psycopg2", "")
    conn = await AsyncConnection.connect(connection_url)

    yield conn

    # CRITICAL FIX: Rollback any failed transactions before closing
    try:
        if conn.info.transaction_status == psycopg.pq.TransactionStatus.INERROR:
            await conn.rollback()
    except Exception:
        pass  # Connection might already be closed
    finally:
        await conn.close()


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


@pytest.fixture
def clickhouse_connection(clickhouse_client: ClickHouseClient) -> Generator[ClickHouseClient, None, None]:
    """
    Alias for clickhouse_client to match test expectations.

    Some tests expect 'clickhouse_connection' instead of 'clickhouse_client'.
    """
    yield clickhouse_client


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
    Create an async TimescaleDB connection to the testcontainer with transaction rollback support

    Args:
        timescaledb_container: Running TimescaleDB container

    Yields:
        Async TimescaleDB connection
    """
    import psycopg.pq

    connection_url = timescaledb_container.get_connection_url().replace("psycopg2", "")
    conn = await AsyncConnection.connect(connection_url)

    # Enable TimescaleDB extension
    async with conn.cursor() as cur:
        await cur.execute("CREATE EXTENSION IF NOT EXISTS timescaledb;")
    await conn.commit()

    yield conn

    # CRITICAL FIX: Rollback any failed transactions before closing
    try:
        if conn.info.transaction_status == psycopg.pq.TransactionStatus.INERROR:
            await conn.rollback()
    except Exception:
        pass  # Connection might already be closed
    finally:
        await conn.close()


# ============================================================================
# Connection URL Fixtures for Health Checks
# ============================================================================


@pytest.fixture(scope="session")
def postgres_connection_url(postgres_container: PostgresContainer) -> str:
    """Get Postgres connection URL for health checks"""
    return postgres_container.get_connection_url().replace("psycopg2", "")


@pytest.fixture(scope="session")
def timescaledb_connection_url(timescaledb_container: PostgresContainer) -> str:
    """Get TimescaleDB connection URL for health checks"""
    return timescaledb_container.get_connection_url().replace("psycopg2", "")


# ============================================================================
# Database Table Fixtures
# ============================================================================


@pytest.fixture
async def postgres_users_table(postgres_connection: AsyncConnection) -> AsyncGenerator[None, None]:
    """Create users table in Postgres for testing"""
    async with postgres_connection.cursor() as cur:
        await cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id UUID PRIMARY KEY,
                email TEXT,
                phone TEXT,
                first_name TEXT,
                last_name TEXT,
                age INTEGER,
                city TEXT,
                created_at TIMESTAMP
            )
        """)
    await postgres_connection.commit()
    yield
    # Cleanup handled by cleanup_test_data fixture


@pytest.fixture
async def postgres_cdc_offsets_table(postgres_connection: AsyncConnection) -> AsyncGenerator[None, None]:
    """Create cdc_offsets table in Postgres for testing"""
    async with postgres_connection.cursor() as cur:
        await cur.execute("""
            CREATE TABLE IF NOT EXISTS cdc_offsets (
                table_name TEXT PRIMARY KEY,
                commitlog_position BIGINT NOT NULL,
                events_replicated_count BIGINT DEFAULT 0,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    await postgres_connection.commit()
    yield
    # Cleanup handled by cleanup_test_data fixture


@pytest.fixture
async def timescaledb_users_table(timescaledb_connection: AsyncConnection) -> AsyncGenerator[None, None]:
    """Create users table in TimescaleDB for testing"""
    async with timescaledb_connection.cursor() as cur:
        await cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id UUID PRIMARY KEY,
                email TEXT,
                phone TEXT,
                first_name TEXT,
                last_name TEXT,
                age INTEGER,
                city TEXT,
                created_at TIMESTAMP
            )
        """)
    await timescaledb_connection.commit()
    yield
    # Cleanup handled by cleanup_test_data fixture


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
    Automatically cleanup test data after each test with deadlock prevention

    This fixture runs after every test to ensure clean state
    """
    yield

    # CRITICAL FIX: Cleanup Postgres with deadlock prevention
    try:
        # Rollback any pending transaction first
        await postgres_connection.rollback()

        async with postgres_connection.cursor() as cur:
            # Terminate other connections to avoid deadlocks
            await cur.execute("""
                SELECT pg_terminate_backend(pg_stat_activity.pid)
                FROM pg_stat_activity
                WHERE pg_stat_activity.datname = current_database()
                  AND pid <> pg_backend_pid();
            """)

            # Now safe to drop schema
            await cur.execute("DROP SCHEMA IF EXISTS public CASCADE;")
            await cur.execute("CREATE SCHEMA public;")
        await postgres_connection.commit()
    except Exception:
        pass  # Ignore cleanup errors

    # Cleanup ClickHouse
    try:
        clickhouse_client.execute("DROP DATABASE IF EXISTS test_db;")
        clickhouse_client.execute("CREATE DATABASE IF NOT EXISTS test_db;")
    except Exception:
        pass

    # CRITICAL FIX: Cleanup TimescaleDB with deadlock prevention
    try:
        # Rollback any pending transaction first
        await timescaledb_connection.rollback()

        async with timescaledb_connection.cursor() as cur:
            # Terminate other connections to avoid deadlocks
            await cur.execute("""
                SELECT pg_terminate_backend(pg_stat_activity.pid)
                FROM pg_stat_activity
                WHERE pg_stat_activity.datname = current_database()
                  AND pid <> pg_backend_pid();
            """)

            # Now safe to drop schema
            await cur.execute("DROP SCHEMA IF EXISTS public CASCADE;")
            await cur.execute("CREATE SCHEMA public;")
            # TimescaleDB extension is already installed at database level, no need to recreate
        await timescaledb_connection.commit()
    except Exception:
        pass  # Ignore cleanup errors
