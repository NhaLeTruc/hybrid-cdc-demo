#!/usr/bin/env bash
#
# Run integration tests with Docker Compose orchestration
# Sets up test databases, runs pytest, and tears down
#

set -euo pipefail

# Configuration
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yml}"
PROJECT_NAME="hybrid-cdc-test"
PYTEST_ARGS="${PYTEST_ARGS:--v -m integration}"
KEEP_CONTAINERS="${KEEP_CONTAINERS:-false}"

echo "=== CDC Integration Test Runner ==="
echo "Compose file: $COMPOSE_FILE"
echo "Project name: $PROJECT_NAME"
echo "Pytest args: $PYTEST_ARGS"
echo ""

# Cleanup function
cleanup() {
    if [ "$KEEP_CONTAINERS" = "false" ]; then
        echo ""
        echo "=== Cleaning up test containers ==="
        docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" down -v
        echo "✓ Containers stopped and removed"
    else
        echo ""
        echo "=== Keeping containers running (KEEP_CONTAINERS=true) ==="
        echo "Stop manually with: docker-compose -f $COMPOSE_FILE -p $PROJECT_NAME down -v"
    fi
}

# Register cleanup on exit
trap cleanup EXIT INT TERM

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "ERROR: Docker is not running"
    exit 1
fi

# Check if docker-compose is available
if ! command -v docker-compose &> /dev/null; then
    echo "ERROR: docker-compose not found"
    exit 1
fi

# Start test databases
echo "=== Starting test databases ==="
docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" up -d \
    cassandra postgres clickhouse timescaledb
echo "✓ Containers started"

# Wait for databases to be ready
echo ""
echo "=== Waiting for databases to be ready ==="

# Wait for Cassandra
echo "Waiting for Cassandra..."
max_attempts=60
attempt=0
while [ $attempt -lt $max_attempts ]; do
    if docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" exec -T cassandra \
        cqlsh -e "DESCRIBE KEYSPACES" > /dev/null 2>&1; then
        echo "✓ Cassandra is ready"
        break
    fi
    attempt=$((attempt + 1))
    sleep 2
done

if [ $attempt -eq $max_attempts ]; then
    echo "ERROR: Cassandra did not become ready"
    exit 1
fi

# Wait for Postgres
echo "Waiting for Postgres..."
attempt=0
while [ $attempt -lt $max_attempts ]; do
    if docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" exec -T postgres \
        pg_isready -U postgres > /dev/null 2>&1; then
        echo "✓ Postgres is ready"
        break
    fi
    attempt=$((attempt + 1))
    sleep 2
done

if [ $attempt -eq $max_attempts ]; then
    echo "ERROR: Postgres did not become ready"
    exit 1
fi

# Wait for ClickHouse
echo "Waiting for ClickHouse..."
attempt=0
while [ $attempt -lt $max_attempts ]; do
    if docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" exec -T clickhouse \
        clickhouse-client --query "SELECT 1" > /dev/null 2>&1; then
        echo "✓ ClickHouse is ready"
        break
    fi
    attempt=$((attempt + 1))
    sleep 2
done

if [ $attempt -eq $max_attempts ]; then
    echo "ERROR: ClickHouse did not become ready"
    exit 1
fi

# Wait for TimescaleDB
echo "Waiting for TimescaleDB..."
attempt=0
while [ $attempt -lt $max_attempts ]; do
    if docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" exec -T timescaledb \
        pg_isready -U postgres > /dev/null 2>&1; then
        echo "✓ TimescaleDB is ready"
        break
    fi
    attempt=$((attempt + 1))
    sleep 2
done

if [ $attempt -eq $max_attempts ]; then
    echo "ERROR: TimescaleDB did not become ready"
    exit 1
fi

echo ""
echo "=== All databases ready ==="
echo ""

# Create test keyspace and tables
echo "=== Setting up test schema ==="
docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" exec -T cassandra cqlsh <<EOF
CREATE KEYSPACE IF NOT EXISTS ecommerce
WITH replication = {'class': 'SimpleStrategy', 'replication_factor': 1};

CREATE TABLE IF NOT EXISTS ecommerce.users (
    user_id uuid PRIMARY KEY,
    email text,
    created_at timestamp
);

CREATE TABLE IF NOT EXISTS ecommerce.orders (
    order_id uuid PRIMARY KEY,
    user_id uuid,
    total decimal,
    created_at timestamp
);
EOF
echo "✓ Test schema created"

# Run pytest
echo ""
echo "=== Running integration tests ==="
echo "Command: pytest $PYTEST_ARGS"
echo ""

# Set environment variables for tests
export TEST_CASSANDRA_HOST="localhost"
export TEST_CASSANDRA_PORT="9042"
export TEST_POSTGRES_HOST="localhost"
export TEST_POSTGRES_PORT="5432"
export TEST_CLICKHOUSE_HOST="localhost"
export TEST_CLICKHOUSE_PORT="9000"
export TEST_TIMESCALEDB_HOST="localhost"
export TEST_TIMESCALEDB_PORT="5433"

# Run tests
if pytest $PYTEST_ARGS; then
    echo ""
    echo "✓✓✓ All integration tests passed! ✓✓✓"
    exit_code=0
else
    echo ""
    echo "✗✗✗ Some integration tests failed ✗✗✗"
    exit_code=1
fi

exit $exit_code
