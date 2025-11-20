#!/bin/bash
# Initialize database schemas and seed test data for local development
# Usage: ./scripts/setup-local-env.sh

set -e

# Color codes for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Setting up local CDC pipeline environment...${NC}\n"

# Source database connection details from environment or defaults
CASSANDRA_HOST=${CASSANDRA_HOST:-localhost}
CASSANDRA_PORT=${CASSANDRA_PORT:-9042}

POSTGRES_HOST=${POSTGRES_HOST:-localhost}
POSTGRES_PORT=${POSTGRES_PORT:-5432}
POSTGRES_USER=${POSTGRES_USER:-postgres}
POSTGRES_PASSWORD=${POSTGRES_PASSWORD:-postgres}
POSTGRES_DB=${POSTGRES_DB:-warehouse}

CLICKHOUSE_HOST=${CLICKHOUSE_HOST:-localhost}
CLICKHOUSE_PORT=${CLICKHOUSE_PORT:-8123}

TIMESCALEDB_HOST=${TIMESCALEDB_HOST:-localhost}
TIMESCALEDB_PORT=${TIMESCALEDB_PORT:-5433}
TIMESCALEDB_USER=${TIMESCALEDB_USER:-postgres}
TIMESCALEDB_PASSWORD=${TIMESCALEDB_PASSWORD:-postgres}
TIMESCALEDB_DB=${TIMESCALEDB_DB:-timeseries}

# ============================================================================
# Step 1: Wait for databases to be ready
# ============================================================================
echo -e "${YELLOW}Step 1: Checking database health...${NC}"
if ! ./scripts/wait-for-databases.sh; then
    echo -e "${RED}Failed to connect to databases. Please ensure all services are running.${NC}"
    echo -e "${YELLOW}Hint: Run 'docker-compose up -d' to start all services${NC}"
    exit 1
fi

# ============================================================================
# Step 2: Setup Cassandra
# ============================================================================
echo -e "\n${YELLOW}Step 2: Setting up Cassandra schema...${NC}"

# Create keyspace with CDC enabled
docker exec -i cdc-cassandra cqlsh -e "CREATE KEYSPACE IF NOT EXISTS ecommerce WITH replication = {'class': 'SimpleStrategy', 'replication_factor': 1};" || echo -e "${YELLOW}  Keyspace may already exist${NC}"

# Create users table with CDC
docker exec -i cdc-cassandra cqlsh -e "CREATE TABLE IF NOT EXISTS ecommerce.users (user_id UUID PRIMARY KEY, email TEXT, phone TEXT, first_name TEXT, last_name TEXT, age INT, city TEXT, created_at TIMESTAMP) WITH cdc = true;" || echo -e "${YELLOW}  Users table may already exist${NC}"

# Create orders table with CDC
docker exec -i cdc-cassandra cqlsh -e "CREATE TABLE IF NOT EXISTS ecommerce.orders (order_id UUID PRIMARY KEY, user_id UUID, product_id UUID, quantity INT, total_price DECIMAL, order_date TIMESTAMP) WITH cdc = true;" || echo -e "${YELLOW}  Orders table may already exist${NC}"

echo -e "${GREEN}✓ Cassandra schema created${NC}"

# ============================================================================
# Step 3: Seed test data in Cassandra
# ============================================================================
echo -e "\n${YELLOW}Step 3: Seeding Cassandra test data...${NC}"

docker exec -i cdc-cassandra cqlsh -e "INSERT INTO ecommerce.users (user_id, email, phone, first_name, last_name, age, city, created_at) VALUES (uuid(), 'alice@example.com', '555-0100', 'Alice', 'Anderson', 28, 'New York', toTimestamp(now()));"

docker exec -i cdc-cassandra cqlsh -e "INSERT INTO ecommerce.users (user_id, email, phone, first_name, last_name, age, city, created_at) VALUES (uuid(), 'bob@example.com', '555-0200', 'Bob', 'Brown', 35, 'San Francisco', toTimestamp(now()));"

docker exec -i cdc-cassandra cqlsh -e "INSERT INTO ecommerce.users (user_id, email, phone, first_name, last_name, age, city, created_at) VALUES (uuid(), 'carol@example.com', '555-0300', 'Carol', 'Chen', 42, 'Seattle', toTimestamp(now()));"

echo -e "${GREEN}✓ Cassandra test data seeded (3 users)${NC}"

# ============================================================================
# Step 4: Setup Postgres
# ============================================================================
echo -e "\n${YELLOW}Step 4: Setting up Postgres schema...${NC}"

docker exec -i cdc-postgres psql -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" <<EOF
-- Create users table
CREATE TABLE IF NOT EXISTS users (
    user_id UUID PRIMARY KEY,
    email VARCHAR(255),
    phone VARCHAR(20),
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    age INTEGER,
    city VARCHAR(100),
    created_at TIMESTAMPTZ,
    -- CDC tracking columns
    cdc_synced_at TIMESTAMPTZ DEFAULT NOW(),
    cdc_version INTEGER DEFAULT 1
);

-- Create orders table
CREATE TABLE IF NOT EXISTS orders (
    order_id UUID PRIMARY KEY,
    user_id UUID,
    product_id UUID,
    quantity INTEGER,
    total_price NUMERIC(10, 2),
    order_date TIMESTAMPTZ,
    -- CDC tracking columns
    cdc_synced_at TIMESTAMPTZ DEFAULT NOW(),
    cdc_version INTEGER DEFAULT 1
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders(user_id);
CREATE INDEX IF NOT EXISTS idx_orders_order_date ON orders(order_date);

-- Create offset tracking table
CREATE TABLE IF NOT EXISTS cdc_offsets (
    offset_id UUID PRIMARY KEY,
    table_name VARCHAR(255) NOT NULL,
    keyspace VARCHAR(255) NOT NULL,
    partition_id INTEGER NOT NULL,
    destination VARCHAR(50) NOT NULL,
    commitlog_file VARCHAR(500) NOT NULL,
    commitlog_position BIGINT NOT NULL,
    last_event_timestamp_micros BIGINT NOT NULL,
    last_committed_at TIMESTAMPTZ DEFAULT NOW(),
    events_replicated_count BIGINT DEFAULT 0,
    UNIQUE(table_name, keyspace, partition_id, destination)
);
EOF

echo -e "${GREEN}✓ Postgres schema created${NC}"

# ============================================================================
# Step 5: Setup ClickHouse
# ============================================================================
echo -e "\n${YELLOW}Step 5: Setting up ClickHouse schema...${NC}"

curl -s "http://${CLICKHOUSE_HOST}:${CLICKHOUSE_PORT}" --data-binary "
CREATE DATABASE IF NOT EXISTS analytics;
"

curl -s "http://${CLICKHOUSE_HOST}:${CLICKHOUSE_PORT}" --data-binary "
CREATE TABLE IF NOT EXISTS analytics.users (
    user_id UUID,
    email String,
    phone String,
    first_name String,
    last_name String,
    age Int32,
    city String,
    created_at DateTime64(3),
    -- CDC tracking columns
    cdc_synced_at DateTime64(3) DEFAULT now64(3),
    cdc_version UInt32 DEFAULT 1
) ENGINE = MergeTree()
ORDER BY (created_at, user_id);
"

curl -s "http://${CLICKHOUSE_HOST}:${CLICKHOUSE_PORT}" --data-binary "
CREATE TABLE IF NOT EXISTS analytics.orders (
    order_id UUID,
    user_id UUID,
    product_id UUID,
    quantity Int32,
    total_price Decimal(10, 2),
    order_date DateTime64(3),
    -- CDC tracking columns
    cdc_synced_at DateTime64(3) DEFAULT now64(3),
    cdc_version UInt32 DEFAULT 1
) ENGINE = MergeTree()
ORDER BY (order_date, order_id);
"

curl -s "http://${CLICKHOUSE_HOST}:${CLICKHOUSE_PORT}" --data-binary "
CREATE TABLE IF NOT EXISTS analytics.cdc_offsets (
    offset_id UUID,
    table_name String,
    keyspace String,
    partition_id Int32,
    destination String,
    commitlog_file String,
    commitlog_position Int64,
    last_event_timestamp_micros Int64,
    last_committed_at DateTime64(3),
    events_replicated_count Int64
) ENGINE = ReplacingMergeTree()
ORDER BY (table_name, keyspace, partition_id, destination);
"

echo -e "${GREEN}✓ ClickHouse schema created${NC}"

# ============================================================================
# Step 6: Setup TimescaleDB
# ============================================================================
echo -e "\n${YELLOW}Step 6: Setting up TimescaleDB schema...${NC}"

docker exec -i cdc-timescaledb psql -U "${TIMESCALEDB_USER}" -d "${TIMESCALEDB_DB}" <<EOF
-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Create users table
CREATE TABLE IF NOT EXISTS users (
    user_id UUID,
    email VARCHAR(255),
    phone VARCHAR(20),
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    age INTEGER,
    city VARCHAR(100),
    created_at TIMESTAMPTZ NOT NULL,
    -- CDC tracking columns
    cdc_synced_at TIMESTAMPTZ DEFAULT NOW(),
    cdc_version INTEGER DEFAULT 1
);

-- Create orders table
CREATE TABLE IF NOT EXISTS orders (
    order_id UUID,
    user_id UUID,
    product_id UUID,
    quantity INTEGER,
    total_price NUMERIC(10, 2),
    order_date TIMESTAMPTZ NOT NULL,
    -- CDC tracking columns
    cdc_synced_at TIMESTAMPTZ DEFAULT NOW(),
    cdc_version INTEGER DEFAULT 1
);

-- Convert to hypertables (time-series optimization)
SELECT create_hypertable('users', 'created_at', if_not_exists => TRUE);
SELECT create_hypertable('orders', 'order_date', if_not_exists => TRUE);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders(user_id, order_date DESC);

-- Create offset tracking table
CREATE TABLE IF NOT EXISTS cdc_offsets (
    offset_id UUID PRIMARY KEY,
    table_name VARCHAR(255) NOT NULL,
    keyspace VARCHAR(255) NOT NULL,
    partition_id INTEGER NOT NULL,
    destination VARCHAR(50) NOT NULL,
    commitlog_file VARCHAR(500) NOT NULL,
    commitlog_position BIGINT NOT NULL,
    last_event_timestamp_micros BIGINT NOT NULL,
    last_committed_at TIMESTAMPTZ DEFAULT NOW(),
    events_replicated_count BIGINT DEFAULT 0,
    UNIQUE(table_name, keyspace, partition_id, destination)
);
EOF

echo -e "${GREEN}✓ TimescaleDB schema created${NC}"

# ============================================================================
# Summary
# ============================================================================
echo -e "\n${GREEN}🎉 Local environment setup complete!${NC}\n"

echo -e "${BLUE}Database Connection Details:${NC}"
echo -e "  ${YELLOW}Cassandra:${NC}    ${CASSANDRA_HOST}:${CASSANDRA_PORT} (keyspace: ecommerce)"
echo -e "  ${YELLOW}Postgres:${NC}     ${POSTGRES_HOST}:${POSTGRES_PORT} (database: ${POSTGRES_DB})"
echo -e "  ${YELLOW}ClickHouse:${NC}   ${CLICKHOUSE_HOST}:${CLICKHOUSE_PORT} (database: analytics)"
echo -e "  ${YELLOW}TimescaleDB:${NC}  ${TIMESCALEDB_HOST}:${TIMESCALEDB_PORT} (database: ${TIMESCALEDB_DB})"

echo -e "\n${BLUE}Next Steps:${NC}"
echo -e "  1. Run tests: ${YELLOW}pytest tests/${NC}"
echo -e "  2. Start pipeline: ${YELLOW}python -m src.main${NC}"
echo -e "  3. View metrics: ${YELLOW}http://localhost:9090/metrics${NC}"
echo -e ""
